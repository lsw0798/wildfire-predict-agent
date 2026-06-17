from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.analyze import router as analyze_router
from app.api.routes.monitoring import router as monitoring_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(title=settings.app_name, version=settings.app_version)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(analyze_router, prefix="/api", tags=["analyze"])
    application.include_router(monitoring_router, prefix="/api", tags=["monitoring"])

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
