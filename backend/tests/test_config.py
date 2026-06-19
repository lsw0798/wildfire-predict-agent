from pathlib import Path

from app.main import app
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings


PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_settings_defaults_match_project_layout(monkeypatch):
    monkeypatch.delenv("WILDFIRE_API_BASE_URL", raising=False)
    monkeypatch.delenv("WILDFIRE_API_KEY", raising=False)
    monkeypatch.delenv("WILDFIRE_DATA_DIR", raising=False)
    monkeypatch.delenv("WILDFIRE_PROCESSED_DATA_PATH", raising=False)
    monkeypatch.delenv("BACKEND_CORS_ORIGINS", raising=False)

    settings = Settings(_env_file=None)

    assert settings.wildfire_api_base_url == "https://www.bigdata-forest.kr/todayFireGet"
    assert settings.wildfire_api_key == ""
    assert settings.wildfire_data_dir == PROJECT_DIR / "data"
    assert settings.wildfire_processed_data_path == PROJECT_DIR / "data" / "processed" / "incidents.json"
    assert settings.backend_cors_origins[:2] == ["http://localhost:3000", "http://127.0.0.1:3000"]
    assert any("vercel.app" in origin for origin in settings.backend_cors_origins)
    assert settings.group_e_enabled is False
    assert settings.group_e_model == "gpt-5.4"
    assert settings.llm_provider == "openai"
    assert settings.openai_api_key == ""


def test_settings_read_env_overrides(monkeypatch, tmp_path):
    data_dir = tmp_path / "wildfire-data"
    processed_path = data_dir / "processed" / "custom.json"

    monkeypatch.setenv("WILDFIRE_API_BASE_URL", "https://example.com/wildfire")
    monkeypatch.setenv("WILDFIRE_API_KEY", "secret-key")
    monkeypatch.setenv("WILDFIRE_DATA_DIR", str(data_dir))
    monkeypatch.setenv("WILDFIRE_PROCESSED_DATA_PATH", str(processed_path))
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "http://localhost:3000,https://service.example.com")
    monkeypatch.setenv("GROUP_E_ENABLED", "true")
    monkeypatch.setenv("GROUP_E_MODEL", "gpt-5.4")
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "llm-secret")

    settings = Settings(_env_file=None)

    assert settings.wildfire_api_base_url == "https://example.com/wildfire"
    assert settings.wildfire_api_key == "secret-key"
    assert settings.wildfire_data_dir == data_dir
    assert settings.wildfire_processed_data_path == processed_path
    assert settings.backend_cors_origins == [
        "http://localhost:3000",
        "https://service.example.com",
    ]
    assert settings.group_e_enabled is True
    assert settings.group_e_model == "gpt-5.4"
    assert settings.llm_provider == "openai"
    assert settings.openai_api_key == "llm-secret"


def test_app_registers_cors_middleware():
    cors_layers = [middleware for middleware in app.user_middleware if middleware.cls is CORSMiddleware]

    assert cors_layers, "CORS middleware should be registered on the FastAPI app"
    assert cors_layers[0].kwargs["allow_origins"] == [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    assert cors_layers[0].kwargs["allow_credentials"] is True
    assert cors_layers[0].kwargs["allow_methods"] == ["*"]
    assert cors_layers[0].kwargs["allow_headers"] == ["*"]
