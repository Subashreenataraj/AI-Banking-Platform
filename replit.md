# AI Banking Regulatory Compliance & Audit Intelligence Platform

Grounded regulatory analysis, policy verification, risk assessment, and audit intelligence for banking compliance teams.

## Run & Operate

- `pnpm --filter @workspace/api-server run dev` — run the API server (port 5000)
- `python services/compliance-api/run.py` — run the Python compliance API (port 8000)
- `pnpm run typecheck` — full typecheck across all packages
- `pnpm run build` — typecheck + build all packages
- `pnpm --filter @workspace/api-spec run codegen` — regenerate API hooks and Zod schemas from the OpenAPI spec
- `pnpm --filter @workspace/db run push` — push DB schema changes (dev only)
- Required env: `DATABASE_URL` — Postgres connection string
- Python provider env: `OPENAI_API_KEY`, `LANGCHAIN_API_KEY`, `LANGCHAIN_TRACING_V2`, and `LANGCHAIN_PROJECT`

## Stack

- pnpm workspaces, Node.js 24, TypeScript 5.9
- API: Express 5
- DB: PostgreSQL + Drizzle ORM
- Validation: Zod (`zod/v4`), `drizzle-zod`
- API codegen: Orval (from OpenAPI spec)
- Build: esbuild (CJS bundle)

## Where things live

- `services/compliance-api/app/` — FastAPI service, PostgreSQL migrations, document ingestion, Chroma RAG, LangGraph agents, OpenAPI tools, and LangSmith configuration.
- `lib/api-spec/openapi.yaml` — source of truth for the browser-facing API contract.
- `services/compliance-api/data/` — local persistent upload and Chroma index data.

## Architecture decisions

- PostgreSQL stores queryable application metadata and workflow history; document bytes and the Chroma index remain in the service data directory until managed object storage is available.
- Compliance answers are grounded in retrieved chunks and return source excerpts; missing evidence produces an explicit unverified result rather than an inferred answer.
- The supervisor graph executes specialized agents in sequence so every run records the actual participants and structured intermediate outputs.

## Product

- Upload and index regulatory and internal policy documents.
- Run evidence-backed compliance analysis through a LangGraph multi-agent workflow.
- Review live dashboard metrics, issues, reports, document status, and agent activity.

## User preferences

- Implement the project sequentially and verify each phase before moving to the next.
- Do not use mocked retrieval or fake agent responses.

## Gotchas

- The managed AI integration and App Storage provisioning were unavailable in this environment; the application uses the user-managed OpenAI/LangSmith secrets and local durable Chroma/file persistence.
- Run the Python API with its environment loaded; the frontend should access it through the `/api` proxy path.

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
