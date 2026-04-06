from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.scheduler import validate_cron_expression
from config_loader import get_value, load_config as load_yaml_config


@dataclass
class CORSConfig:
    allow_origins: list[str]
    allow_methods: list[str]
    allow_headers: list[str]


@dataclass
class APIConfig:
    host: str
    port: int
    prefix: str
    admin_token: str | None
    cors: CORSConfig


@dataclass
class FrontendConfig:
    site_url: str
    dev_server_url: str
    dist_dir: str
    reverse_proxy_api_prefix: str


@dataclass
class MediaWallConfig:
    openlist_base_url: str
    openlist_token: str | None
    openlist_username: str | None
    openlist_password: str | None
    openlist_hash_login: bool
    media_root: str
    tmdb_read_access_token: str | None
    tmdb_api_key: str | None
    tmdb_language: str
    item_url_template: str | None
    list_retry_count: int
    retry_delay_seconds: float
    skip_failed_directories: bool
    database_path: Path
    cache_ttl_seconds: int
    refresh_cron: str | None
    skip_directories: list[str]


@dataclass
class BackendConfig:
    api: APIConfig
    frontend: FrontendConfig
    media_wall: MediaWallConfig


def load_backend_config() -> BackendConfig:
    config = load_yaml_config()
    admin_token = _env_or_config(
        "MEDIA_WALL_ADMIN_TOKEN", get_value(config, "backend", "admin_token")
    )
    return BackendConfig(
        api=APIConfig(
            host=_string_value(
                get_value(config, "backend", "host", default="127.0.0.1"), "127.0.0.1"
            ),
            port=int(
                get_value(
                    config,
                    "backend",
                    "port",
                    default=get_value(config, "media_wall", "port", default=8000),
                )
            ),
            prefix=_string_value(
                get_value(config, "backend", "api_prefix", default="/api/v1"), "/api/v1"
            ),
            admin_token=_optional_string(admin_token),
            cors=CORSConfig(
                allow_origins=_string_list(
                    _env_or_config(
                        "MEDIA_WALL_CORS_ALLOW_ORIGINS",
                        get_value(
                            config,
                            "backend",
                            "cors",
                            "allow_origins",
                            default=["http://127.0.0.1:5173"],
                        ),
                    )
                ),
                allow_methods=_string_list(
                    get_value(
                        config,
                        "backend",
                        "cors",
                        "allow_methods",
                        default=["GET", "POST", "OPTIONS"],
                    )
                ),
                allow_headers=_string_list(
                    get_value(
                        config,
                        "backend",
                        "cors",
                        "allow_headers",
                        default=["Content-Type", "X-Admin-Token"],
                    )
                ),
            ),
        ),
        frontend=FrontendConfig(
            site_url=_string_value(
                _env_or_config(
                    "MEDIA_WALL_FRONTEND_SITE_URL",
                    get_value(
                        config, "frontend", "site_url", default="http://127.0.0.1:5173"
                    ),
                ),
                "http://127.0.0.1:5173",
            ),
            dev_server_url=_string_value(
                get_value(
                    config,
                    "frontend",
                    "dev_server_url",
                    default="http://127.0.0.1:5173",
                ),
                "http://127.0.0.1:5173",
            ),
            dist_dir=_string_value(
                get_value(config, "frontend", "dist_dir", default="frontend/dist"),
                "frontend/dist",
            ),
            reverse_proxy_api_prefix=_string_value(
                get_value(
                    config, "frontend", "reverse_proxy_api_prefix", default="/api/v1"
                ),
                "/api/v1",
            ),
        ),
        media_wall=MediaWallConfig(
            openlist_base_url=_string_value(get_value(config, "openlist", "base_url")),
            openlist_token=_optional_string(
                _env_or_config("OPENLIST_TOKEN", get_value(config, "openlist", "token"))
            ),
            openlist_username=_optional_string(
                get_value(config, "openlist", "username")
            ),
            openlist_password=_optional_string(
                _env_or_config(
                    "OPENLIST_PASSWORD", get_value(config, "openlist", "password")
                )
            ),
            openlist_hash_login=bool(
                get_value(config, "openlist", "hash_login", default=False)
            ),
            media_root=_string_value(
                get_value(config, "media_wall", "media_root", default="/影视资源"),
                "/影视资源",
            ),
            tmdb_read_access_token=_optional_string(
                _env_or_config(
                    "TMDB_READ_ACCESS_TOKEN",
                    get_value(config, "tmdb", "read_access_token"),
                )
            ),
            tmdb_api_key=_optional_string(
                _env_or_config("TMDB_API_KEY", get_value(config, "tmdb", "api_key"))
            ),
            tmdb_language=_string_value(
                get_value(config, "tmdb", "language", default="zh-CN"), "zh-CN"
            ),
            item_url_template=_optional_string(
                get_value(config, "media_wall", "item_url_template")
            ),
            list_retry_count=int(
                get_value(config, "media_wall", "list_retry_count", default=2)
            ),
            retry_delay_seconds=float(
                get_value(config, "media_wall", "retry_delay_seconds", default=1.0)
            ),
            skip_failed_directories=bool(
                get_value(config, "media_wall", "skip_failed_directories", default=True)
            ),
            database_path=Path(
                _string_value(
                    get_value(
                        config, "media_wall", "database_path", default="media_wall.db"
                    ),
                    "media_wall.db",
                )
            ),
            cache_ttl_seconds=int(
                get_value(config, "media_wall", "cache_ttl_seconds", default=86400)
            ),
            refresh_cron=_validated_cron(
                get_value(config, "media_wall", "refresh_cron", default="")
            ),
            skip_directories=_string_list(
                get_value(config, "media_wall", "skip_directories", default=["热更"])
            ),
        ),
    )


def _env_or_config(env_name: str, value: Any) -> Any:
    env_value = os.environ.get(env_name)
    if env_value is None:
        return value
    return env_value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_value(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    normalized = text.replace("|", ",")
    if "," in normalized:
        return [item.strip() for item in normalized.split(",") if item.strip()]
    return [normalized]


def _validated_cron(value: Any) -> str | None:
    text = _optional_string(value)
    if not text:
        return None
    validate_cron_expression(text)
    return text
