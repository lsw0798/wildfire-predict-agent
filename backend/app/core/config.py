from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
DEFAULT_DATA_DIR = BACKEND_DIR / "data"
DEFAULT_PROCESSED_DATA_PATH = DEFAULT_DATA_DIR / "processed" / "incidents.json"
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://wildfire-predict-agent-lth9gx9oj-swzzangr7890-9379s-projects.vercel.app/"
]


def _resolve_project_path(value: str | Path) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()
    backend_candidate = (BACKEND_DIR / candidate).resolve()
    if backend_candidate.exists():
        return backend_candidate

    project_candidate = (PROJECT_DIR / candidate).resolve()
    if project_candidate.exists():
        return project_candidate

    return backend_candidate


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "Wildfire Agent Backend"
    app_version: str = "0.1.0"

    wildfire_api_base_url: str = "https://www.bigdata-forest.kr/todayFireGet"
    wildfire_api_key: str = ""
    kakao_rest_api_key: str = ""
    wildfire_data_dir: Path = Field(default=DEFAULT_DATA_DIR)
    wildfire_processed_data_path: Path = Field(default=DEFAULT_PROCESSED_DATA_PATH)
    backend_cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: DEFAULT_CORS_ORIGINS.copy()
    )
    group_e_enabled: bool = False
    group_e_model: str = "gpt-5.4"
    llm_provider: str = "openai"
    openai_api_key: str = ""

    @field_validator("wildfire_data_dir", "wildfire_processed_data_path", mode="before")
    @classmethod
    def _expand_path(cls, value: str | Path) -> Path:
        return _resolve_project_path(value)

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
