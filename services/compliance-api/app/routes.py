import json
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from sqlalchemy import text

from .agents import run_compliance_workflow
from .config import get_settings
from .db import connection
from .ingestion import SUPPORTED_EXTENSIONS, content_hash
from .rag import delete_document_embeddings, index_document
from .schemas import (
    AgentRunResponse,
    AssistantRequest,
    AssistantResponse,
    AuditReportInput,
    AuditReportResponse,
    ComplianceIssueInput,
    ComplianceIssueResponse,
    ComplianceIssueUpdate,
    DashboardResponse,
    DocumentResponse,
    HealthResponse,
    NotificationInput,
    NotificationResponse,
)
from .tools import create_issue, generate_audit_report, send_compliance_notification, update_issue


router = APIRouter()


def _document(row) -> DocumentResponse:
    return DocumentResponse.model_validate(dict(row))


def _issue(row) -> ComplianceIssueResponse:
    data = dict(row)
    data["evidence"] = data.get("evidence") or []
    data["source_document_ids"] = [UUID(value) for value in (data.get("source_document_ids") or [])]
    return ComplianceIssueResponse.model_validate(data)


def _run(row) -> AgentRunResponse:
    data = dict(row)
    data["agents_involved"] = data.get("agents_involved") or []
    return AgentRunResponse.model_validate(data)


@router.get("/healthz", response_model=HealthResponse)
def health() -> HealthResponse:
    with connection() as conn:
        conn.execute(text("SELECT 1"))
    settings = get_settings()
    chroma_ready = Path(settings.chroma_persist_directory).exists()
    return HealthResponse(
        status="ok",
        database="connected",
        llm_configured=bool(settings.openai_api_key),
        rag_ready=chroma_ready,
    )


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard() -> DashboardResponse:
    with connection() as conn:
        counts = conn.execute(
            text(
                """
                SELECT
                  (SELECT count(*) FROM compliance_issues WHERE status IN ('OPEN', 'IN_REVIEW')) AS open_issues,
                  (SELECT count(*) FROM compliance_issues WHERE risk IN ('HIGH', 'CRITICAL') AND status != 'REMEDIATED') AS high_risk_issues,
                  (SELECT count(*) FROM documents WHERE status = 'INDEXED') AS documents_indexed,
                  (SELECT count(*) FROM audit_reports WHERE status = 'COMPLETED') AS completed_audits,
                  (SELECT count(*) FROM compliance_issues WHERE status = 'REMEDIATED') AS remediated_issues,
                  (SELECT count(*) FROM compliance_issues) AS total_issues
                """
            )
        ).mappings().one()
        runs = conn.execute(
            text("SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT 8")
        ).mappings().all()
    total = int(counts["total_issues"])
    score = 100.0 if total == 0 else round(int(counts["remediated_issues"]) / total * 100, 1)
    return DashboardResponse(
        compliance_score=score,
        open_issues=int(counts["open_issues"]),
        high_risk_issues=int(counts["high_risk_issues"]),
        documents_indexed=int(counts["documents_indexed"]),
        completed_audits=int(counts["completed_audits"]),
        recent_runs=[_run(row) for row in runs],
    )


@router.post("/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Query(..., pattern="^(regulation|policy|audit|other)$"),
    is_synthetic: bool = Query(False),
) -> DocumentResponse:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(400, "Only PDF, DOCX, and TXT documents are supported.")
    data = await file.read()
    digest = content_hash(data)
    settings = get_settings()
    directory = Path(settings.upload_directory)
    directory.mkdir(parents=True, exist_ok=True)
    document_id = uuid4()
    path = directory / f"{document_id}{suffix}"
    path.write_bytes(data)
    with connection() as conn:
        duplicate = conn.execute(
            text("SELECT id FROM documents WHERE content_hash = :content_hash"),
            {"content_hash": digest},
        ).first()
    if duplicate:
        path.unlink(missing_ok=True)
        raise HTTPException(409, "This document has already been indexed.")
    try:
        chunk_count = index_document(path, document_id, file.filename or path.name, category)
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(422, f"Document indexing failed: {exc}") from exc

    with connection() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO documents
                  (id, name, document_type, category, source_path, content_hash, status, chunk_count, is_synthetic, indexed_at)
                VALUES
                  (:id, :name, :document_type, :category, :source_path, :content_hash, 'INDEXED', :chunk_count, :is_synthetic, now())
                RETURNING *
                """
            ),
            {
                "id": document_id,
                "name": file.filename or path.name,
                "document_type": suffix.lstrip(".").upper(),
                "category": category,
                "source_path": str(path),
                "content_hash": digest,
                "chunk_count": chunk_count,
                "is_synthetic": is_synthetic,
            },
        ).mappings().one()
    return _document(row)


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents() -> list[DocumentResponse]:
    with connection() as conn:
        rows = conn.execute(text("SELECT * FROM documents ORDER BY created_at DESC")).mappings().all()
    return [_document(row) for row in rows]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID) -> None:
    with connection() as conn:
        row = conn.execute(
            text("SELECT source_path FROM documents WHERE id = :id"),
            {"id": document_id},
        ).mappings().first()
    if not row:
        raise HTTPException(404, "Document not found.")
    try:
        delete_document_embeddings(document_id)
    except Exception as exc:
        raise HTTPException(500, f"Document vector cleanup failed: {exc}") from exc
    with connection() as conn:
        conn.execute(text("DELETE FROM documents WHERE id = :id"), {"id": document_id})
    Path(row["source_path"]).unlink(missing_ok=True)


@router.post("/assistant/analyze", response_model=AssistantResponse)
def analyze(request: AssistantRequest) -> AssistantResponse:
    run_id = uuid4()
    thread_id = str(uuid4())
    with connection() as conn:
        conn.execute(
            text(
                """
                INSERT INTO agent_runs (id, thread_id, question, status, current_agent)
                VALUES (:id, :thread_id, :question, 'RUNNING', 'Supervisor Agent')
                """
            ),
            {"id": run_id, "thread_id": thread_id, "question": request.question},
        )
    try:
        result = run_compliance_workflow(
            request.question,
            regulation_document_id=request.regulation_document_id,
            policy_document_id=request.policy_document_id,
        )
        with connection() as conn:
            row = conn.execute(
                text(
                    """
                    UPDATE agent_runs
                    SET status = 'COMPLETED', current_agent = NULL, agents_involved = CAST(:agents AS jsonb),
                        result = CAST(:result AS jsonb), completed_at = now()
                    WHERE id = :id RETURNING *
                    """
                ),
                {
                    "id": run_id,
                    "agents": json.dumps(result.get("agents_involved", [])),
                    "result": json.dumps(result, default=str),
                },
            ).mappings().one()
    except Exception as exc:
        with connection() as conn:
            conn.execute(
                text("UPDATE agent_runs SET status = 'FAILED', error = :error, completed_at = now() WHERE id = :id"),
                {"id": run_id, "error": str(exc)},
            )
        raise HTTPException(502, f"Compliance workflow failed: {exc}") from exc

    evidence = result.get("evidence", [])
    evidence_indexes = set(
        result.get("audit", {}).get("evidence", [])
        + result.get("risk", {}).get("evidence", [])
        + result.get("policy", {}).get("evidence", [])
        + result.get("regulation", {}).get("evidence", [])
    )
    selected_evidence = [item for index, item in enumerate(evidence) if index in evidence_indexes]
    document_ids = [UUID(item["document_id"]) for item in selected_evidence if item.get("document_id")]
    documents = []
    if document_ids:
        with connection() as conn:
            rows = conn.execute(
                text("SELECT * FROM documents WHERE id = ANY(CAST(:ids AS uuid[]))"),
                {"ids": "{" + ",".join(str(item) for item in document_ids) + "}"},
            ).mappings().all()
        documents = [_document(row) for row in rows]
    audit = result.get("audit", {})
    risk_level = result.get("risk", {}).get("risk_level", "HIGH")
    return AssistantResponse(
        run=_run(row),
        answer=audit.get("audit_summary", "The requirement could not be verified from indexed evidence."),
        compliance_status=result.get("policy", {}).get("compliance_status", "UNVERIFIED"),
        risk_level=risk_level,
        evidence=selected_evidence,
        source_documents=documents,
        agents_involved=result.get("agents_involved", []),
    )


@router.get("/runs", response_model=list[AgentRunResponse])
def list_runs(limit: int = Query(20, ge=1, le=100)) -> list[AgentRunResponse]:
    with connection() as conn:
        rows = conn.execute(
            text("SELECT * FROM agent_runs ORDER BY started_at DESC LIMIT :limit"),
            {"limit": limit},
        ).mappings().all()
    return [_run(row) for row in rows]


@router.get("/issues", response_model=list[ComplianceIssueResponse])
def list_issues(status_filter: str | None = Query(None, alias="status")) -> list[ComplianceIssueResponse]:
    with connection() as conn:
        if status_filter:
            rows = conn.execute(
                text("SELECT * FROM compliance_issues WHERE status = :status ORDER BY created_at DESC"),
                {"status": status_filter},
            ).mappings().all()
        else:
            rows = conn.execute(text("SELECT * FROM compliance_issues ORDER BY created_at DESC")).mappings().all()
    return [_issue(row) for row in rows]


@router.post("/issues", response_model=ComplianceIssueResponse, status_code=status.HTTP_201_CREATED)
def create_issue_route(request: ComplianceIssueInput) -> ComplianceIssueResponse:
    return _issue(create_issue(request.model_dump()))


@router.patch("/issues/{issue_id}", response_model=ComplianceIssueResponse)
def update_issue_route(issue_id: UUID, request: ComplianceIssueUpdate) -> ComplianceIssueResponse:
    row = update_issue(issue_id, request.model_dump())
    if not row:
        raise HTTPException(404, "Compliance issue not found.")
    return _issue(row)


@router.get("/reports", response_model=list[AuditReportResponse])
def list_reports() -> list[AuditReportResponse]:
    with connection() as conn:
        rows = conn.execute(text("SELECT * FROM audit_reports ORDER BY created_at DESC")).mappings().all()
    return [AuditReportResponse.model_validate(dict(row)) for row in rows]


@router.post("/reports", response_model=AuditReportResponse, status_code=status.HTTP_201_CREATED)
def create_audit_report(request: AuditReportInput) -> AuditReportResponse:
    result = generate_audit_report.invoke(
        {
            "title": request.title,
            "summary": request.summary,
            "findings_json": json.dumps(request.findings),
        }
    )
    return AuditReportResponse.model_validate(json.loads(result))


@router.post("/notifications", response_model=NotificationResponse, status_code=status.HTTP_201_CREATED)
def send_notification(request: NotificationInput) -> NotificationResponse:
    result = send_compliance_notification.invoke(
        {
            "issue_id": str(request.issue_id),
            "recipient": request.recipient,
            "message": request.message,
        }
    )
    return NotificationResponse.model_validate(json.loads(result))


@router.get("/openapi-tools")
def available_tools() -> dict[str, list[str]]:
    return {
        "tools": [
            "search_regulations",
            "retrieve_policies",
            "create_compliance_issue",
            "update_compliance_issue",
            "generate_audit_report",
            "send_compliance_notification",
        ]
    }