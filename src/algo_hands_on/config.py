from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Configuração central carregada de ambiente e `.env`."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")

    db_path: Path = Field(default=PROJECT_ROOT / "data" / "aho.db", alias="AHO_DB_PATH")
    skills_dir: Path = Field(default=PROJECT_ROOT / "skills", alias="AHO_SKILLS_DIR")

    host: str = Field(default="127.0.0.1", alias="AHO_HOST")
    port: int = Field(default=7777, alias="AHO_PORT", ge=1, le=65535)
    reload: bool = Field(default=False, alias="AHO_RELOAD")

    history_runs: int = Field(default=3, alias="AHO_HISTORY_RUNS", ge=1, le=30)
    session_summaries: bool = Field(default=True, alias="AHO_SESSION_SUMMARIES")
    memory: bool = Field(default=True, alias="AHO_MEMORY")
    stream: bool = Field(default=True, alias="AHO_STREAM")
    stream_events: bool = Field(default=True, alias="AHO_STREAM_EVENTS")
    debug: bool = Field(default=False, alias="AHO_DEBUG")
    telemetry: bool = Field(default=False, alias="AHO_TELEMETRY")
    log_level: str = Field(default="INFO", alias="AHO_LOG_LEVEL")

    @field_validator("db_path", "skills_dir", mode="before")
    @classmethod
    def resolve_path(cls, value: str | Path) -> Path:
        path = Path(value).expanduser()
        return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()

    def prepare_runtime(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def validate_runtime(self) -> list[str]:
        errors: list[str] = []
        if not self.deepseek_api_key or self.deepseek_api_key == "coloque_sua_chave_aqui":
            errors.append("DEEPSEEK_API_KEY não foi configurada.")
        if not self.skills_dir.exists():
            errors.append(f"Diretório de skills não existe: {self.skills_dir}")
        return errors


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.prepare_runtime()
    return settings
