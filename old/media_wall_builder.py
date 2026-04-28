from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

from config_loader import get_value, load_config as load_yaml_config
from openlist_sdk import OpenListClient
from openlist_sdk.exceptions import OpenListHTTPError
from tmdb_sdk import TMDbAPIError, TMDbClient, TMDbHTTPError


MEDIA_PATTERN = re.compile(r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*\{tmdb-(?P<tmdb_id>\d+)\}\s*$")
SEASON_PATTERN = re.compile(r"^Season\s+(?P<number>\d+)$", re.IGNORECASE)
EPISODE_PATTERN = re.compile(r"S(?P<season>\d{1,2})E(?P<episode_start>\d{1,3})(?:-E?(?P<episode_end>\d{1,3}))?", re.IGNORECASE)
VIDEO_SUFFIXES = {".mp4", ".mkv", ".avi", ".ts", ".m2ts", ".mov", ".wmv", ".flv", ".mpg", ".mpeg"}


@dataclass
class BuildConfig:
    openlist_base_url: str
    openlist_token: str | None
    openlist_username: str | None
    openlist_password: str | None
    openlist_hash_login: bool
    media_root: str
    output_path: Path
    tmdb_read_access_token: str | None
    tmdb_api_key: str | None
    tmdb_language: str
    item_url_template: str | None
    list_retry_count: int
    retry_delay_seconds: float
    skip_failed_directories: bool
    max_media_items: int | None
    stop_after_path: str | None


class OpenListPosterWallBuilder:
    def __init__(self, config: BuildConfig) -> None:
        self.config = config
        self.tmdb_cache_path = Path(".cache") / "media_wall_tmdb_cache.json"
        self.tmdb_cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.tmdb_cache = self._load_tmdb_cache()
        self.tmdb_image_base_url: str | None = None

    def build(self) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        self.failed_paths: list[dict[str, Any]] = []
        self.scanned_media_count = 0
        root_path = self.config.stop_after_path or self.config.media_root
        with OpenListClient(self.config.openlist_base_url, token=self.config.openlist_token) as openlist:
            self._ensure_openlist_auth(openlist)

            tmdb_client: TMDbClient | None = None
            if self.config.tmdb_read_access_token or self.config.tmdb_api_key:
                tmdb_client = TMDbClient(
                    self.config.tmdb_read_access_token,
                    api_key=self.config.tmdb_api_key,
                )

            try:
                if tmdb_client:
                    self.tmdb_image_base_url = tmdb_client.configuration_details()["images"]["secure_base_url"]
                self._walk_category(openlist, tmdb_client, root_path, [], items)
            finally:
                if tmdb_client:
                    tmdb_client.close()

        items.sort(key=lambda item: (item["type"], item["title"].lower()))
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "media_root": root_path,
            "language": self.config.tmdb_language,
            "stats": {
                "item_count": len(items),
                "movie_count": sum(1 for item in items if item["type"] == "movie"),
                "tv_count": sum(1 for item in items if item["type"] == "tv"),
                "episode_count": sum(item.get("episode_count", 0) for item in items),
                "failed_path_count": len(self.failed_paths),
            },
            "failed_paths": self.failed_paths,
            "items": items,
        }
        self._save_tmdb_cache()
        self.config.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    def _walk_category(
        self,
        client: OpenListClient,
        tmdb_client: TMDbClient | None,
        current_path: str,
        category_parts: list[str],
        results: list[dict[str, Any]],
    ) -> None:
        try:
            entries = self._list_dir(client, current_path)
        except OpenListHTTPError as exc:
            self._handle_scan_error(current_path, exc)
            return

        for entry in entries:
            if self._should_stop():
                return
            if not self._is_dir(entry):
                continue

            name = entry["name"]
            path = self._join_path(current_path, name)
            media_match = MEDIA_PATTERN.match(name)
            if media_match:
                results.append(self._scan_media_directory(client, tmdb_client, path, category_parts, media_match))
                self.scanned_media_count += 1
                print(f"[scan] media #{self.scanned_media_count}: {path}")
                continue

            self._walk_category(client, tmdb_client, path, category_parts + [name], results)

    def _scan_media_directory(
        self,
        client: OpenListClient,
        tmdb_client: TMDbClient | None,
        media_path: str,
        category_parts: list[str],
        media_match: re.Match[str],
    ) -> dict[str, Any]:
        title = media_match.group("title").strip()
        year = int(media_match.group("year"))
        tmdb_id = int(media_match.group("tmdb_id"))
        top_level_entries = self._list_dir(client, media_path)

        files: list[dict[str, Any]] = []
        seasons: dict[int, dict[str, Any]] = {}
        for entry in top_level_entries:
            name = entry["name"]
            path = self._join_path(media_path, name)
            if self._is_dir(entry):
                season_match = SEASON_PATTERN.match(name)
                if season_match:
                    season_number = int(season_match.group("number"))
                    season_files = self._scan_files_recursive(client, path)
                    seasons[season_number] = {
                        "season_number": season_number,
                        "name": name,
                        "path": path,
                        "episodes": season_files,
                    }
                    files.extend(season_files)
                else:
                    files.extend(self._scan_files_recursive(client, path))
            elif self._is_video(name):
                files.append(self._make_file_entry(entry, media_path))

        media_type = "tv" if seasons or any(file["episode_numbers"] for file in files) else "movie"
        metadata = self._fetch_tmdb_metadata(tmdb_client, media_type, tmdb_id)
        if not metadata:
            fallback_type = "movie" if media_type == "tv" else "tv"
            fallback_metadata = self._fetch_tmdb_metadata(tmdb_client, fallback_type, tmdb_id)
            if fallback_metadata:
                media_type = fallback_type
                metadata = fallback_metadata

        if media_type == "tv" and not seasons:
            seasons = self._group_loose_episodes(files)

        season_list = [seasons[number] for number in sorted(seasons)]
        for season in season_list:
            season["episodes"].sort(key=lambda item: self._file_sort_key(item))

        files.sort(key=lambda item: self._file_sort_key(item))
        payload = {
            "title": title,
            "display_title": (metadata or {}).get("title") or (metadata or {}).get("name") or title,
            "original_title": (metadata or {}).get("original_title") or (metadata or {}).get("original_name"),
            "year": year,
            "type": media_type,
            "tmdb_id": tmdb_id,
            "overview": (metadata or {}).get("overview"),
            "vote_average": (metadata or {}).get("vote_average"),
            "genres": [genre.get("name") for genre in (metadata or {}).get("genres", []) if genre.get("name")],
            "release_date": (metadata or {}).get("release_date") or (metadata or {}).get("first_air_date"),
            "poster_path": (metadata or {}).get("poster_path"),
            "poster_url": self._image_url((metadata or {}).get("poster_path"), "w500"),
            "backdrop_path": (metadata or {}).get("backdrop_path"),
            "backdrop_url": self._image_url((metadata or {}).get("backdrop_path"), "w1280"),
            "category_path": category_parts,
            "category_label": " / ".join(category_parts),
            "openlist_path": media_path,
            "openlist_url": self._build_item_url(media_path),
            "file_count": len(files),
            "season_count": len(season_list),
            "episode_count": sum(len(season["episodes"]) for season in season_list),
            "files": files,
            "seasons": season_list,
        }
        return payload

    def _scan_files_recursive(self, client: OpenListClient, current_path: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        try:
            entries = self._list_dir(client, current_path)
        except OpenListHTTPError as exc:
            self._handle_scan_error(current_path, exc)
            return results

        for entry in entries:
            name = entry["name"]
            path = self._join_path(current_path, name)
            if self._is_dir(entry):
                results.extend(self._scan_files_recursive(client, path))
            elif self._is_video(name):
                results.append(self._make_file_entry(entry, current_path))
        return results

    def _make_file_entry(self, entry: dict[str, Any], parent_path: str) -> dict[str, Any]:
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

    def _group_loose_episodes(self, files: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
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
        self,
        tmdb_client: TMDbClient | None,
        media_type: str,
        tmdb_id: int,
    ) -> dict[str, Any] | None:
        if not tmdb_client:
            return None

        cache_key = f"{media_type}:{tmdb_id}:{self.config.tmdb_language}"
        if cache_key in self.tmdb_cache:
            return self.tmdb_cache[cache_key]

        try:
            if media_type == "tv":
                metadata = tmdb_client.tv_details(tmdb_id, language=self.config.tmdb_language)
            else:
                metadata = tmdb_client.movie_details(tmdb_id, language=self.config.tmdb_language)
        except (TMDbAPIError, TMDbHTTPError):
            return None

        self.tmdb_cache[cache_key] = metadata
        return metadata

    def _ensure_openlist_auth(self, client: OpenListClient) -> None:
        if client.token:
            return
        if not self.config.openlist_username or not self.config.openlist_password:
            raise RuntimeError("Set openlist.token or both openlist.username and openlist.password in config.yml.")
        if self.config.openlist_hash_login:
            client.login_hashed(self.config.openlist_username, self.config.openlist_password)
        else:
            client.login(self.config.openlist_username, self.config.openlist_password)

    def _list_dir(self, client: OpenListClient, path: str) -> list[dict[str, Any]]:
        last_error: OpenListHTTPError | None = None
        for attempt in range(1, self.config.list_retry_count + 2):
            try:
                payload = client.list_dir(path)
                if isinstance(payload, dict) and isinstance(payload.get("content"), list):
                    return [entry for entry in payload["content"] if isinstance(entry, dict) and entry.get("name")]
                return []
            except OpenListHTTPError as exc:
                last_error = exc
                print(f"[scan] list_dir failed (attempt {attempt}) {path}: HTTP {exc.status_code}")
                if attempt < self.config.list_retry_count + 1:
                    time.sleep(self.config.retry_delay_seconds)

        if last_error is not None:
            raise last_error
        return []

    def _handle_scan_error(self, path: str, exc: OpenListHTTPError) -> None:
        self.failed_paths.append(
            {
                "path": path,
                "status_code": exc.status_code,
                "message": exc.message,
            }
        )
        print(f"[scan] skipped {path}: HTTP {exc.status_code} {exc.message}")
        if not self.config.skip_failed_directories:
            raise exc

    def _should_stop(self) -> bool:
        limit = self.config.max_media_items
        return limit is not None and self.scanned_media_count >= limit

    def _image_url(self, file_path: str | None, size: str) -> str | None:
        if not file_path or not self.tmdb_image_base_url:
            return None
        clean_path = file_path if file_path.startswith("/") else f"/{file_path}"
        return f"{self.tmdb_image_base_url}{size}{clean_path}"

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
        self.tmdb_cache_path.write_text(json.dumps(self.tmdb_cache, ensure_ascii=False, indent=2), encoding="utf-8")

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
    def _is_dir(entry: dict[str, Any]) -> bool:
        return bool(entry.get("is_dir"))

    @staticmethod
    def _is_video(name: str) -> bool:
        return Path(name).suffix.lower() in VIDEO_SUFFIXES


def load_config() -> BuildConfig:
    config = load_yaml_config()
    return BuildConfig(
        openlist_base_url=_string_value(get_value(config, "openlist", "base_url")),
        openlist_token=_optional_string(get_value(config, "openlist", "token")),
        openlist_username=_optional_string(get_value(config, "openlist", "username")),
        openlist_password=_optional_string(get_value(config, "openlist", "password")),
        openlist_hash_login=bool(get_value(config, "openlist", "hash_login", default=False)),
        media_root=_string_value(get_value(config, "media_wall", "media_root", default="/影视资源"), "/影视资源"),
        output_path=Path(_string_value(get_value(config, "media_wall", "output", default="media_wall_site/data/library.json"), "media_wall_site/data/library.json")),
        tmdb_read_access_token=_optional_string(get_value(config, "tmdb", "read_access_token")),
        tmdb_api_key=_optional_string(get_value(config, "tmdb", "api_key")),
        tmdb_language=_string_value(get_value(config, "tmdb", "language", default="zh-CN"), "zh-CN"),
        item_url_template=_optional_string(get_value(config, "media_wall", "item_url_template")),
        list_retry_count=int(get_value(config, "media_wall", "list_retry_count", default=2)),
        retry_delay_seconds=float(get_value(config, "media_wall", "retry_delay_seconds", default=1.0)),
        skip_failed_directories=bool(get_value(config, "media_wall", "skip_failed_directories", default=True)),
        max_media_items=_optional_int(get_value(config, "media_wall", "max_media_items")),
        stop_after_path=_optional_string(get_value(config, "media_wall", "stop_after_path")),
    )


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_value(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return text or default


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def main() -> int:
    config = load_config()
    if not config.openlist_base_url:
        raise RuntimeError("Missing openlist.base_url in config.yml.")

    builder = OpenListPosterWallBuilder(config)
    payload = builder.build()
    print(f"Built poster wall data: {payload['stats']['item_count']} items -> {config.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
