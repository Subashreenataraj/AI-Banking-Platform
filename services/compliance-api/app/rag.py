from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable

from .config import get_settings
from .ingestion import extract_text, normalize_text


def _embeddings() -> OpenAIEmbeddings:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required to index and retrieve documents.")
    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=settings.openai_api_key,
    )


def _store() -> Chroma:
    settings = get_settings()
    Path(settings.chroma_persist_directory).mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name="banking-compliance",
        embedding_function=_embeddings(),
        persist_directory=settings.chroma_persist_directory,
    )


@traceable(name="rag-index-document", run_type="chain")
def index_document(
    path: Path,
    document_id: UUID,
    document_name: str,
    category: str,
) -> int:
    text = normalize_text(extract_text(path))
    if not text:
        raise ValueError("The document did not contain extractable text.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=180,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.create_documents(
        [text],
        metadatas=[
            {
                "document_id": str(document_id),
                "document_name": document_name,
                "category": category,
                "source": document_name,
            }
        ],
    )
    ids = [f"{document_id}:{index}" for index in range(len(chunks))]
    _store().add_documents(chunks, ids=ids)
    return len(chunks)


@traceable(name="rag-retrieve-evidence", run_type="retriever")
def retrieve_evidence(
    query: str,
    *,
    document_ids: list[UUID] | None = None,
    category: str | None = None,
    k: int = 8,
) -> list[dict[str, Any]]:
    filters: dict[str, Any] | None = None
    clauses: list[dict[str, Any]] = []
    if document_ids:
        clauses.append({"document_id": {"$in": [str(item) for item in document_ids]}})
    if category:
        clauses.append({"category": category})
    if clauses:
        filters = clauses[0] if len(clauses) == 1 else {"$and": clauses}

    results = _store().similarity_search_with_relevance_scores(
        query,
        k=k,
        filter=filters,
    )
    evidence: list[dict[str, Any]] = []
    for document, score in results:
        evidence.append(
            {
                "document_id": document.metadata.get("document_id"),
                "document_name": document.metadata.get("document_name", "Unknown document"),
                "excerpt": document.page_content,
                "source_type": "indexed_document",
                "relevance_score": round(float(score), 4),
            }
        )
    return evidence


@traceable(name="rag-delete-document", run_type="chain")
def delete_document_embeddings(document_id: UUID) -> None:
    """Remove all vector chunks belonging to a deleted source document."""
    _store().delete(where={"document_id": str(document_id)})