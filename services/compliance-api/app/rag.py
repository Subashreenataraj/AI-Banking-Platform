from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable
from sqlalchemy import text

from .config import get_settings
from .db import connection
from .ingestion import extract_text, normalize_text


def _embeddings() -> OpenAIEmbeddings:
    settings = get_settings()

    if not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required to index and retrieve documents."
        )

    return OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=settings.openai_api_key,
    )


@traceable(name="rag-index-document", run_type="chain")
def index_document(
    path: Path,
    document_id: UUID,
    document_name: str,
    category: str,
) -> int:

    content = normalize_text(extract_text(path))

    if not content:
        raise ValueError("The document did not contain extractable text.")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=180,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = splitter.split_text(content)

    embeddings = _embeddings()
    vectors = embeddings.embed_documents(chunks)

    with connection() as conn:

        # Remove old chunks if document is being re-indexed
        conn.execute(
            text(
                """
                DELETE FROM document_chunks
                WHERE document_id = :document_id
                """
            ),
            {"document_id": str(document_id)},
        )

        for index, (chunk, vector) in enumerate(zip(chunks, vectors)):

            conn.execute(
                text(
                    """
                    INSERT INTO document_chunks (
                        id,
                        document_id,
                        chunk_index,
                        content,
                        page_number,
                        embedding,
                        metadata
                    )
                    VALUES (
                        :id,
                        :document_id,
                        :chunk_index,
                        :content,
                        :page_number,
                        CAST(:embedding AS vector),
                        CAST(:metadata AS jsonb)
                    )
                    """
                ),
                {
                    "id": str(uuid4()),
                    "document_id": str(document_id),
                    "chunk_index": index,
                    "content": chunk,
                    "page_number": None,
                    "embedding": str(vector),
                    "metadata": (
                        '{"document_name": "'
                        + document_name.replace('"', '\\"')
                        + '", "category": "'
                        + category
                        + '"}'
                    ),
                },
            )

        conn.execute(
            text(
                """
                UPDATE documents
                SET
                    status = 'indexed',
                    chunk_count = :chunk_count,
                    indexed_at = now()
                WHERE id = :document_id
                """
            ),
            {
                "document_id": str(document_id),
                "chunk_count": len(chunks),
            },
        )

    return len(chunks)


@traceable(name="rag-retrieve-evidence", run_type="retriever")
def retrieve_evidence(
    query: str,
    *,
    document_ids: list[UUID] | None = None,
    category: str | None = None,
    k: int = 8,
) -> list[dict[str, Any]]:

    query_vector = _embeddings().embed_query(query)

    filters = []
    params: dict[str, Any] = {
        "query_embedding": str(query_vector),
        "limit": k,
    }

    if document_ids:
        placeholders = []

        for index, document_id in enumerate(document_ids):
            key = f"document_id_{index}"
            placeholders.append(f":{key}")
            params[key] = str(document_id)

        filters.append(
            f"dc.document_id IN ({', '.join(placeholders)})"
        )

    if category:
        filters.append("d.category = :category")
        params["category"] = category

    where_clause = ""

    if filters:
        where_clause = "WHERE " + " AND ".join(filters)

    sql = text(
        f"""
        SELECT
            dc.id,
            dc.document_id,
            dc.content,
            dc.page_number,
            d.name AS document_name,
            d.category,

            1 - (
                dc.embedding <=> CAST(:query_embedding AS vector)
            ) AS relevance_score

        FROM document_chunks dc

        JOIN documents d
            ON d.id = dc.document_id

        {where_clause}

        ORDER BY dc.embedding <=> CAST(:query_embedding AS vector)

        LIMIT :limit
        """
    )

    with connection() as conn:
        rows = conn.execute(sql, params).mappings().all()

    evidence = []

    for row in rows:

        score = float(row["relevance_score"])

        # Ignore weak matches
        if score < 0.30:
            continue

        evidence.append(
            {
                "chunk_id": str(row["id"]),
                "document_id": str(row["document_id"]),
                "document_name": row["document_name"],
                "page_number": row["page_number"],
                "excerpt": row["content"],
                "source_type": row["category"],
                "relevance_score": round(score, 4),
            }
        )

    return evidence


@traceable(name="rag-delete-document", run_type="chain")
def delete_document_embeddings(document_id: UUID) -> None:

    with connection() as conn:
        conn.execute(
            text(
                """
                DELETE FROM document_chunks
                WHERE document_id = :document_id
                """
            ),
            {"document_id": str(document_id)},
        )