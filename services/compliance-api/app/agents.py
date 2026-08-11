import json
from operator import add
from typing import Annotated, Any, Literal, TypedDict
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
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    rationale: str
    impact: str
    evidence: list[int] = Field(default_factory=list)


class AuditFinding(BaseModel):
    finding: str
    recommendation: str
    audit_summary: str
    evidence: list[int] = Field(default_factory=list)


class SupervisorDecision(BaseModel):
    workflow: Literal[
        "COMPLIANCE_COMPARISON",
        "REGULATION_ANALYSIS",
        "POLICY_ANALYSIS",
    ]
    reason: str


class ComplianceState(TypedDict, total=False):
    question: str
    regulation_document_id: UUID | None
    policy_document_id: UUID | None

    regulation_evidence: list[dict[str, Any]]
    policy_evidence: list[dict[str, Any]]
    evidence: list[dict[str, Any]]

    regulation: dict[str, Any]
    policy: dict[str, Any]
    risk: dict[str, Any]
    audit: dict[str, Any]

    workflow: str
    routing_reason: str

    agents_involved: Annotated[list[str], add]
    error: str | None


def _llm():
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required for compliance analysis."
        )

    return ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        max_retries=2,
    )


def _evidence_text(
    evidence: list[dict[str, Any]],
) -> str:

    if not evidence:
        return (
            "NO EVIDENCE FOUND. "
            "Do not infer or invent any requirement."
        )

    return "\n\n".join(
        f"[{index}] "
        f"{item.get('document_name', 'Unknown document')} "
        f"(Page {item.get('page_number') or 'N/A'})\n"
        f"{item.get('excerpt', '')}"
        for index, item in enumerate(evidence)
    )


@traceable(
    name="supervisor-agent",
    run_type="chain",
)
def supervisor_node(
    state: ComplianceState,
) -> dict[str, Any]:

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are the Supervisor Agent for a banking compliance platform.

Determine what type of analysis the user needs.

Use:
COMPLIANCE_COMPARISON when the user wants to compare
a regulation with an internal policy.

Use:
REGULATION_ANALYSIS when the user only wants to understand
a regulation.

Use:
POLICY_ANALYSIS when the user only wants to understand
an internal policy.

Do not perform the actual compliance analysis.
Only decide the workflow.
""",
            ),
            (
                "human",
                "User request:\n{question}",
            ),
        ]
    )

    result = (
        prompt
        | _llm().with_structured_output(SupervisorDecision)
    ).invoke(
        {
            "question": state["question"],
        }
    )

    return {
        "workflow": result.workflow,
        "routing_reason": result.reason,
        "agents_involved": ["Supervisor Agent"],
    }


def route_after_supervisor(
    state: ComplianceState,
) -> str:

    workflow = state.get(
        "workflow",
        "COMPLIANCE_COMPARISON",
    )

    if workflow == "REGULATION_ANALYSIS":
        return "regulation_analysis"

    if workflow == "POLICY_ANALYSIS":
        return "policy_verification"

    return "regulation_analysis"


@traceable(
    name="regulation-analysis-agent",
    run_type="chain",
)
def regulation_analysis_node(
    state: ComplianceState,
) -> dict[str, Any]:

    evidence = retrieve_evidence(
        state["question"],
        document_ids=(
            [state["regulation_document_id"]]
            if state.get("regulation_document_id")
            else None
        ),
        category="regulation",
        k=8,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are the Regulation Analysis Agent.

Analyze ONLY the supplied regulatory evidence.

Identify the actual regulatory requirement.

If the evidence does not establish the requirement:
- set verifiable=false
- do not guess
- clearly state that it cannot be verified.

Return the indexes of supporting evidence.
""",
            ),
            (
                "human",
                """
Question:
{question}

Regulatory Evidence:
{evidence}
""",
            ),
        ]
    )

    result = (
        prompt
        | _llm().with_structured_output(
            RegulationAnalysis
        )
    ).invoke(
        {
            "question": state["question"],
            "evidence": _evidence_text(evidence),
        }
    )

    return {
        "regulation": result.model_dump(),
        "regulation_evidence": evidence,
        "evidence": evidence,
        "agents_involved": [
            "Regulation Analysis Agent"
        ],
    }


@traceable(
    name="policy-verification-agent",
    run_type="chain",
)
def policy_verification_node(
    state: ComplianceState,
) -> dict[str, Any]:

    regulation = state.get(
        "regulation",
        {},
    )

    policy_query = (
        state["question"]
        + "\nRegulatory requirement: "
        + regulation.get(
            "requirement",
            "",
        )
    )

    evidence = retrieve_evidence(
        policy_query,
        document_ids=(
            [state["policy_document_id"]]
            if state.get("policy_document_id")
            else None
        ),
        category="policy",
        k=8,
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are the Policy Verification Agent.

Compare the regulatory requirement with
the supplied internal policy evidence.

Never claim that a policy covers a requirement
without supporting evidence.

Possible compliance statuses:
COMPLIANT
PARTIALLY_COMPLIANT
NON_COMPLIANT
UNVERIFIED

Return supporting evidence indexes.
""",
            ),
            (
                "human",
                """
Question:
{question}

Regulation:
{regulation}

Policy Evidence:
{evidence}
""",
            ),
        ]
    )

    result = (
        prompt
        | _llm().with_structured_output(
            PolicyVerification
        )
    ).invoke(
        {
            "question": state["question"],
            "regulation": json.dumps(
                regulation
            ),
            "evidence": _evidence_text(evidence),
        }
    )

    combined_evidence = (
        state.get("regulation_evidence", [])
        + evidence
    )

    return {
        "policy": result.model_dump(),
        "policy_evidence": evidence,
        "evidence": combined_evidence,
        "agents_involved": [
            "Policy Verification Agent"
        ],
    }


@traceable(
    name="risk-assessment-agent",
    run_type="chain",
)
def risk_assessment_node(
    state: ComplianceState,
) -> dict[str, Any]:

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are the Risk Assessment Agent for banking compliance.

Assess the seriousness of the identified compliance gap.

Use ONLY the supplied regulation analysis,
policy verification and evidence.

Assign exactly:
LOW, MEDIUM, HIGH, or CRITICAL.

Do not invent facts.
Return supporting evidence indexes.
""",
            ),
            (
                "human",
                """
Question:
{question}

Regulation:
{regulation}

Policy:
{policy}

Evidence:
{evidence}
""",
            ),
        ]
    )

    result = (
        prompt
        | _llm().with_structured_output(
            RiskAssessment
        )
    ).invoke(
        {
            "question": state["question"],
            "regulation": json.dumps(
                state.get("regulation", {})
            ),
            "policy": json.dumps(
                state.get("policy", {})
            ),
            "evidence": _evidence_text(
                state.get("evidence", [])
            ),
        }
    )

    return {
        "risk": result.model_dump(),
        "agents_involved": [
            "Risk Assessment Agent"
        ],
    }


@traceable(
    name="audit-report-agent",
    run_type="chain",
)
def audit_report_node(
    state: ComplianceState,
) -> dict[str, Any]:

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
You are the Audit Report Agent.

Create a concise structured compliance finding
and recommendation.

Use only the supplied analysis and evidence.

If the requirement cannot be verified,
clearly state that it cannot be verified.

Return evidence indexes.
""",
            ),
            (
                "human",
                """
Question:
{question}

Regulation:
{regulation}

Policy:
{policy}

Risk:
{risk}

Evidence:
{evidence}
""",
            ),
        ]
    )

    result = (
        prompt
        | _llm().with_structured_output(
            AuditFinding
        )
    ).invoke(
        {
            "question": state["question"],
            "regulation": json.dumps(
                state.get("regulation", {})
            ),
            "policy": json.dumps(
                state.get("policy", {})
            ),
            "risk": json.dumps(
                state.get("risk", {})
            ),
            "evidence": _evidence_text(
                state.get("evidence", [])
            ),
        }
    )

    return {
        "audit": result.model_dump(),
        "agents_involved": [
            "Audit Report Agent"
        ],
    }


def build_graph():

    graph = StateGraph(
        ComplianceState
    )

    graph.add_node(
        "supervisor",
        supervisor_node,
    )

    graph.add_node(
        "regulation_analysis",
        regulation_analysis_node,
    )

    graph.add_node(
        "policy_verification",
        policy_verification_node,
    )

    graph.add_node(
        "risk_assessment",
        risk_assessment_node,
    )

    graph.add_node(
        "audit_report",
        audit_report_node,
    )

    graph.set_entry_point(
        "supervisor"
    )

    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {
            "regulation_analysis":
                "regulation_analysis",

            "policy_verification":
                "policy_verification",
        },
    )

    graph.add_edge(
        "regulation_analysis",
        "policy_verification",
    )

    graph.add_edge(
        "policy_verification",
        "risk_assessment",
    )

    graph.add_edge(
        "risk_assessment",
        "audit_report",
    )

    graph.add_edge(
        "audit_report",
        END,
    )

    return graph.compile()


workflow = build_graph()


@traceable(
    name="run-compliance-workflow",
    run_type="chain",
)
def run_compliance_workflow(
    question: str,
    *,
    regulation_document_id: UUID | None = None,
    policy_document_id: UUID | None = None,
) -> dict[str, Any]:

    if not regulation_document_id:
        raise ValueError(
            "A regulation document must be selected."
        )

    if not policy_document_id:
        raise ValueError(
            "A policy document must be selected."
        )

    result = workflow.invoke(
        {
            "question": question,
            "regulation_document_id":
                regulation_document_id,
            "policy_document_id":
                policy_document_id,
            "agents_involved": [],
        },
        config={
            "run_id": uuid4()
        },
    )

    return result