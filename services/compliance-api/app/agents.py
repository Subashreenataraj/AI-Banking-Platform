import json
from operator import add
from typing import Annotated, Any, TypedDict
from uuid import UUID, uuid4

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langsmith import traceable
from pydantic import BaseModel, Field

from .config import get_settings
from .rag import retrieve_evidence


class RegulationAnalysis(BaseModel):
    requirement: str
    regulatory_context: str
    evidence: list[int] = Field(default_factory=list)
    verifiable: bool


class PolicyVerification(BaseModel):
    policy_coverage: str
    gaps: list[str] = Field(default_factory=list)
    evidence: list[int] = Field(default_factory=list)
    compliance_status: str


class RiskAssessment(BaseModel):
    risk_level: str
    rationale: str
    impact: str
    evidence: list[int] = Field(default_factory=list)


class AuditFinding(BaseModel):
    finding: str
    recommendation: str
    audit_summary: str
    evidence: list[int] = Field(default_factory=list)


class ComplianceState(TypedDict, total=False):
    question: str
    regulation_document_id: UUID | None
    policy_document_id: UUID | None
    evidence: list[dict[str, Any]]
    regulation: dict[str, Any]
    policy: dict[str, Any]
    risk: dict[str, Any]
    audit: dict[str, Any]
    agents_involved: Annotated[list[str], add]
    error: str | None


def _llm():
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required for compliance analysis.")
    return ChatOpenAI(
        model="gpt-5.2",
        api_key=settings.openai_api_key,
        max_retries=2,
    )


def _evidence_text(evidence: list[dict[str, Any]]) -> str:
    if not evidence:
        return "NO EVIDENCE FOUND. Do not infer or invent a requirement."
    return "\n\n".join(
        f"[{index}] {item['document_name']}\n{item['excerpt']}"
        for index, item in enumerate(evidence)
    )


@traceable(name="regulation-analysis-agent", run_type="chain")
def regulation_analysis_node(state: ComplianceState) -> dict[str, Any]:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Regulation Analysis Agent for a bank. Analyze only the "
                "retrieved evidence. If the evidence does not establish the answer, "
                "set verifiable=false and say so. Return evidence indexes.",
            ),
            (
                "human",
                "Question: {question}\n\nRetrieved evidence:\n{evidence}",
            ),
        ]
    )
    result = (prompt | _llm().with_structured_output(RegulationAnalysis)).invoke(
        {"question": state["question"], "evidence": _evidence_text(state["evidence"])}
    )
    return {
        "regulation": result.model_dump(),
        "agents_involved": ["Regulation Analysis Agent"],
    }


@traceable(name="policy-verification-agent", run_type="chain")
def policy_verification_node(state: ComplianceState) -> dict[str, Any]:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Policy Verification Agent. Compare the regulatory "
                "requirement with internal policy evidence. Never claim coverage "
                "without evidence. Return evidence indexes.",
            ),
            (
                "human",
                "Question: {question}\nRegulation analysis: {regulation}\n\nEvidence:\n{evidence}",
            ),
        ]
    )
    result = (prompt | _llm().with_structured_output(PolicyVerification)).invoke(
        {
            "question": state["question"],
            "regulation": json.dumps(state["regulation"]),
            "evidence": _evidence_text(state["evidence"]),
        }
    )
    return {
        "policy": result.model_dump(),
        "agents_involved": ["Policy Verification Agent"],
    }


@traceable(name="risk-assessment-agent", run_type="chain")
def risk_assessment_node(state: ComplianceState) -> dict[str, Any]:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Risk Assessment Agent for banking compliance. Assign "
                "exactly one of LOW, MEDIUM, HIGH, or CRITICAL. Use only the provided "
                "analysis and evidence. Return evidence indexes.",
            ),
            (
                "human",
                "Question: {question}\nRegulation: {regulation}\nPolicy: {policy}\nEvidence:\n{evidence}",
            ),
        ]
    )
    result = (prompt | _llm().with_structured_output(RiskAssessment)).invoke(
        {
            "question": state["question"],
            "regulation": json.dumps(state["regulation"]),
            "policy": json.dumps(state["policy"]),
            "evidence": _evidence_text(state["evidence"]),
        }
    )
    risk = result.model_dump()
    if risk["risk_level"] not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        risk["risk_level"] = "HIGH"
    return {"risk": risk, "agents_involved": ["Risk Assessment Agent"]}


@traceable(name="audit-report-agent", run_type="chain")
def audit_report_node(state: ComplianceState) -> dict[str, Any]:
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are the Audit Report Agent. Produce a structured, concise "
                "audit finding and recommendation. If evidence is missing, clearly "
                "state that the requirement cannot be verified. Return evidence indexes.",
            ),
            (
                "human",
                "Question: {question}\nRegulation: {regulation}\nPolicy: {policy}\n"
                "Risk: {risk}\nEvidence:\n{evidence}",
            ),
        ]
    )
    result = (prompt | _llm().with_structured_output(AuditFinding)).invoke(
        {
            "question": state["question"],
            "regulation": json.dumps(state["regulation"]),
            "policy": json.dumps(state["policy"]),
            "risk": json.dumps(state["risk"]),
            "evidence": _evidence_text(state["evidence"]),
        }
    )
    return {"audit": result.model_dump(), "agents_involved": ["Audit Report Agent"]}


@traceable(name="supervisor-route", run_type="chain")
def supervisor_node(state: ComplianceState) -> dict[str, Any]:
    return {"agents_involved": ["Supervisor Agent"]}


def build_graph():
    graph = StateGraph(ComplianceState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("regulation_analysis", regulation_analysis_node)
    graph.add_node("policy_verification", policy_verification_node)
    graph.add_node("risk_assessment", risk_assessment_node)
    graph.add_node("audit_report", audit_report_node)
    graph.set_entry_point("supervisor")
    graph.add_edge("supervisor", "regulation_analysis")
    graph.add_edge("regulation_analysis", "policy_verification")
    graph.add_edge("policy_verification", "risk_assessment")
    graph.add_edge("risk_assessment", "audit_report")
    graph.add_edge("audit_report", END)
    return graph.compile()


workflow = build_graph()


@traceable(name="run-compliance-workflow", run_type="chain")
def run_compliance_workflow(
    question: str,
    *,
    regulation_document_id: UUID | None = None,
    policy_document_id: UUID | None = None,
) -> dict[str, Any]:
    ids = [item for item in [regulation_document_id, policy_document_id] if item]
    evidence = retrieve_evidence(question, document_ids=ids or None, k=8)
    result = workflow.invoke(
        {
            "question": question,
            "regulation_document_id": regulation_document_id,
            "policy_document_id": policy_document_id,
            "evidence": evidence,
            "agents_involved": [],
        },
        config={"run_id": uuid4()},
    )
    return result