from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]

IssueStatus = Literal[
    "OPEN",
    "IN_REVIEW",
    "REMEDIATED",
    "ACCEPTED",
]

DocumentStatus = Literal[
    "UPLOADED",
    "INDEXING",
    "INDEXED",
    "FAILED",
]

ComplianceStatus = Literal[
    "COMPLIANT",
    "PARTIALLY_COMPLIANT",
    "NON_COMPLIANT",
    "UNVERIFIED",
]


class HealthResponse(BaseModel):
    status: str
    database: str
    llm_configured: bool
    rag_ready: bool


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    document_type: str
    category: str
    status: str
    chunk_count: int
    is_synthetic: bool
    created_at: datetime
    indexed_at: datetime | None = None


class Evidence(BaseModel):
    chunk_id: UUID | None = None
    document_id: UUID | None = None
    document_name: str
    page_number: int | None = None
    excerpt: str
    source_type: str
    relevance_score: float | None = None


class ComplianceIssueInput(BaseModel):
    finding: str = Field(min_length=1)
    regulation: str = Field(min_length=1)
    risk: RiskLevel
    recommendation: str = Field(min_length=1)
    evidence: list[Evidence] = Field(default_factory=list)
    source_document_ids: list[UUID] = Field(default_factory=list)


class ComplianceIssueUpdate(BaseModel):
    status: IssueStatus | None = None
    risk: RiskLevel | None = None
    recommendation: str | None = None


class ComplianceIssueResponse(ComplianceIssueInput):
    id: UUID
    status: IssueStatus
    created_at: datetime
    updated_at: datetime


class AuditReportResponse(BaseModel):
    id: UUID
    title: str
    status: str
    summary: str
    findings: list[dict[str, Any]]
    generated_by: str
    created_at: datetime


class AuditReportInput(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    findings: list[dict[str, Any]] = Field(default_factory=list)
    generated_by: str = "Audit Report Agent"


class NotificationInput(BaseModel):
    issue_id: UUID
    message: str = Field(min_length=1)
    recipient: str = Field(min_length=1)


class NotificationResponse(BaseModel):
    id: UUID
    issue_id: UUID
    recipient: str
    message: str
    status: str
    sent_at: datetime


class AgentRunResponse(BaseModel):
    id: UUID
    thread_id: str
    question: str
    status: str
    current_agent: str | None = None
    agents_involved: list[str]
    trace_url: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class AssistantRequest(BaseModel):
    question: str = Field(min_length=10)

    regulation_document_id: UUID | None = None
    policy_document_id: UUID | None = None


class AssistantResponse(BaseModel):
    run: AgentRunResponse
    answer: str

    compliance_status: ComplianceStatus
    risk_level: RiskLevel

    evidence: list[Evidence]
    source_documents: list[DocumentResponse]

    agents_involved: list[str]


class DashboardResponse(BaseModel):
    compliance_score: float
    open_issues: int
    high_risk_issues: int
    documents_indexed: int
    completed_audits: int
    recent_runs: list[AgentRunResponse]