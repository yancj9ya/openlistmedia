from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from backend.config.settings import FrontendConfig


class FrontendStaticMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, frontend: FrontendConfig) -> None:
        super().__init__(app)
        self.frontend = frontend

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method not in {"GET", "HEAD"}:
            return await call_next(request)
        if request.url.path.startswith("/api/"):
            return await call_next(request)

        response = await serve_frontend_file(request.url.path, self.frontend)
        if response is not None:
            return response
        return await call_next(request)


async def serve_frontend_file(
    request_path: str, frontend: FrontendConfig
) -> FileResponse | None:
    dist_dir = Path(frontend.dist_dir).resolve()
    if not dist_dir.exists() or not dist_dir.is_dir():
        return None

    normalized_path = request_path.strip() or "/"
    if normalized_path == "/":
        candidate = dist_dir / "index.html"
    else:
        candidate = (dist_dir / normalized_path.lstrip("/")).resolve()
        try:
            candidate.relative_to(dist_dir)
        except ValueError:
            return None
        if candidate.is_dir():
            candidate = candidate / "index.html"

    if not candidate.exists() or not candidate.is_file():
        candidate = dist_dir / "index.html"
        if not candidate.exists() or not candidate.is_file():
            return None

    return _file_response(candidate, dist_dir)


def _file_response(path: Path, dist_dir: Path) -> FileResponse:
    content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    headers = {"Cache-Control": "no-cache"}
    try:
        relative = path.resolve().relative_to(dist_dir)
        first_segment = relative.parts[0] if relative.parts else ""
    except ValueError:
        first_segment = ""
    if first_segment == "assets":
        headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return FileResponse(path, media_type=content_type, headers=headers)
