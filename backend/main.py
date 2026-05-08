from __future__ import annotations

import uvicorn

from backend.config import load_backend_config


def main() -> int:
    config = load_backend_config()
    print(
        f"Serving FastAPI backend at http://{config.api.host}:{config.api.port}{config.api.prefix}"
    )
    uvicorn.run(
        "backend.fastapi_app:app",
        host=config.api.host,
        port=config.api.port,
        factory=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
