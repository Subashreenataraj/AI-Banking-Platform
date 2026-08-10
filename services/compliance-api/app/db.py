from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import get_settings


def get_engine() -> Engine:
    database_url = get_settings().database_url
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
    elif database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return create_engine(database_url, pool_pre_ping=True)


engine = get_engine()


@contextmanager
def connection() -> Generator:
    with engine.begin() as conn:
        yield conn


def run_migrations() -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS documents (
            id UUID PRIMARY KEY,
            name TEXT NOT NULL,
            document_type TEXT NOT NULL,
            category TEXT NOT NULL,
            source_path TEXT NOT NULL,
            content_hash TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'uploaded',
            chunk_count INTEGER NOT NULL DEFAULT 0,
            is_synthetic BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            indexed_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS compliance_issues (
            id UUID PRIMARY KEY,
            finding TEXT NOT NULL,
            regulation TEXT NOT NULL,
            risk TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            recommendation TEXT NOT NULL,
            evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
            source_document_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS audit_reports (
            id UUID PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'COMPLETED',
            summary TEXT NOT NULL,
            findings JSONB NOT NULL DEFAULT '[]'::jsonb,
            generated_by TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS agent_runs (
            id UUID PRIMARY KEY,
            thread_id TEXT NOT NULL,
            question TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'RUNNING',
            current_agent TEXT,
            agents_involved JSONB NOT NULL DEFAULT '[]'::jsonb,
            trace_url TEXT,
            result JSONB,
            error TEXT,
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            completed_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS compliance_notifications (
            id UUID PRIMARY KEY,
            issue_id UUID NOT NULL REFERENCES compliance_issues(id) ON DELETE CASCADE,
            recipient TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'SENT',
            sent_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS documents_status_idx ON documents(status)
        """,
        """
        CREATE INDEX IF NOT EXISTS compliance_issues_risk_idx ON compliance_issues(risk)
        """,
        """
        CREATE INDEX IF NOT EXISTS agent_runs_started_at_idx ON agent_runs(started_at DESC)
        """,
    ]
    with connection() as conn:
        for statement in statements:
            conn.execute(text(statement))