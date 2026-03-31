from __future__ import annotations

from backend.config.settings import MediaWallConfig, load_backend_config
from backend.repository import MediaWallDB
from backend.scanner.openlist_scanner import OpenListScanner
from backend.service import MediaWallService


MediaWallRepository = MediaWallService


def load_media_wall_config() -> MediaWallConfig:
    return load_backend_config().media_wall


__all__ = [
    "MediaWallConfig",
    "MediaWallDB",
    "MediaWallRepository",
    "OpenListScanner",
    "load_media_wall_config",
]
