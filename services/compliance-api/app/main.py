from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import run_migrations
from .observability import configure_langsmith
from .routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_langsmith()
    run_migrations()
    yield


app = FastAPI(
    title="AI Banking Regulatory Compliance & Audit Intelligence Platform",
    version="1.0.0",
    description=(
        "Grounded regulatory analysis, policy verification, "
        "risk assessment, and audit intelligence."
    ),
    lifespan=lifespan,
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    router,
    prefix="/api",
)