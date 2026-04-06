from __future__ import annotations

from backend.api import BackendHTTPRequestHandler, ReusableTCPServer
from backend.api.routes import MediaRoutes
from backend.config import load_backend_config
from backend.scheduler import ScheduledRefreshRunner
from backend.service import MediaWallService


def create_backend_server() -> tuple[ReusableTCPServer, object, object, object]:
    config = load_backend_config()
    service = MediaWallService(config)
    scheduler = ScheduledRefreshRunner(service, config.media_wall.refresh_cron)
    routes = MediaRoutes(service, config.api.prefix, config.api.admin_token)
    handler = type("ConfiguredBackendHandler", (BackendHTTPRequestHandler,), {})
    handler.routes = routes
    handler.cors = config.api.cors
    handler.frontend = config.frontend
    server = ReusableTCPServer((config.api.host, config.api.port), handler)
    return server, config, service, scheduler
