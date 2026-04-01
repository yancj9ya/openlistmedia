from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import PurePosixPath
from typing import Any

from openlist_sdk import OpenListClient
from openlist_sdk.exceptions import OpenListAPIError, OpenListHTTPError

from backend.config.settings import BackendConfig
from backend.repository import MediaQueryOptions, MediaWallDB
from backend.scanner import OpenListScanner
from config_loader import load_config, save_config


class MediaWallService:
    def __init__(self, config: BackendConfig) -> None:
        self.config = config
        self.db = MediaWallDB(config.media_wall.database_path)
        self.scanner = OpenListScanner(config.media_wall)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "api_prefix": self.config.api.prefix,
            "media_root": self.config.media_wall.media_root,
            "database_path": str(self.db.path),
        }

    def get_category_tree(self, category_path: str | None = None) -> dict[str, Any]:
        payload = self.scanner.list_categories(
            category_path or self.config.media_wall.media_root
        )
        payload["root"] = self.config.media_wall.media_root
        payload["skip_directories"] = self.config.media_wall.skip_directories
        payload["children"] = [
            self._to_category_node(entry) for entry in payload.get("entries", [])
        ]
        return payload

    def get_settings(self) -> dict[str, Any]:
        return load_config()

    def authenticate_access(self, passcode: str) -> dict[str, Any] | None:
        config = load_config()
        frontend = config.get("frontend") or {}
        admin_passcode = str(frontend.get("admin_passcode") or "admin").strip()
        visitor_passcode = str(frontend.get("visitor_passcode") or "yancj").strip()
        if passcode == admin_passcode:
            return {"role": "admin"}
        if passcode == visitor_passcode:
            return {"role": "visitor"}
        return None

    def is_admin_passcode(self, passcode: str | None) -> bool:
        if not passcode:
            return False
        config = load_config()
        frontend = config.get("frontend") or {}
        admin_passcode = str(frontend.get("admin_passcode") or "admin").strip()
        return bool(admin_passcode) and str(passcode).strip() == admin_passcode

    def update_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = load_config()
        previous_skip_directories = self._normalize_skip_directories(
            ((current.get("media_wall") or {}).get("skip_directories"))
        )
        merged = self._deep_merge(current, payload)

        media_wall = merged.get("media_wall") or {}
        normalized_skip_directories = self._normalize_skip_directories(
            media_wall.get("skip_directories")
        )
        media_wall["skip_directories"] = normalized_skip_directories
        merged["media_wall"] = media_wall

        save_config(merged)

        self.config.media_wall.skip_directories = normalized_skip_directories
        self.scanner.config.skip_directories = normalized_skip_directories

        if normalized_skip_directories != previous_skip_directories:
            self.db.clear_all_cache()

        return merged

    def _restart_process(self) -> None:
        time.sleep(0.5)
        os.execv(sys.executable, [sys.executable, "-m", "backend.main"])

    def restart_backend(self) -> dict[str, Any]:
        threading.Thread(target=self._restart_process, daemon=True).start()
        return {"restart_requested": True}

    def get_media_list(
        self,
        category_path: str | None,
        include_descendants: bool,
        year: int | None,
        page: int,
        page_size: int,
        keyword: str | None,
        media_type: str | None,
        sort_by: str,
        sort_order: str,
    ) -> dict[str, Any]:
        normalized_path = self._normalize_optional_path(category_path)
        if normalized_path and not self.db.cache_is_fresh(
            normalized_path, self.config.media_wall.cache_ttl_seconds
        ):
            self.refresh_category(normalized_path)
        query_result = self.db.query_media_items(
            MediaQueryOptions(
                category_path=normalized_path,
                include_descendants=include_descendants,
                year=year,
                page=page,
                page_size=page_size,
                keyword=keyword,
                media_type=media_type,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        )
        return {
            "items": query_result.items,
            "total": query_result.total,
            "page": query_result.page,
            "page_size": query_result.page_size,
            "years": self.db.list_available_years(
                normalized_path, include_descendants=include_descendants
            ),
        }

    def get_media_detail(self, media_id: int) -> dict[str, Any] | None:
        item = self.db.get_media_item(media_id)
        if item is None:
            return None
        files = []
        for file_item in item.get("files") or []:
            files.append(
                {
                    **file_item,
                    "playable_url": None,
                }
            )
        item["files"] = files
        item["playable_url"] = None
        return item

    def get_play_link(self, path: str) -> dict[str, Any]:
        playable_url = self.resolve_download_url(path)
        return {
            "path": OpenListScanner.normalize_path(path),
            "playable_url": playable_url,
        }

    def resolve_download_url(self, path: str) -> str | None:
        normalized_path = OpenListScanner.normalize_path(path)
        resolved_path, payload = self._get_fs_info_with_refresh(normalized_path)
        return self._build_download_url_from_payload(resolved_path, payload)

    def refresh_category(
        self, category_path: str, *, force_remote_refresh: bool = False
    ) -> dict[str, Any]:
        normalized_path = OpenListScanner.normalize_path(category_path)
        payload = self.scanner.scan_category(
            normalized_path, refresh=force_remote_refresh
        )
        self.db.upsert_category_cache(
            category_path=normalized_path,
            category_name=payload["category_name"],
            parent_path=payload.get("parent_path"),
            payload=payload,
        )
        payload["cache_hit"] = False
        return payload

    def refresh_media_item(
        self, media_path: str, *, force_remote_refresh: bool = False
    ) -> dict[str, Any]:
        normalized_path = OpenListScanner.normalize_path(media_path)
        payload = self.scanner.scan_media_item(
            normalized_path, refresh=force_remote_refresh
        )
        self.db.replace_media_item(
            category_path=payload["category_path"],
            media_path=normalized_path,
            item=payload["item"],
        )
        refreshed_item = self.db.get_media_item_by_path(
            payload["category_path"],
            str(payload["item"].get("openlist_path") or normalized_path),
        )
        payload["media_id"] = refreshed_item.get("db_id") if refreshed_item else None
        payload["media_path"] = payload["item"].get("openlist_path") or normalized_path
        payload["cache_hit"] = False
        payload["stats"] = {
            "item_count": 1,
            "movie_count": 1 if payload["item"].get("type") == "movie" else 0,
            "tv_count": 1 if payload["item"].get("type") == "tv" else 0,
            "episode_count": int(payload["item"].get("episode_count") or 0),
            "failed_path_count": 0,
        }
        return payload

    def _get_fs_info_with_refresh(
        self, normalized_path: str
    ) -> tuple[str, dict[str, Any] | None]:
        with OpenListClient(
            self.config.media_wall.openlist_base_url,
            token=self.config.media_wall.openlist_token,
        ) as client:
            self.scanner._ensure_openlist_auth(client)
            try:
                payload = client.get_fs_info(normalized_path)
                return normalized_path, payload if isinstance(payload, dict) else None
            except (OpenListHTTPError, OpenListAPIError) as exc:
                if not self._should_refresh_missing_file(exc):
                    raise
                refreshed_path = self._refresh_for_missing_path(normalized_path)
                if not refreshed_path:
                    return normalized_path, None
                try:
                    payload = client.get_fs_info(refreshed_path)
                except (OpenListHTTPError, OpenListAPIError) as retry_exc:
                    if self._should_refresh_missing_file(retry_exc):
                        return refreshed_path, None
                    raise
        return normalized_path, None

    @staticmethod
    def _should_refresh_missing_file(exc: Exception) -> bool:
        if isinstance(exc, OpenListHTTPError):
            return exc.status_code == 404
        if isinstance(exc, OpenListAPIError):
            message = str(exc.message or "").strip().lower()
            return exc.code == 500 and "object not found" in message
        return False

    def _refresh_for_missing_path(self, normalized_path: str) -> str | None:
        category_path = self._guess_cached_category_path(normalized_path)
        if not category_path:
            return None
        refreshed = self.refresh_category(category_path)
        return self._find_refreshed_file_path(refreshed, normalized_path)

    def _guess_cached_category_path(self, normalized_path: str) -> str | None:
        target = PurePosixPath(normalized_path)
        parts = target.parts
        if len(parts) < 3:
            return None
        for end in range(len(parts) - 1, 1, -1):
            candidate = str(PurePosixPath(*parts[:end]))
            if candidate == ".":
                candidate = "/"
            cached = self.db.get_category_cache(candidate)
            if cached:
                return candidate
        return None

    def _find_refreshed_file_path(
        self, refreshed: dict[str, Any], original_path: str
    ) -> str | None:
        target_name = PurePosixPath(original_path).name.lower()
        if not target_name:
            return None
        for item in refreshed.get("items") or []:
            for file_item in item.get("files") or []:
                candidate_path = str(file_item.get("path") or "").strip()
                if not candidate_path:
                    continue
                if PurePosixPath(candidate_path).name.lower() == target_name:
                    return OpenListScanner.normalize_path(candidate_path)
        return None

    def _build_download_url_from_payload(
        self, normalized_path: str, payload: dict[str, Any] | None
    ) -> str | None:
        if not isinstance(payload, dict):
            return None
        from urllib.parse import quote

        sign = str(payload.get("sign") or "").strip()
        if sign:
            encoded_path = quote(normalized_path, safe="/")
            encoded_sign = quote(sign, safe=":=")
            template = str(self.config.media_wall.item_url_template or "").strip()
            if template and "{path}" in template:
                return template.replace("{path}", encoded_path).replace(
                    "{sign}", encoded_sign
                )
            return f"https://yancj.de/d{encoded_path}?sign={encoded_sign}"
        raw_url = payload.get("raw_url")
        if raw_url:
            return str(raw_url)
        return None

    def _to_category_node(self, entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "name": entry.get("name"),
            "path": entry.get("path"),
            "parent_path": OpenListScanner.parent_path(entry.get("path") or ""),
            "category_count": entry.get("category_count_hint", 0),
            "media_count": entry.get("media_count_hint", 0),
            "expandable": bool(
                entry.get("category_count_hint") or entry.get("media_count_hint")
            ),
        }

    def _normalize_optional_path(self, category_path: str | None) -> str | None:
        if not category_path:
            return None
        return OpenListScanner.normalize_path(category_path)

    def _normalize_skip_directories(self, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value).strip()
        if not text:
            return []
        normalized = text.replace("|", ",")
        return [item.strip() for item in normalized.split(",") if item.strip()]

    def _deep_merge(
        self, current: dict[str, Any], payload: dict[str, Any]
    ) -> dict[str, Any]:
        merged = dict(current)
        for key, value in payload.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged
