from __future__ import annotations

from backend.main import main as backend_main


def main() -> int:
    print(
        "serve_media_wall.py 已降级为兼容入口，请优先使用 backend/main.py 启动独立后端 API 服务。"
    )
    return backend_main()


if __name__ == "__main__":
    raise SystemExit(main())
