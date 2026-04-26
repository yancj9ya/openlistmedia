from __future__ import annotations

from backend.app import create_backend_server


def main() -> int:
    server, config, service, scheduler = create_backend_server()
    print(
        f"Serving backend API at http://{config.api.host}:{config.api.port}{config.api.prefix}"
    )
    service.ensure_initial_cache()
    scheduler.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        scheduler.stop()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
