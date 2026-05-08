from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.api.fastapi_routes import APIError, create_media_router
from backend.api.fastapi_static import FrontendStaticMiddleware
from backend.config import load_backend_config
from backend.config.settings import BackendConfig
from backend.dto.responses import error_response
from backend.scheduler import ScheduledRefreshRunner
from backend.service import MediaWallService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    service: MediaWallService = app.state.service
    scheduler: ScheduledRefreshRunner = app.state.scheduler
    service.ensure_initial_cache()
    scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()


def create_fastapi_app() -> FastAPI:
    config = load_backend_config()
    service = MediaWallService(config)
    scheduler = ScheduledRefreshRunner(service, config.media_wall.refresh_cron)

    app = FastAPI(title="OpenListMedia", lifespan=lifespan)
    app.state.config = config
    app.state.service = service
    app.state.scheduler = scheduler

    _register_config_reload_listener(service, scheduler)
    _register_exception_handlers(app)
    _register_cors(app, config)

    app.include_router(create_media_router(config.api.prefix))
    app.add_middleware(FrontendStaticMiddleware, frontend=config.frontend)
    return app


def _register_config_reload_listener(
    service: MediaWallService, scheduler: ScheduledRefreshRunner
) -> None:
    def on_config_reload(fresh: BackendConfig) -> None:
        scheduler.reload(fresh.media_wall.refresh_cron)

    service.register_config_listener(on_config_reload)


def _register_cors(app: FastAPI, config: BackendConfig) -> None:
    cors = config.api.cors
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors.allow_origins or [],
        allow_methods=cors.allow_methods or ["GET", "POST", "OPTIONS"],
        allow_headers=cors.allow_headers or ["Content-Type", "X-Admin-Token"],
    )


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(_request: Request, exc: APIError) -> JSONResponse:
        status, payload = error_response(
            exc.code,
            exc.message,
            exc.status_code,
            exc.details,
        )
        return JSONResponse(status_code=status, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        status, payload = error_response(
            "bad_request",
            "Invalid request parameters.",
            400,
            exc.errors(),
        )
        return JSONResponse(status_code=status, content=payload)

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        message = str(exc.detail or "Request failed.")
        status, payload = error_response(code, message, exc.status_code)
        return JSONResponse(status_code=status, content=payload)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        print(f"Unhandled API error: {exc}")
        status, payload = error_response("internal_error", "Internal server error.", 500)
        return JSONResponse(status_code=status, content=payload)


app = create_fastapi_app()
