from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    database_url: str = "sqlite:///./backend/data/interviews.sqlite"
    vector_db_path: str = "./backend/data/vector_store.sqlite"
    frontend_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    interview_question_limit: int = Field(default=5, ge=3, le=10)
    pdf_download_timeout: int = Field(default=35, ge=5, le=120)

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    @property
    def resolved_vector_db_path(self) -> Path:
        path = Path(self.vector_db_path)
        return path if path.is_absolute() else ROOT_DIR / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
