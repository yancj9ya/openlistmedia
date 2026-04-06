from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from openlist_sdk import OpenListClient
from openlist_sdk.exceptions import OpenListHTTPError
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
    def __init__(self, config: MediaWallConfig) -> None:
        self.config = config
        self.tmdb_cache_path = Path(".cache") / "media_wall_tmdb_cache.json"
        self.tmdb_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.tmdb_cache = self._load_tmdb_cache()
        self.tmdb_image_base_url: str | None = None
        self.failed_paths: list[dict[str, Any]] = []

    def list_categories(
        self, base_path: str | None = None, *, refresh: bool = False
    ) -> dict[str, Any]:
        root = self.normalize_path(base_path or self.config.media_root)
        with OpenListClient(
            self.config.openlist_base_url, token=self.config.openlist_token
        ) as client:
            self._ensure_openlist_auth(client)
            return {
                "path": root,
                "parent_path": self.parent_path(root),
                "entries": self._list_categories(client, root, refresh=refresh),
            }

    def scan_category(
        self, category_path: str, *, refresh: bool = False
    ) -> dict[str, Any]:
        category_path = self.normalize_path(category_path)
        category_name = (
            category_path.rstrip("/").split("/")[-1] if category_path != "/" else "/"
        )
        with OpenListClient(
            self.config.openlist_base_url, token=self.config.openlist_token
        ) as openlist:
            self._ensure_openlist_auth(openlist)
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
        payload = {
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
        self._save_tmdb_cache()
        return payload

    def scan_media_item(
        self, media_path: str, *, refresh: bool = False
    ) -> dict[str, Any]:
        media_path = self.normalize_path(media_path)
        media_name = media_path.rstrip("/").split("/")[-1] if media_path != "/" else "/"
        media_match = MEDIA_PATTERN.match(media_name)
        if not media_match:
            raise ValueError("Invalid media_path: expected a media directory name.")
        category_path = self.parent_path(media_path)
        if not category_path:
            raise ValueError("Invalid media_path: missing parent category path.")
        with OpenListClient(
            self.config.openlist_base_url, token=self.config.openlist_token
        ) as openlist:
            self._ensure_openlist_auth(openlist)
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
        results: list[dict[str, Any]] = []
        for entry in self._list_dir(client, current_path, refresh=refresh):
            if not self._is_dir(entry):
                continue
            name = entry["name"]
            if self._should_skip_dir(name):
                continue
            path = self._join_path(current_path, name)
            if MEDIA_PATTERN.match(name):
                continue
            category_count, media_count = self._count_directory_summary(
                client, path, refresh=refresh
            )
            results.append(
                {
                    "name": name,
                    "path": path,
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

    def _scan_category_items(
        self,
        client: OpenListClient,
        tmdb_client: TMDbClient | None,
        category_path: str,
        *,
        refresh: bool = False,
    ) -> list[dict[str, Any]]:
        self.failed_paths = []
        items: list[dict[str, Any]] = []
        for entry in self._list_dir(client, category_path, refresh=refresh):
            if not self._is_dir(entry):
                continue
            name = entry["name"]
            if self._should_skip_dir(name):
                continue
            path = self._join_path(category_path, name)
            media_match = MEDIA_PATTERN.match(name)
            if media_match:
                items.append(
                    self._scan_media_directory(
                        client,
                        tmdb_client,
                        path,
                        [category_path.rstrip("/").split("/")[-1]],
                        media_match,
                        refresh=refresh,
                    )
                )
        return items

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
        top_level_entries = self._list_dir(client, media_path, refresh=refresh)
        files: list[dict[str, Any]] = []
        seasons: dict[int, dict[str, Any]] = {}
        for entry in top_level_entries:
            name = entry["name"]
            path = self._join_path(media_path, name)
            if self._is_dir(entry):
                season_match = SEASON_PATTERN.match(name)
                if season_match:
                    season_number = int(season_match.group("number"))
                    season_files = self._scan_files_recursive(
                        client, path, refresh=refresh
                    )
                    seasons[season_number] = {
                        "season_number": season_number,
                        "name": name,
                        "path": path,
                        "episodes": season_files,
                    }
                    files.extend(season_files)
                else:
                    files.extend(
                        self._scan_files_recursive(client, path, refresh=refresh)
                    )
            elif self._is_video(name):
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

    def _fetch_tmdb_metadata(
        self, tmdb_client: TMDbClient | None, media_type: str, tmdb_id: int
    ) -> dict[str, Any] | None:
        if not tmdb_client:
            return None
        cache_key = f"{media_type}:{tmdb_id}:{self.config.tmdb_language}"
        if cache_key in self.tmdb_cache:
            return self.tmdb_cache[cache_key]
        try:
            metadata = (
                tmdb_client.tv_details(tmdb_id, language=self.config.tmdb_language)
                if media_type == "tv"
                else tmdb_client.movie_details(
                    tmdb_id, language=self.config.tmdb_language
                )
            )
        except (TMDbAPIError, TMDbHTTPError):
            return None
        self.tmdb_cache[cache_key] = metadata
        return metadata

    def _ensure_openlist_auth(self, client: OpenListClient) -> None:
        if client.token:
            return
        if not self.config.openlist_username or not self.config.openlist_password:
            raise RuntimeError(
                "Set openlist.token or both openlist.username and openlist.password in config.yml."
            )
        if self.config.openlist_hash_login:
            client.login_hashed(
                self.config.openlist_username, self.config.openlist_password
            )
        else:
            client.login(self.config.openlist_username, self.config.openlist_password)

    def _list_dir(
        self, client: OpenListClient, path: str, *, refresh: bool = False
    ) -> list[dict[str, Any]]:
        last_error: OpenListHTTPError | None = None
        for attempt in range(1, self.config.list_retry_count + 2):
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
            except OpenListHTTPError as exc:
                last_error = exc
                if attempt < self.config.list_retry_count + 1:
                    time.sleep(self.config.retry_delay_seconds)
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
        if not self.tmdb_cache_path.exists():
            return {}
        try:
            return json.loads(self.tmdb_cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _save_tmdb_cache(self) -> None:
        self.tmdb_cache_path.write_text(
            json.dumps(self.tmdb_cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )

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
