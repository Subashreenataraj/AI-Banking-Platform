import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from langchain_core.tools import tool
from sqlalchemy import text

from .db import connection
from .rag import retrieve_evidence


def create_issue(data: dict[str, Any]) -> dict[str, Any]:
    issue_id = uuid4()
    now = datetime.utcnow()
    with connection() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO compliance_issues
                    (id, finding, regulation, risk, recommendation, evidence, source_document_ids)
                VALUES (:id, :finding, :regulation, :risk, :recommendation, CAST(:evidence AS jsonb), CAST(:source_ids AS jsonb))
                RETURNING *
                """
            ),
            {
                "id": issue_id,
                "finding": data["finding"],
                "regulation": data["regulation"],
                "risk": data["risk"],
                "recommendation": data["recommendation"],
                "evidence": json.dumps(data.get("evidence", [])),
                "source_ids": json.dumps([str(item) for item in data.get("source_document_ids", [])]),
            },
        ).mappings().one()
    return dict(row)


def update_issue(issue_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
    allowed = {key: value for key, value in data.items() if value is not None}
    if not allowed:
        with connection() as conn:
            row = conn.execute(
                text("SELECT * FROM compliance_issues WHERE id = :id"),
                {"id": issue_id},
            ).mappings().first()
            return dict(row) if row else None
    assignments = ", ".join(f"{key} = :{key}" for key in allowed)
    allowed["id"] = issue_id
    with connection() as conn:
        row = conn.execute(
            text(f"UPDATE compliance_issues SET {assignments}, updated_at = now() WHERE id = :id RETURNING *"),
            allowed,
        ).mappings().first()
    return dict(row) if row else None


@tool
def search_regulations(query: str) -> str:
    """Search indexed regulatory documents and return grounded evidence."""
    return json.dumps(retrieve_evidence(query, category="regulation", k=6))


@tool
def retrieve_policies(query: str) -> str:
    """Search indexed internal policy documents and return grounded evidence."""
    return json.dumps(retrieve_evidence(query, category="policy", k=6))


@tool
def create_compliance_issue(
    finding: str,
    regulation: str,
    risk: str,
    recommendation: str,
) -> str:
    """Create a compliance issue using the platform business operation."""
    return json.dumps(
        create_issue(
            {
                "finding": finding,
                "regulation": regulation,
                "risk": risk,
                "recommendation": recommendation,
            }
        ),
        default=str,
    )


@tool
def update_compliance_issue(issue_id: str, status: str, recommendation: str = "") -> str:
    """Update a compliance issue using the platform business operation."""
    result = update_issue(
        UUID(issue_id),
        {"status": status, "recommendation": recommendation or None},
    )
    return json.dumps(result, default=str)


OPENAPI_TOOLS = [
    search_regulations,
    retrieve_policies,
    create_compliance_issue,
    update_compliance_issue,
]


@tool
def generate_audit_report(title: str, summary: str, findings_json: str = "[]") -> str:
    """Persist a structured audit report generated from grounded findings."""
    report_id = uuid4()
    findings = json.loads(findings_json)
    with connection() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO audit_reports (id, title, summary, findings, generated_by)
                VALUES (:id, :title, :summary, CAST(:findings AS jsonb), 'Audit Report Agent')
                RETURNING *
                """
            ),
            {
                "id": report_id,
                "title": title,
                "summary": summary,
                "findings": json.dumps(findings),
            },
        ).mappings().one()
    return json.dumps(dict(row), default=str)


@tool
def send_compliance_notification(issue_id: str, recipient: str, message: str) -> str:
    """Record a compliance notification sent to an issue owner."""
    notification = {
        "id": str(uuid4()),
        "issue_id": issue_id,
        "recipient": recipient,
        "message": message,
        "status": "SENT",
        "sent_at": datetime.now(timezone.utc).isoformat(),
    }
    with connection() as conn:
        conn.execute(
            text(
                """
                INSERT INTO compliance_notifications (id, issue_id, recipient, message, status, sent_at)
                VALUES (:id, :issue_id, :recipient, :message, :status, :sent_at)
                """
            ),
            notification,
        )
    return json.dumps(notification)


OPENAPI_TOOLS.extend([generate_audit_report, send_compliance_notification])