from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.2"

    langchain_api_key: str | None = None
    langchain_tracing_v2: bool = False
    langchain_project: str = "ai-banking-compliance"

    supabase_url: str | None = None
    supabase_key: str | None = None

    upload_directory: str = "./data/uploads"

    allowed_origins: str = (
        "http://localhost:3000,http://localhost:5173"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.allowed_origins.split(",")
            if origin.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()