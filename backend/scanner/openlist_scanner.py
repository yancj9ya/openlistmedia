from __future__ import annotations

import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import quote

from openlist_sdk import OpenListClient
from openlist_sdk.exceptions import OpenListAPIError, OpenListHTTPError
from tmdb_sdk import TMDbAPIError, TMDbClient, TMDbHTTPError

from backend.config.settings import MediaWallConfig


MEDIA_PATTERN = re.compile(
    r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*\{tmdb-(?P<tmdb_id>\d+)\}\s*$"
)
SEASON_PATTERN = re.compile(r"^Season\s+(?P<number>\d+)$", re.IGNORECASE)
EPISODE_PATTERN = re.compile(
    r"S(?P<season>\d{1,2})E(?P<episode_start>\d{1,3})(?:-E?(?P<episode_end>\d{1,3}))?",
    re.IGNORECASE,
)
VIDEO_SUFFIXES = {
    ".mp4",
    ".mkv",
    ".avi",
    ".ts",
    ".m2ts",
    ".mov",
    ".wmv",
    ".flv",
    ".mpg",
    ".mpeg",
}


class OpenListScanner:
    def __init__(self, config: MediaWallConfig, db: Any = None) -> None:
        self.config = config
        self.db = db
        self.tmdb_image_base_url: str | None = None
        self._scan_local = threading.local()
        self._tmdb_cache_lock = threading.Lock()
        self._client_local = threading.local()
        self._login_lock = threading.Lock()
        if self.db is not None and hasattr(self.db, "load_all_tmdb_cache"):
            self.tmdb_cache = self.db.load_all_tmdb_cache()
        else:
            self.tmdb_cache = {}
        self._client_local = threading.local()
        self._login_lock = threading.Lock()

    def get_client(self) -> OpenListClient:
        client = getattr(self._client_local, "client", None)
        if client is None:
            client = OpenListClient(
                self.config.openlist_base_url,
                token=self.config.openlist_token,
            )
            if not client.token:
                with self._login_lock:
                    if not client.token:
                        self._ensure_openlist_auth(client)
            self._client_local.client = client
        return client

    @property
    def failed_paths(self) -> list[dict[str, Any]]:
        paths = getattr(self._scan_local, "failed_paths", None)
        if paths is None:
            paths = []
            self._scan_local.failed_paths = paths
        return paths

    @failed_paths.setter
    def failed_paths(self, value: list[dict[str, Any]]) -> None:
        self._scan_local.failed_paths = value

    def list_categories(
        self, base_path: str | None = None, *, refresh: bool = False
    ) -> dict[str, Any]:
        root = self.normalize_path(base_path or self.config.media_root)
        client = self.get_client()
        return {
            "path": root,
            "parent_path": self.parent_path(root),
            "entries": self._list_categories(client, root, refresh=refresh),
        }

    def scan_category(
        self, category_path: str, *, refresh: bool = False
    ) -> dict[str, Any]:
        category_path = self.normalize_path(category_path)
        print(
            "[scanner] deep category scan start "
            f"path={category_path} openlist_refresh={refresh}"
        )
        category_name = (
            category_path.rstrip("/").split("/")[-1] if category_path != "/" else "/"
        )
        openlist = self.get_client()
        tmdb_client: TMDbClient | None = None
        if self.config.tmdb_read_access_token or self.config.tmdb_api_key:
            tmdb_client = TMDbClient(
                self.config.tmdb_read_access_token, api_key=self.config.tmdb_api_key
            )
        try:
            if tmdb_client:
                self.tmdb_image_base_url = tmdb_client.configuration_details()[
                    "images"
                ]["secure_base_url"]
            items = self._scan_category_items(
                openlist, tmdb_client, category_path, refresh=refresh
            )
        finally:
            if tmdb_client:
                tmdb_client.close()
        items.sort(key=lambda item: (item["type"], item["title"].lower()))
        payload = self._build_category_payload(
            category_path, category_name, items, refresh
        )
        print(
            "[scanner] deep category scan done "
            f"path={category_path} items={len(items)} "
            f"failed={len(self.failed_paths)}"
        )
        self._save_tmdb_cache()
        return payload

    def scan_category_shallow(
        self,
        category_path: str,
        *,
        refresh: bool = False,
        existing_items: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        category_path = self.normalize_path(category_path)
        print(
            "[scanner] shallow category scan start "
            f"path={category_path} openlist_refresh={refresh}"
        )
        category_name = (
            category_path.rstrip("/").split("/")[-1] if category_path != "/" else "/"
        )
        parent_name = category_name if category_path != "/" else ""
        openlist = self.get_client()
        existing_items = existing_items or {}
        tmdb_client: TMDbClient | None = None
        self.failed_paths = []
        items: list[dict[str, Any]] = []
        missing_metadata: list[tuple[str, re.Match[str]]] = []
        for entry in self._list_dir(openlist, category_path, refresh=refresh):
            if not self._is_dir(entry):
                continue
            name = entry["name"]
            if self._should_skip_dir(name):
                continue
            media_match = MEDIA_PATTERN.match(name)
            if not media_match:
                continue
            media_path = self._join_path(category_path, name)
            existing = existing_items.get(media_path)
            if existing:
                items.append(
                    self._reuse_shallow_cached_media_item(
                        existing, media_path, [parent_name], media_match
                    )
                )
            else:
                missing_metadata.append((media_path, media_match))

        if missing_metadata and (
            self.config.tmdb_read_access_token or self.config.tmdb_api_key
        ):
            tmdb_client = TMDbClient(
                self.config.tmdb_read_access_token, api_key=self.config.tmdb_api_key
            )
        try:
            if tmdb_client:
                self.tmdb_image_base_url = tmdb_client.configuration_details()[
                    "images"
                ]["secure_base_url"]
            for media_path, media_match in missing_metadata:
                items.append(
                    self._make_shallow_media_item(
                        media_path,
                        [parent_name],
                        media_match,
                        tmdb_client,
                        self._infer_media_type_from_path(category_path),
                    )
                )
        finally:
            if tmdb_client:
                tmdb_client.close()
        items.sort(key=lambda item: (item["type"], item["title"].lower()))
        print(
            "[scanner] shallow category scan done "
            f"path={category_path} items={len(items)} reused={len(items) - len(missing_metadata)} "
            f"new={len(missing_metadata)} failed={len(self.failed_paths)}"
        )
        self._save_tmdb_cache()
        return self._build_category_payload(
            category_path, category_name, items, refresh
        )

    def scan_media_item(
        self, media_path: str, *, refresh: bool = False
    ) -> dict[str, Any]:
        media_path = self.normalize_path(media_path)
        print(
            "[scanner] media item scan start "
            f"path={media_path} openlist_refresh={refresh}"
        )
        media_name = media_path.rstrip("/").split("/")[-1] if media_path != "/" else "/"
        media_match = MEDIA_PATTERN.match(media_name)
        if not media_match:
            raise ValueError("Invalid media_path: expected a media directory name.")
        category_path = self.parent_path(media_path)
        if not category_path:
            raise ValueError("Invalid media_path: missing parent category path.")
        openlist = self.get_client()
        tmdb_client: TMDbClient | None = None
        if self.config.tmdb_read_access_token or self.config.tmdb_api_key:
            tmdb_client = TMDbClient(
                self.config.tmdb_read_access_token, api_key=self.config.tmdb_api_key
            )
        try:
            if tmdb_client:
                self.tmdb_image_base_url = tmdb_client.configuration_details()[
                    "images"
                ]["secure_base_url"]
            item = self._scan_media_directory(
                openlist,
                tmdb_client,
                media_path,
                [category_path.rstrip("/").split("/")[-1]],
                media_match,
                refresh=refresh,
            )
        finally:
            if tmdb_client:
                tmdb_client.close()
        print(
            "[scanner] media item scan done "
            f"path={media_path} type={item.get('type')} "
            f"files={len(item.get('files') or [])} seasons={len(item.get('seasons') or [])}"
        )
        self._save_tmdb_cache()
        return {
            "category_path": category_path,
            "category_name": category_path.rstrip("/").split("/")[-1]
            if category_path != "/"
            else "/",
            "media_path": media_path,
            "media_name": media_name,
            "item": item,
            "openlist_refreshed": refresh,
        }

    def _list_categories(
        self, client: OpenListClient, current_path: str, *, refresh: bool = False
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, str]] = []
        for entry in self._list_dir(client, current_path, refresh=refresh):
            if not self._is_dir(entry):
                continue
            name = entry["name"]
            if self._should_skip_dir(name):
                continue
            if MEDIA_PATTERN.match(name):
                continue
            path = self._join_path(current_path, name)
            candidates.append({"name": name, "path": path})

        if not candidates:
            return []

        def count(path: str) -> tuple[int, int]:
            child_client = self.get_client()
            return self._count_directory_summary(
                child_client, path, refresh=refresh
            )

        workers = min(len(candidates), 8)
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="category-count"
        ) as pool:
            counts = list(pool.map(count, [item["path"] for item in candidates]))

        results: list[dict[str, Any]] = []
        for candidate, (category_count, media_count) in zip(candidates, counts):
            results.append(
                {
                    "name": candidate["name"],
                    "path": candidate["path"],
                    "category_count_hint": category_count,
                    "media_count_hint": media_count,
                }
            )
        return results

    def _count_directory_summary(
        self, client: OpenListClient, current_path: str, *, refresh: bool = False
    ) -> tuple[int, int]:
        category_count = 0
        media_count = 0
        for entry in self._list_dir(client, current_path, refresh=refresh):
            if not self._is_dir(entry):
                continue
            name = entry["name"]
            if self._should_skip_dir(name):
                continue
            if MEDIA_PATTERN.match(name):
                media_count += 1
            else:
                category_count += 1
        return category_count, media_count

    def _build_category_payload(
        self,
        category_path: str,
        category_name: str,
        items: list[dict[str, Any]],
        refresh: bool,
    ) -> dict[str, Any]:
        return {
            "category_path": category_path,
            "category_name": category_name,
            "parent_path": self.parent_path(category_path),
            "items": items,
            "failed_paths": self.failed_paths,
            "stats": {
                "item_count": len(items),
                "movie_count": sum(1 for item in items if item["type"] == "movie"),
                "tv_count": sum(1 for item in items if item["type"] == "tv"),
                "episode_count": sum(item.get("episode_count", 0) for item in items),
                "failed_path_count": len(self.failed_paths),
            },
            "openlist_refreshed": refresh,
        }

    def _scan_category_items(
        self,
        client: OpenListClient,
        tmdb_client: TMDbClient | None,
        category_path: str,
        *,
        refresh: bool = False,
    ) -> list[dict[str, Any]]:
        self.failed_paths = []
        parent_name = (
            category_path.rstrip("/").split("/")[-1] if category_path != "/" else ""
        )
        candidates: list[tuple[str, re.Match[str]]] = []
        for entry in self._list_dir(client, category_path, refresh=refresh):
            if not self._is_dir(entry):
                continue
            name = entry["name"]
            if self._should_skip_dir(name):
                continue
            media_match = MEDIA_PATTERN.match(name)
            if not media_match:
                continue
            candidates.append(
                (self._join_path(category_path, name), media_match)
            )

        if not candidates:
            return []

        if len(candidates) == 1:
            path, media_match = candidates[0]
            return [
                self._scan_media_directory(
                    client,
                    tmdb_client,
                    path,
                    [parent_name],
                    media_match,
                    refresh=refresh,
                )
            ]

        aggregated_failed: list[dict[str, Any]] = []
        aggregated_failed_lock = threading.Lock()

        def scan_one(task: tuple[str, re.Match[str]]) -> dict[str, Any]:
            path, media_match = task
            self._scan_local.failed_paths = []
            child_openlist = self.get_client()
            child_tmdb: TMDbClient | None = None
            if tmdb_client is not None:
                child_tmdb = TMDbClient(
                    self.config.tmdb_read_access_token,
                    api_key=self.config.tmdb_api_key,
                )
            try:
                item = self._scan_media_directory(
                    child_openlist,
                    child_tmdb,
                    path,
                    [parent_name],
                    media_match,
                    refresh=refresh,
                )
            finally:
                if child_tmdb is not None:
                    child_tmdb.close()
            with aggregated_failed_lock:
                aggregated_failed.extend(self._scan_local.failed_paths)
            self._scan_local.failed_paths = []
            return item

        workers = min(len(candidates), 16)
        with ThreadPoolExecutor(
            max_workers=workers, thread_name_prefix="media-scan"
        ) as pool:
            items = list(pool.map(scan_one, candidates))

        self.failed_paths = aggregated_failed
        return items

    def _reuse_shallow_cached_media_item(
        self,
        existing: dict[str, Any],
        media_path: str,
        category_parts: list[str],
        media_match: re.Match[str],
    ) -> dict[str, Any]:
        title = media_match.group("title").strip()
        year = int(media_match.group("year"))
        tmdb_id = int(media_match.group("tmdb_id"))
        item = {**existing}
        item.update(
            {
                "title": title,
                "year": year,
                "tmdb_id": tmdb_id,
                "category_path": category_parts,
                "category_label": " / ".join(part for part in category_parts if part),
                "openlist_path": media_path,
                "openlist_url": self._build_item_url(media_path),
            }
        )
        return item

    def _make_shallow_media_item(
        self,
        media_path: str,
        category_parts: list[str],
        media_match: re.Match[str],
        tmdb_client: TMDbClient | None,
        inferred_media_type: str | None = None,
    ) -> dict[str, Any]:
        title = media_match.group("title").strip()
        year = int(media_match.group("year"))
        tmdb_id = int(media_match.group("tmdb_id"))
        media_type = inferred_media_type or "movie"
        print(
            "[scanner] shallow media metadata "
            f"path={media_path} tmdb_id={tmdb_id} preferred_type={media_type}"
        )
        metadata = self._fetch_tmdb_metadata(tmdb_client, media_type, tmdb_id)
        if metadata and not self._metadata_matches_media_name(metadata, title, year):
            print(
                "[scanner] shallow media metadata mismatch "
                f"path={media_path} type={media_type}"
            )
            metadata = None
        if not metadata:
            fallback_type = "tv" if media_type == "movie" else "movie"
            fallback = self._fetch_tmdb_metadata(tmdb_client, fallback_type, tmdb_id)
            if fallback and self._metadata_matches_media_name(fallback, title, year):
                print(
                    "[scanner] shallow media metadata fallback matched "
                    f"path={media_path} type={fallback_type}"
                )
                media_type = fallback_type
                metadata = fallback
        return {
            "title": title,
            "display_title": (metadata or {}).get("title")
            or (metadata or {}).get("name")
            or title,
            "original_title": (metadata or {}).get("original_title")
            or (metadata or {}).get("original_name"),
            "year": year,
            "type": media_type,
            "tmdb_id": tmdb_id,
            "overview": (metadata or {}).get("overview"),
            "vote_average": (metadata or {}).get("vote_average"),
            "genres": [
                genre.get("name")
                for genre in (metadata or {}).get("genres", [])
                if genre.get("name")
            ],
            "release_date": (metadata or {}).get("release_date")
            or (metadata or {}).get("first_air_date"),
            "poster_path": (metadata or {}).get("poster_path"),
            "poster_url": self._image_url((metadata or {}).get("poster_path"), "w500"),
            "backdrop_path": (metadata or {}).get("backdrop_path"),
            "backdrop_url": self._image_url(
                (metadata or {}).get("backdrop_path"), "w1280"
            ),
            "category_path": category_parts,
            "category_label": " / ".join(part for part in category_parts if part),
            "openlist_path": media_path,
            "openlist_url": self._build_item_url(media_path),
            "file_count": 0,
            "season_count": 0,
            "episode_count": 0,
            "files": [],
            "seasons": [],
            "scan_level": "shallow",
            "detail_scanned_at": None,
        }

    def _scan_media_directory(
        self,
        client: OpenListClient,
        tmdb_client: TMDbClient | None,
        media_path: str,
        category_parts: list[str],
        media_match: re.Match[str],
        *,
        refresh: bool = False,
    ) -> dict[str, Any]:
        title = media_match.group("title").strip()
        year = int(media_match.group("year"))
        tmdb_id = int(media_match.group("tmdb_id"))
        print(
            "[scanner] deep media directory scan start "
            f"path={media_path} tmdb_id={tmdb_id} openlist_refresh={refresh}"
        )
        top_level_entries = self._list_dir(client, media_path, refresh=refresh)
        files: list[dict[str, Any]] = []
        seasons: dict[int, dict[str, Any]] = {}

        dir_tasks: list[tuple[str, str, re.Match[str] | None]] = []
        direct_video_entries: list[dict[str, Any]] = []
        for entry in top_level_entries:
            name = entry["name"]
            path = self._join_path(media_path, name)
            if self._is_dir(entry):
                dir_tasks.append((name, path, SEASON_PATTERN.match(name)))
            elif self._is_video(name):
                direct_video_entries.append(entry)

        def scan_dir(
            task: tuple[str, str, re.Match[str] | None],
        ) -> tuple[str, str, re.Match[str] | None, list[dict[str, Any]]]:
            name, path, season_match = task
            sub_client = self.get_client()
            episodes = self._scan_files_recursive(sub_client, path, refresh=refresh)
            return name, path, season_match, episodes

        if len(dir_tasks) <= 1:
            dir_results = [scan_dir(t) for t in dir_tasks]
        else:
            workers = min(len(dir_tasks), 4)
            with ThreadPoolExecutor(
                max_workers=workers, thread_name_prefix="season-scan"
            ) as pool:
                dir_results = list(pool.map(scan_dir, dir_tasks))

        for name, path, season_match, episodes in dir_results:
            if season_match:
                season_number = int(season_match.group("number"))
                seasons[season_number] = {
                    "season_number": season_number,
                    "name": name,
                    "path": path,
                    "episodes": episodes,
                }
            files.extend(episodes)

        for entry in direct_video_entries:
            files.append(self._make_file_entry(entry, media_path))

        media_type = (
            "tv"
            if seasons or any(file["episode_numbers"] for file in files)
            else "movie"
        )
        metadata = self._fetch_tmdb_metadata(tmdb_client, media_type, tmdb_id)
        if not metadata:
            fallback_type = "movie" if media_type == "tv" else "tv"
            fallback = self._fetch_tmdb_metadata(tmdb_client, fallback_type, tmdb_id)
            if fallback:
                media_type = fallback_type
                metadata = fallback

        if media_type == "tv" and not seasons:
            seasons = self._group_loose_episodes(files)
        season_list = [seasons[number] for number in sorted(seasons)]
        print(
            "[scanner] deep media directory scan done "
            f"path={media_path} type={media_type} files={len(files)} "
            f"seasons={len(season_list)}"
        )
        for season in season_list:
            season["episodes"].sort(key=self._file_sort_key)
        files.sort(key=self._file_sort_key)
        return {
            "title": title,
            "display_title": (metadata or {}).get("title")
            or (metadata or {}).get("name")
            or title,
            "original_title": (metadata or {}).get("original_title")
            or (metadata or {}).get("original_name"),
            "year": year,
            "type": media_type,
            "tmdb_id": tmdb_id,
            "overview": (metadata or {}).get("overview"),
            "vote_average": (metadata or {}).get("vote_average"),
            "genres": [
                genre.get("name")
                for genre in (metadata or {}).get("genres", [])
                if genre.get("name")
            ],
            "release_date": (metadata or {}).get("release_date")
            or (metadata or {}).get("first_air_date"),
            "poster_path": (metadata or {}).get("poster_path"),
            "poster_url": self._image_url((metadata or {}).get("poster_path"), "w500"),
            "backdrop_path": (metadata or {}).get("backdrop_path"),
            "backdrop_url": self._image_url(
                (metadata or {}).get("backdrop_path"), "w1280"
            ),
            "category_path": category_parts,
            "category_label": " / ".join(part for part in category_parts if part),
            "openlist_path": media_path,
            "openlist_url": self._build_item_url(media_path),
            "file_count": len(files),
            "season_count": len(season_list),
            "episode_count": sum(len(season["episodes"]) for season in season_list),
            "files": files,
            "seasons": season_list,
            "scan_level": "detail",
            "detail_scanned_at": int(time.time()),
        }

    def _scan_files_recursive(
        self, client: OpenListClient, current_path: str, *, refresh: bool = False
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            entries = self._list_dir(client, current_path, refresh=refresh)
        except OpenListHTTPError as exc:
            self._handle_scan_error(current_path, exc)
            return results
        for entry in entries:
            name = entry["name"]
            path = self._join_path(current_path, name)
            if self._is_dir(entry):
                results.extend(
                    self._scan_files_recursive(client, path, refresh=refresh)
                )
            elif self._is_video(name):
                results.append(self._make_file_entry(entry, current_path))
        return results

    def _make_file_entry(
        self, entry: dict[str, Any], parent_path: str
    ) -> dict[str, Any]:
        name = entry["name"]
        season_number = None
        episode_numbers: list[int] = []
        match = EPISODE_PATTERN.search(name)
        if match:
            season_number = int(match.group("season"))
            start = int(match.group("episode_start"))
            end = int(match.group("episode_end") or start)
            episode_numbers = list(range(start, end + 1))
        path = self._join_path(parent_path, name)
        return {
            "name": name,
            "path": path,
            "size": entry.get("size"),
            "modified": entry.get("modified") or entry.get("updated_at"),
            "extension": Path(name).suffix.lower(),
            "season_number": season_number,
            "episode_numbers": episode_numbers,
            "openlist_url": self._build_item_url(path),
        }

    def _group_loose_episodes(
        self, files: list[dict[str, Any]]
    ) -> dict[int, dict[str, Any]]:
        grouped: dict[int, dict[str, Any]] = {}
        for file in files:
            season_number = file["season_number"]
            if season_number is None:
                continue
            grouped.setdefault(
                season_number,
                {
                    "season_number": season_number,
                    "name": f"Season {season_number}",
                    "path": None,
                    "episodes": [],
                },
            )["episodes"].append(file)
        return grouped

    def fill_missing_media_poster(self, item: dict[str, Any]) -> dict[str, Any]:
        if item.get("poster_url"):
            return item
        tmdb_id = item.get("tmdb_id")
        if not tmdb_id or not (
            self.config.tmdb_read_access_token or self.config.tmdb_api_key
        ):
            return item
        tmdb_client = TMDbClient(
            self.config.tmdb_read_access_token, api_key=self.config.tmdb_api_key
        )
        try:
            self.tmdb_image_base_url = tmdb_client.configuration_details()["images"][
                "secure_base_url"
            ]
            media_type = str(item.get("type") or "").strip()
            if media_type not in ("movie", "tv"):
                media_type = self._infer_media_type_from_path(
                    str(item.get("category_path") or item.get("openlist_path") or "")
                ) or "movie"
            metadata = self._fetch_tmdb_metadata(
                tmdb_client, media_type, int(tmdb_id)
            )
            title = str(item.get("title") or "").strip()
            year = int(item.get("year") or 0)
            if metadata and not self._metadata_matches_media_name(
                metadata, title, year
            ):
                metadata = None
            if not metadata and media_type != "tv":
                fallback = self._fetch_tmdb_metadata(tmdb_client, "tv", int(tmdb_id))
                if fallback and self._metadata_matches_media_name(
                    fallback, title, year
                ):
                    media_type = "tv"
                    metadata = fallback
            if not metadata:
                return item
            updated = {**item}
            updated["type"] = media_type
            for key, value in {
                "display_title": metadata.get("title") or metadata.get("name"),
                "original_title": metadata.get("original_title")
                or metadata.get("original_name"),
                "overview": metadata.get("overview"),
                "vote_average": metadata.get("vote_average"),
                "release_date": metadata.get("release_date")
                or metadata.get("first_air_date"),
                "poster_path": metadata.get("poster_path"),
                "poster_url": self._image_url(metadata.get("poster_path"), "w500"),
                "backdrop_path": metadata.get("backdrop_path"),
                "backdrop_url": self._image_url(
                    metadata.get("backdrop_path"), "w1280"
                ),
            }.items():
                if value not in (None, "", []):
                    updated[key] = value
            genres = [
                genre.get("name")
                for genre in metadata.get("genres", [])
                if genre.get("name")
            ]
            if genres:
                updated["genres"] = genres
            self._save_tmdb_cache()
            return updated
        finally:
            tmdb_client.close()

    def _infer_media_type_from_path(self, path: str) -> str | None:
        normalized = self.normalize_path(path)
        root = self.normalize_path(self.config.media_root)
        if root != "/" and normalized.startswith(f"{root}/"):
            relative = normalized[len(root) + 1 :]
        else:
            relative = normalized.lstrip("/")
        first_part = relative.split("/", 1)[0].strip()
        normalized_name = self._normalize_match_title(first_part)
        if not normalized_name:
            return None
        exact_type_map = {
            "电影": "movie",
            "剧集": "tv",
            "动漫": "tv",
            "综艺": "tv",
            "纪录片": "tv",
        }
        if first_part in exact_type_map:
            return exact_type_map[first_part]
        tv_keywords = (
            "tv",
            "show",
            "shows",
            "series",
            "drama",
            "anime",
            "documentary",
            "documentaries",
            "variety",
            "varietyshow",
            "电视剧",
            "剧集",
            "连续剧",
            "番剧",
            "动漫",
            "动画",
            "综艺",
            "纪录片",
            "纪录",
        )
        movie_keywords = ("movie", "movies", "film", "films", "电影", "影片")
        if any(keyword in normalized_name for keyword in tv_keywords):
            return "tv"
        if any(keyword in normalized_name for keyword in movie_keywords):
            return "movie"
        return None

    def _metadata_matches_media_name(
        self, metadata: dict[str, Any], title: str, year: int
    ) -> bool:
        release_date = metadata.get("release_date") or metadata.get("first_air_date")
        metadata_year = None
        if isinstance(release_date, str) and len(release_date) >= 4:
            try:
                metadata_year = int(release_date[:4])
            except ValueError:
                metadata_year = None
        if metadata_year and year and abs(metadata_year - year) > 1:
            return False
        metadata_title = str(
            metadata.get("title")
            or metadata.get("name")
            or metadata.get("original_title")
            or metadata.get("original_name")
            or ""
        )
        normalized_title = self._normalize_match_title(title)
        normalized_metadata_title = self._normalize_match_title(metadata_title)
        if normalized_title and normalized_metadata_title:
            return (
                normalized_title == normalized_metadata_title
                or normalized_title in normalized_metadata_title
                or normalized_metadata_title in normalized_title
            )
        return True

    @staticmethod
    def _normalize_match_title(value: str) -> str:
        return re.sub(r"\W+", "", value, flags=re.UNICODE).casefold()

    def _fetch_tmdb_metadata(
        self, tmdb_client: TMDbClient | None, media_type: str, tmdb_id: int
    ) -> dict[str, Any] | None:
        if not tmdb_client:
            return None
        cache_key = f"{media_type}:{tmdb_id}:{self.config.tmdb_language}"
        with self._tmdb_cache_lock:
            if cache_key in self.tmdb_cache:
                return self.tmdb_cache[cache_key]
        print(f"[scanner] TMDb fetch type={media_type} id={tmdb_id}")
        try:
            metadata = (
                tmdb_client.tv_details(tmdb_id, language=self.config.tmdb_language)
                if media_type == "tv"
                else tmdb_client.movie_details(
                    tmdb_id, language=self.config.tmdb_language
                )
            )
        except (TMDbAPIError, TMDbHTTPError) as exc:
            print(f"[scanner] TMDb fetch failed type={media_type} id={tmdb_id}: {exc}")
            return None
        with self._tmdb_cache_lock:
            self.tmdb_cache[cache_key] = metadata
        if self.db is not None and hasattr(self.db, "upsert_tmdb_cache"):
            try:
                self.db.upsert_tmdb_cache(cache_key, metadata)
            except Exception as exc:
                print(f"TMDb cache persist failed for {cache_key}: {exc}")
        return metadata

    def _ensure_openlist_auth(self, client: OpenListClient) -> None:
        if not self.config.openlist_username or not self.config.openlist_password:
            raise RuntimeError(
                "Set openlist.token or both openlist.username and openlist.password in config.yml."
            )
        if self.config.openlist_hash_login:
            token = client.login_hashed(
                self.config.openlist_username, self.config.openlist_password
            )
        else:
            token = client.login(
                self.config.openlist_username, self.config.openlist_password
            )
        if token:
            self.config.openlist_token = token

    def _refresh_openlist_auth(self, client: OpenListClient) -> None:
        with self._login_lock:
            client.set_token(None)
            self._ensure_openlist_auth(client)

    @staticmethod
    def _is_openlist_token_expired(exc: OpenListAPIError) -> bool:
        message = str(exc.message or "").strip().lower()
        return exc.code == 401 and "token" in message and "expired" in message

    def _list_dir(
        self, client: OpenListClient, path: str, *, refresh: bool = False
    ) -> list[dict[str, Any]]:
        last_error: OpenListHTTPError | None = None
        max_attempts = self.config.list_retry_count + 1
        auth_refreshed = False
        for attempt in range(1, max_attempts + 1):
            while True:
                try:
                    payload = client.list_dir(path, refresh=refresh)
                    if isinstance(payload, dict) and isinstance(
                        payload.get("content"), list
                    ):
                        return [
                            entry
                            for entry in payload["content"]
                            if isinstance(entry, dict) and entry.get("name")
                        ]
                    return []
                except OpenListAPIError as exc:
                    if self._is_openlist_token_expired(exc) and not auth_refreshed:
                        auth_refreshed = True
                        self._refresh_openlist_auth(client)
                        continue
                    raise
                except OpenListHTTPError as exc:
                    if 400 <= exc.status_code < 500:
                        raise
                    last_error = exc
                    if attempt < max_attempts:
                        delay = self.config.retry_delay_seconds * (2 ** (attempt - 1))
                        time.sleep(delay)
                    break
        if last_error:
            raise last_error
        return []

    def _handle_scan_error(self, path: str, exc: OpenListHTTPError) -> None:
        self.failed_paths.append(
            {"path": path, "status_code": exc.status_code, "message": exc.message}
        )
        if not self.config.skip_failed_directories:
            raise exc

    def _should_skip_dir(self, name: str) -> bool:
        return name in set(self.config.skip_directories)

    def _image_url(self, file_path: str | None, size: str) -> str | None:
        if not file_path or not self.tmdb_image_base_url:
            return None
        clean = file_path if file_path.startswith("/") else f"/{file_path}"
        return f"{self.tmdb_image_base_url}{size}{clean}"

    def _build_item_url(self, path: str) -> str | None:
        if not self.config.item_url_template:
            return None
        return self.config.item_url_template.replace("{path}", quote(path, safe="/"))

    def _load_tmdb_cache(self) -> dict[str, Any]:
        return {}

    def _save_tmdb_cache(self) -> None:
        return None

    @staticmethod
    def _is_dir(entry: dict[str, Any]) -> bool:
        return bool(entry.get("is_dir"))

    @staticmethod
    def _is_video(name: str) -> bool:
        return Path(name).suffix.lower() in VIDEO_SUFFIXES

    @staticmethod
    def _join_path(parent: str, name: str) -> str:
        if parent in ("", "/"):
            return f"/{name.strip('/')}"
        return f"{parent.rstrip('/')}/{name.strip('/')}"

    @staticmethod
    def _file_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
        season = item.get("season_number") or 10**6
        episode = item["episode_numbers"][0] if item.get("episode_numbers") else 10**6
        return season, episode, item["name"].lower()

    @staticmethod
    def normalize_path(path: str) -> str:
        if not path:
            return "/"
        return "/" + path.strip("/")

    @staticmethod
    def parent_path(path: str) -> str | None:
        clean = "/" + path.strip("/")
        if clean == "/":
            return None
        parent = clean.rsplit("/", 1)[0]
        return parent or "/"
