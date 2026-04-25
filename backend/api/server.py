from __future__ import annotations

import http.server
import json
import mimetypes
from pathlib import Path
import socketserver
import time
from urllib.parse import urlparse

from backend.dto.responses import RawResponse, error_response


class BackendHTTPRequestHandler(http.server.BaseHTTPRequestHandler):
    routes = None
    cors = None
    frontend = None

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        started = time.perf_counter()
        parsed = urlparse(self.path)
        self._log_request_start("GET", parsed.path, parsed.query)
        try:
            status, payload = self.routes.handle(
                parsed.path, parsed.query, self.headers
            )
        except Exception as exc:
            status, payload = error_response("internal_error", str(exc), 500)
            self._log_request_error("GET", parsed.path, exc)
        if isinstance(payload, RawResponse):
            self._send_raw(status, payload)
            self._log_request_done("GET", parsed.path, status, started)
            return
        if status == 404 and self._try_serve_frontend(parsed.path):
            self._log_request_done("GET", parsed.path, 200, started)
            return
        self._send_json(status, payload)
        self._log_request_done("GET", parsed.path, status, started)

    def do_POST(self) -> None:
        started = time.perf_counter()
        parsed = urlparse(self.path)
        self._log_request_start("POST", parsed.path, "")
        body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object.")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            status, response = error_response("bad_request", str(exc), 400)
            self._send_json(status, response)
            self._log_request_done("POST", parsed.path, status, started)
            return
        try:
            status, response = self.routes.handle_post(
                parsed.path, payload, self.headers
            )
        except Exception as exc:
            status, response = error_response("internal_error", str(exc), 500)
            self._log_request_error("POST", parsed.path, exc)
        self._send_json(status, response)
        self._log_request_done("POST", parsed.path, status, started)

    def log_message(self, format: str, *args) -> None:
        return

    def _log_request_start(self, method: str, path: str, query: str) -> None:
        query_text = f"?{query}" if query else ""
        print(f"[api] -> {method} {path}{query_text}")

    def _log_request_done(
        self, method: str, path: str, status: int, started: float
    ) -> None:
        elapsed_ms = (time.perf_counter() - started) * 1000
        print(f"[api] <- {method} {path} {status} {elapsed_ms:.1f}ms")

    def _log_request_error(self, method: str, path: str, exc: Exception) -> None:
        print(f"[api] !! {method} {path} failed: {exc}")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_raw(self, status: int, response: RawResponse) -> None:
        self.send_response(status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(response.body)

    def _send_cors_headers(self) -> None:
        cors = self.cors
        if not cors:
            return
        origin = self.headers.get("Origin", "").strip()
        allowed_origins = cors.allow_origins or []
        allow_origin: str | None = None
        if "*" in allowed_origins:
            allow_origin = "*"
        elif origin and origin in allowed_origins:
            allow_origin = origin
        if allow_origin is not None:
            self.send_header("Access-Control-Allow-Origin", allow_origin)
            if allow_origin != "*":
                self.send_header("Vary", "Origin")
        self.send_header(
            "Access-Control-Allow-Methods",
            ", ".join(cors.allow_methods or ["GET", "POST", "OPTIONS"]),
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            ", ".join(cors.allow_headers or ["Content-Type", "X-Admin-Token"]),
        )

    def _try_serve_frontend(self, path: str) -> bool:
        frontend = self.frontend
        if not frontend:
            return False
        dist_dir = Path(frontend.dist_dir).resolve()
        if not dist_dir.exists() or not dist_dir.is_dir():
            return False
        request_path = path.strip() or "/"
        if request_path.startswith("/api/"):
            return False
        if request_path == "/":
            candidate = dist_dir / "index.html"
        else:
            candidate = (dist_dir / request_path.lstrip("/")).resolve()
            try:
                candidate.relative_to(dist_dir)
            except ValueError:
                return False
            if candidate.is_dir():
                candidate = candidate / "index.html"
        if candidate.exists() and candidate.is_file():
            self._send_file(candidate, dist_dir)
            return True
        index_file = dist_dir / "index.html"
        if index_file.exists() and index_file.is_file():
            self._send_file(index_file, dist_dir)
            return True
        return False

    def _send_file(self, path: Path, dist_dir: Path) -> None:
        body = path.read_bytes()
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        try:
            relative = path.resolve().relative_to(dist_dir)
            first_segment = relative.parts[0] if relative.parts else ""
        except ValueError:
            first_segment = ""
        if first_segment == "assets":
            self.send_header(
                "Cache-Control", "public, max-age=31536000, immutable"
            )
        else:
            self.send_header("Cache-Control", "no-cache")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
