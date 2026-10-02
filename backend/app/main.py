import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.assistant import router as assistant_router
from app.api.routes.auth import router as auth_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.extraction import router as extraction_router
from app.api.routes.health import router as health_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.personal_tasks import router as personal_tasks_router
from app.api.routes.shell import router as shell_router
from app.api.routes.sync import router as sync_router
from app.core.config import get_settings
from app.core.exceptions import unhandled_exception_handler
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.getLogger(__name__).info("application_started env=%s", settings.app_env)
    yield
    logging.getLogger(__name__).info("application_stopped")


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    application = FastAPI(title="Academic Assistant API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "X-CSRF-Token"],
    )
    application.add_exception_handler(Exception, unhandled_exception_handler)

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    application.include_router(health_router)
    application.include_router(auth_router)
    application.include_router(assistant_router)
    application.include_router(sync_router)
    application.include_router(shell_router)
    application.include_router(extraction_router)
    application.include_router(dashboard_router)
    application.include_router(notifications_router)
    application.include_router(personal_tasks_router)
    return application


app = create_app()
