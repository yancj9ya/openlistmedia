from __future__ import annotations

import dataclasses
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath
from typing import Any, Callable

from backend.scheduler import validate_cron_expression
from openlist_sdk import OpenListClient
from openlist_sdk.exceptions import OpenListAPIError, OpenListHTTPError

from backend.config.settings import BackendConfig, load_backend_config
from backend.repository import MediaQueryOptions, MediaWallDB
from backend.scanner import OpenListScanner
from config_loader import load_config, save_config


ConfigListener = Callable[[BackendConfig], None]


class MediaWallService:
    def __init__(self, config: BackendConfig) -> None:
        self.config = config
        self.db = MediaWallDB(config.media_wall.database_path)
        self.scanner = OpenListScanner(config.media_wall, db=self.db)
        self._category_locks: dict[str, threading.Lock] = {}
        self._category_locks_guard = threading.Lock()
        self._config_listeners: list[ConfigListener] = []
        self._category_tree_cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._category_tree_cache_lock = threading.Lock()
        self._category_tree_cache_ttl = 60.0
        self._playlist_cache: dict[str, tuple[float, str]] = {}
        self._playlist_cache_lock = threading.Lock()
        self._playlist_ttl = 600.0
        self._yaml_cache: tuple[float, dict[str, Any]] | None = None
        self._yaml_cache_lock = threading.Lock()

    def _load_config_cached(self) -> dict[str, Any]:
        try:
            from pathlib import Path

            path = Path("config.yml")
            mtime = path.stat().st_mtime if path.exists() else 0.0
        except OSError:
            mtime = 0.0
        with self._yaml_cache_lock:
            if self._yaml_cache and self._yaml_cache[0] == mtime:
                return self._yaml_cache[1]
            data = load_config()
            self._yaml_cache = (mtime, data)
            return data

    def _invalidate_yaml_cache(self) -> None:
        with self._yaml_cache_lock:
            self._yaml_cache = None

    def register_config_listener(self, listener: ConfigListener) -> None:
        self._config_listeners.append(listener)

    def _get_category_lock(self, category_path: str) -> threading.Lock:
        with self._category_locks_guard:
            lock = self._category_locks.get(category_path)
            if lock is None:
                lock = threading.Lock()
                self._category_locks[category_path] = lock
            return lock

    def _invalidate_category_tree_cache(self) -> None:
        with self._category_tree_cache_lock:
            self._category_tree_cache.clear()

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "api_prefix": self.config.api.prefix,
            "media_root": self.config.media_wall.media_root,
            "database_path": str(self.db.path),
        }

    def get_category_tree(self, category_path: str | None = None) -> dict[str, Any]:
        target_path = category_path or self.config.media_wall.media_root
        cache_key = target_path
        now = time.monotonic()
        with self._category_tree_cache_lock:
            cached = self._category_tree_cache.get(cache_key)
            if cached and now - cached[0] < self._category_tree_cache_ttl:
                return cached[1]

        payload = self.scanner.list_categories(target_path)
        payload["root"] = self.config.media_wall.media_root
        payload["skip_directories"] = self.config.media_wall.skip_directories
        payload["children"] = [
            self._to_category_node(entry) for entry in payload.get("entries", [])
        ]
        with self._category_tree_cache_lock:
            self._category_tree_cache[cache_key] = (time.monotonic(), payload)
        return payload

    def get_settings(self) -> dict[str, Any]:
        return self._load_config_cached()

    def authenticate_access(self, passcode: str) -> dict[str, Any] | None:
        config = self._load_config_cached()
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
        config = self._load_config_cached()
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
        refresh_cron = str(media_wall.get("refresh_cron") or "").strip()
        if refresh_cron:
            validate_cron_expression(refresh_cron)
            media_wall["refresh_cron"] = refresh_cron
        else:
            media_wall["refresh_cron"] = ""
        media_wall["skip_directories"] = normalized_skip_directories
        merged["media_wall"] = media_wall

        save_config(merged)
        self._invalidate_yaml_cache()

        reload_result = self._apply_config_reload()

        if normalized_skip_directories != previous_skip_directories:
            self.db.clear_all_cache()

        return {
            "saved": merged,
            "restart_required": reload_result["restart_required"],
            "changed_fields": reload_result["changed_fields"],
        }

    def _apply_config_reload(self) -> dict[str, Any]:
        fresh = load_backend_config()
        old_api = self.config.api
        restart_fields: list[str] = []
        if fresh.api.host != old_api.host:
            restart_fields.append("backend.host")
        if fresh.api.port != old_api.port:
            restart_fields.append("backend.port")
        if str(fresh.media_wall.database_path) != str(
            self.config.media_wall.database_path
        ):
            restart_fields.append("media_wall.database_path")

        self._mutate_dataclass(self.config.api, fresh.api)
        self._mutate_dataclass(self.config.api.cors, fresh.api.cors)
        self._mutate_dataclass(self.config.frontend, fresh.frontend)
        self._mutate_dataclass(self.config.media_wall, fresh.media_wall)

        for listener in list(self._config_listeners):
            try:
                listener(self.config)
            except Exception as exc:
                print(f"Config listener failed: {exc}")

        return {
            "restart_required": bool(restart_fields),
            "changed_fields": restart_fields,
        }

    @staticmethod
    def _mutate_dataclass(target: Any, source: Any) -> None:
        if not dataclasses.is_dataclass(target) or not dataclasses.is_dataclass(source):
            return
        for field in dataclasses.fields(source):
            setattr(target, field.name, getattr(source, field.name))

    def apply_settings(self) -> dict[str, Any]:
        return self._apply_config_reload()

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
        print(
            "[media] list "
            f"category={normalized_path or '<all>'} page={page} "
            f"page_size={page_size} include_descendants={include_descendants}"
        )
        if normalized_path:
            ttl = self.config.media_wall.cache_ttl_seconds
            if not self.db.cache_is_fresh(normalized_path, ttl):
                if self.db.category_cache_exists(normalized_path):
                    print(f"[media] cache stale, schedule shallow refresh: {normalized_path}")
                    self._schedule_background_refresh(normalized_path)
                else:
                    print(f"[media] cache missing, run shallow refresh: {normalized_path}")
                    with self._get_category_lock(normalized_path):
                        if not self.db.cache_is_fresh(normalized_path, ttl):
                            self._refresh_category_shallow_locked(normalized_path)
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
        print(
            "[media] list result "
            f"category={normalized_path or '<all>'} returned={len(query_result.items)} "
            f"total={query_result.total}"
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

    def _schedule_background_refresh(self, normalized_path: str) -> None:
        lock = self._get_category_lock(normalized_path)
        if not lock.acquire(blocking=False):
            print(f"[media] background refresh already running: {normalized_path}")
            return

        def run() -> None:
            print(f"[media] background shallow refresh start: {normalized_path}")
            try:
                self._refresh_category_shallow_locked(normalized_path)
                print(f"[media] background shallow refresh done: {normalized_path}")
            except Exception as exc:
                print(f"[media] background shallow refresh failed for {normalized_path}: {exc}")
            finally:
                lock.release()

        threading.Thread(
            target=run,
            daemon=True,
            name=f"bg-refresh-{normalized_path}",
        ).start()

    def get_media_detail(self, media_id: int) -> dict[str, Any] | None:
        print(f"[media] detail request id={media_id}")
        item = self.db.get_media_item(media_id)
        if item is None:
            print(f"[media] detail not found id={media_id}")
            return None
        if self._needs_detail_scan(item):
            media_path = str(item.get("openlist_path") or "").strip()
            if media_path:
                print(f"[media] detail needs deep scan id={media_id} path={media_path}")
                refreshed = self.refresh_media_item(
                    media_path, force_remote_refresh=False
                )
                refreshed_id = refreshed.get("media_id")
                item = self.db.get_media_item(int(refreshed_id or media_id))
                if item is None:
                    return None
        item = self._ensure_media_poster(item)
        print(
            "[media] detail ready "
            f"id={media_id} title={item.get('title')} "
            f"files={len(item.get('files') or [])} seasons={len(item.get('seasons') or [])}"
        )
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

    def _ensure_media_poster(self, item: dict[str, Any]) -> dict[str, Any]:
        if item.get("poster_url"):
            return item
        media_path = str(item.get("openlist_path") or "").strip()
        print(f"[media] poster missing, fetch TMDb metadata: {media_path}")
        updated = self.scanner.fill_missing_media_poster(item)
        if updated is item or not updated.get("poster_url"):
            print(f"[media] poster still missing after TMDb fetch: {media_path}")
            return item
        category_path = str(item.get("category_path") or "").strip()
        media_path = str(item.get("openlist_path") or "").strip()
        if not category_path or not media_path:
            return updated
        try:
            self.db.replace_media_item(category_path, media_path, updated)
            refreshed = self.db.get_media_item_by_path(category_path, media_path)
            if refreshed is not None:
                print(f"[media] poster saved to cache: {media_path}")
                return refreshed
        except ValueError as exc:
            print(f"Poster cache update skipped for {media_path}: {exc}")
        return updated

    @staticmethod
    def _needs_detail_scan(item: dict[str, Any]) -> bool:
        if item.get("scan_level") == "shallow":
            return True
        if item.get("detail_scanned_at"):
            return False
        return not (item.get("files") or item.get("seasons"))

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
        with self._get_category_lock(normalized_path):
            return self._refresh_category_locked(
                normalized_path, force_remote_refresh=force_remote_refresh
            )

    def refresh_category_shallow(
        self, category_path: str, *, force_remote_refresh: bool = False
    ) -> dict[str, Any]:
        normalized_path = OpenListScanner.normalize_path(category_path)
        with self._get_category_lock(normalized_path):
            return self._refresh_category_shallow_locked(
                normalized_path, force_remote_refresh=force_remote_refresh
            )

    def _refresh_category_locked(
        self, normalized_path: str, *, force_remote_refresh: bool = False
    ) -> dict[str, Any]:
        print(
            "[media] category deep refresh start "
            f"path={normalized_path} openlist_refresh={force_remote_refresh}"
        )
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
        self._invalidate_category_tree_cache()
        print(
            "[media] category deep refresh done "
            f"path={normalized_path} items={payload.get('stats', {}).get('item_count', 0)}"
        )
        return payload

    def _refresh_category_shallow_locked(
        self, normalized_path: str, *, force_remote_refresh: bool = False
    ) -> dict[str, Any]:
        print(
            "[media] category shallow refresh start "
            f"path={normalized_path} openlist_refresh={force_remote_refresh}"
        )
        existing_items = self._get_existing_items_by_path(normalized_path)
        payload = self.scanner.scan_category_shallow(
            normalized_path,
            refresh=force_remote_refresh,
            existing_items=existing_items,
        )
        payload = self._merge_shallow_payload_with_existing(
            normalized_path, payload, existing_items=existing_items
        )
        self.db.upsert_category_cache(
            category_path=normalized_path,
            category_name=payload["category_name"],
            parent_path=payload.get("parent_path"),
            payload=payload,
        )
        payload["cache_hit"] = False
        self._invalidate_category_tree_cache()
        print(
            "[media] category shallow refresh done "
            f"path={normalized_path} items={payload.get('stats', {}).get('item_count', 0)} "
            f"existing={len(existing_items)}"
        )
        return payload

    def _get_existing_items_by_path(
        self, normalized_path: str
    ) -> dict[str, dict[str, Any]]:
        cached = self.db.get_category_cache(normalized_path) or {}
        return {
            str(item.get("openlist_path") or "").strip(): item
            for item in cached.get("items") or []
            if str(item.get("openlist_path") or "").strip()
        }

    def _merge_shallow_payload_with_existing(
        self,
        normalized_path: str,
        payload: dict[str, Any],
        *,
        existing_items: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        existing_by_path = existing_items or self._get_existing_items_by_path(
            normalized_path
        )
        merged_items: list[dict[str, Any]] = []
        for shallow in payload.get("items") or []:
            media_path = str(shallow.get("openlist_path") or "").strip()
            existing = existing_by_path.get(media_path)
            if existing:
                if (
                    existing.get("scan_level") == "detail"
                    or existing.get("detail_scanned_at")
                ):
                    merged = {**existing}
                    merged.update(
                        {
                            "title": shallow.get("title"),
                            "year": shallow.get("year"),
                            "tmdb_id": shallow.get("tmdb_id"),
                            "category_path": shallow.get("category_path"),
                            "category_label": shallow.get("category_label"),
                            "openlist_path": shallow.get("openlist_path"),
                            "openlist_url": shallow.get("openlist_url"),
                        }
                    )
                else:
                    merged = {**shallow}
                    for key in (
                        "type",
                        "display_title",
                        "original_title",
                        "overview",
                        "vote_average",
                        "genres",
                        "release_date",
                        "poster_path",
                        "poster_url",
                        "backdrop_path",
                        "backdrop_url",
                    ):
                        if existing.get(key) not in (None, "", []):
                            merged[key] = existing.get(key)
            else:
                merged = shallow
            merged_items.append(merged)
        payload["items"] = merged_items
        stats = payload.setdefault("stats", {})
        stats["item_count"] = len(merged_items)
        stats["movie_count"] = sum(
            1 for item in merged_items if item.get("type") == "movie"
        )
        stats["tv_count"] = sum(
            1 for item in merged_items if item.get("type") == "tv"
        )
        stats["episode_count"] = sum(
            int(item.get("episode_count") or 0) for item in merged_items
        )
        stats["failed_path_count"] = len(payload.get("failed_paths") or [])
        return payload

    def refresh_media_item(
        self, media_path: str, *, force_remote_refresh: bool = False
    ) -> dict[str, Any]:
        normalized_path = OpenListScanner.normalize_path(media_path)
        parent_category = OpenListScanner.parent_path(normalized_path) or "/"
        with self._get_category_lock(parent_category):
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

    def refresh_all_categories(
        self, *, force_remote_refresh: bool = False
    ) -> dict[str, Any]:
        root_path = OpenListScanner.normalize_path(self.config.media_wall.media_root)
        pending_paths = [root_path]
        seen_paths: set[str] = set()
        refreshed_paths: list[str] = []
        failed_paths: list[dict[str, str]] = []

        while pending_paths:
            current_path = OpenListScanner.normalize_path(pending_paths.pop(0))
            if current_path in seen_paths:
                continue
            seen_paths.add(current_path)

            try:
                tree = self.scanner.list_categories(
                    current_path, refresh=force_remote_refresh
                )
                for entry in tree.get("entries", []):
                    child_path = str(entry.get("path") or "").strip()
                    if child_path:
                        pending_paths.append(child_path)
            except Exception as exc:
                failed_paths.append(
                    {
                        "path": current_path,
                        "stage": "list",
                        "message": str(exc),
                    }
                )
                continue

            try:
                self.refresh_category(
                    current_path, force_remote_refresh=force_remote_refresh
                )
                refreshed_paths.append(current_path)
            except Exception as exc:
                failed_paths.append(
                    {
                        "path": current_path,
                        "stage": "refresh",
                        "message": str(exc),
                    }
                )

        return {
            "root_path": root_path,
            "refreshed_count": len(refreshed_paths),
            "failed_count": len(failed_paths),
            "refreshed_paths": refreshed_paths,
            "failed_paths": failed_paths,
        }

    def _get_fs_info_with_refresh(
        self, normalized_path: str
    ) -> tuple[str, dict[str, Any] | None]:
        client = self.scanner.get_client()
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

    def record_play_history(self, media_id: int, file_path: str | None = None) -> None:
        media = self.db.get_media_item(media_id)
        if media:
            self.db.record_play_history(
                media_id=media_id,
                media_title=media.get("title", "Unknown"),
                media_type=media.get("type"),
                poster_url=media.get("poster_url"),
                tmdb_id=int(media.get("tmdb_id")) if media.get("tmdb_id") is not None else None,
                release_year=int(media.get("year")) if media.get("year") is not None else None,
            )
        if file_path:
            self.db.upsert_last_played_episode(media_id, file_path)

    def get_last_played_episode(self, media_id: int) -> dict[str, Any] | None:
        return self.db.get_last_played_episode(media_id)

    def create_playlist(self, paths: list[str]) -> dict[str, Any]:
        cleaned = [str(p).strip() for p in paths if str(p).strip()]
        if not cleaned:
            raise ValueError("paths is empty")
        resolved: list[tuple[str, str | None]] = [(p, None) for p in cleaned]

        def resolve(index_path: tuple[int, str]) -> tuple[int, str | None]:
            index, path = index_path
            try:
                return index, self.resolve_download_url(path)
            except Exception:
                return index, None

        workers = min(len(cleaned), 8)
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="playlist-resolve"
        ) as pool:
            for index, url in pool.map(resolve, enumerate(cleaned)):
                resolved[index] = (cleaned[index], url)

        lines = ["#EXTM3U"]
        count = 0
        for path, url in resolved:
            if not url:
                continue
            name = PurePosixPath(path).name or path
            lines.append(f"#EXTINF:-1,{name}")
            lines.append(url)
            count += 1

        if count == 0:
            raise ValueError("No resolvable playable URL in the given paths")

        text = "\n".join(lines) + "\n"
        playlist_id = secrets.token_urlsafe(16)
        now = time.monotonic()
        with self._playlist_cache_lock:
            for key in list(self._playlist_cache.keys()):
                created_at, _ = self._playlist_cache[key]
                if now - created_at > self._playlist_ttl:
                    del self._playlist_cache[key]
            self._playlist_cache[playlist_id] = (now, text)
        return {"id": playlist_id, "count": count}

    def get_playlist(self, playlist_id: str) -> str | None:
        now = time.monotonic()
        with self._playlist_cache_lock:
            entry = self._playlist_cache.get(playlist_id)
            if not entry:
                return None
            created_at, text = entry
            if now - created_at > self._playlist_ttl:
                del self._playlist_cache[playlist_id]
                return None
            return text

    def get_recent_play_history(self, limit: int = 10) -> list[dict[str, Any]]:
        items = self.db.get_recent_play_history(limit)
        normalized: list[dict[str, Any]] = []
        for item in items:
            vote_average = item.get("vote_average")
            normalized.append(
                {
                    **item,
                    "vote_average": float(vote_average)
                    if vote_average is not None
                    else None,
                }
            )
        return normalized
