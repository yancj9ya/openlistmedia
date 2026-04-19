from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MediaQueryOptions:
    category_path: str | None = None
    include_descendants: bool = False
    year: int | None = None
    page: int = 1
    page_size: int = 20
    keyword: str | None = None
    media_type: str | None = None
    sort_by: str = "updated_at"
    sort_order: str = "desc"


@dataclass
class MediaQueryResult:
    items: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class MediaWallDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS category_cache (
                    category_path TEXT PRIMARY KEY,
                    category_name TEXT NOT NULL,
                    parent_path TEXT,
                    payload_json TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    scanned_at INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS media_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_path TEXT NOT NULL,
                    media_path TEXT NOT NULL,
                    tmdb_id INTEGER NOT NULL,
                    media_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    display_title TEXT,
                    original_title TEXT,
                    release_date TEXT,
                    vote_average REAL,
                    updated_at INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    sort_title TEXT,
                    search_text TEXT,
                    year INTEGER,
                    poster_url TEXT,
                    backdrop_url TEXT,
                    category_label TEXT,
                    UNIQUE(category_path, media_path)
                )
                """
            )
            self._ensure_column(conn, "media_items", "display_title", "TEXT")
            self._ensure_column(conn, "media_items", "original_title", "TEXT")
            self._ensure_column(conn, "media_items", "release_date", "TEXT")
            self._ensure_column(conn, "media_items", "vote_average", "REAL")
            self._ensure_column(conn, "media_items", "sort_title", "TEXT")
            self._ensure_column(conn, "media_items", "search_text", "TEXT")
            self._ensure_column(conn, "media_items", "year", "INTEGER")
            self._ensure_column(conn, "media_items", "poster_url", "TEXT")
            self._ensure_column(conn, "media_items", "backdrop_url", "TEXT")
            self._ensure_column(conn, "media_items", "category_label", "TEXT")
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_media_items_category_path
                ON media_items(category_path)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_media_items_sort_title
                ON media_items(sort_title)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_media_items_tmdb_id
                ON media_items(tmdb_id)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS play_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_id INTEGER NOT NULL,
                    media_title TEXT NOT NULL,
                    media_type TEXT,
                    tmdb_id INTEGER,
                    release_year INTEGER,
                    poster_url TEXT,
                    played_at INTEGER NOT NULL,
                    FOREIGN KEY(media_id) REFERENCES media_items(id) ON DELETE CASCADE
                )
                """
            )
            self._ensure_column(conn, "play_history", "tmdb_id", "INTEGER")
            self._ensure_column(conn, "play_history", "release_year", "INTEGER")
            conn.execute(
                """
                DELETE FROM play_history
                WHERE tmdb_id IS NULL
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_play_history_played_at
                ON play_history(played_at DESC)
                """
            )
            conn.commit()

    def _ensure_column(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_type: str,
    ) -> None:
        columns = {
            row["name"]
            for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            conn.execute(
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            )

    def get_category_cache(self, category_path: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json, scanned_at FROM category_cache WHERE category_path = ?",
                (category_path,),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload_json"])
        payload["scanned_at"] = row["scanned_at"]
        return payload

    def list_category_caches(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT category_path, category_name, parent_path, item_count, scanned_at
                FROM category_cache
                ORDER BY category_path ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_category_cache(
        self,
        category_path: str,
        category_name: str,
        parent_path: str | None,
        payload: dict[str, Any],
    ) -> None:
        scanned_at = int(time.time())
        item_count = len(payload.get("items", []))
        payload_json = json.dumps(payload, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO category_cache(category_path, category_name, parent_path, payload_json, item_count, scanned_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(category_path) DO UPDATE SET
                    category_name = excluded.category_name,
                    parent_path = excluded.parent_path,
                    payload_json = excluded.payload_json,
                    item_count = excluded.item_count,
                    scanned_at = excluded.scanned_at
                """,
                (
                    category_path,
                    category_name,
                    parent_path,
                    payload_json,
                    item_count,
                    scanned_at,
                ),
            )
            incoming_paths = [
                str(item.get("openlist_path") or "").strip()
                for item in payload.get("items", [])
                if str(item.get("openlist_path") or "").strip()
            ]
            if incoming_paths:
                placeholders = ", ".join("?" for _ in incoming_paths)
                conn.execute(
                    f"DELETE FROM media_items WHERE category_path = ? AND media_path NOT IN ({placeholders})",
                    (category_path, *incoming_paths),
                )
            else:
                conn.execute(
                    "DELETE FROM media_items WHERE category_path = ?", (category_path,)
                )
            for item in payload.get("items", []):
                media_path = str(item.get("openlist_path") or "").strip()
                if not media_path:
                    continue
                conn.execute(
                    """
                    INSERT INTO media_items(
                        category_path,
                        media_path,
                        tmdb_id,
                        media_type,
                        title,
                        display_title,
                        original_title,
                        release_date,
                        vote_average,
                        updated_at,
                        payload_json,
                        sort_title,
                        search_text,
                        year,
                        poster_url,
                        backdrop_url,
                        category_label
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(category_path, media_path) DO UPDATE SET
                        tmdb_id = excluded.tmdb_id,
                        media_type = excluded.media_type,
                        title = excluded.title,
                        display_title = excluded.display_title,
                        original_title = excluded.original_title,
                        release_date = excluded.release_date,
                        vote_average = excluded.vote_average,
                        updated_at = excluded.updated_at,
                        payload_json = excluded.payload_json,
                        sort_title = excluded.sort_title,
                        search_text = excluded.search_text,
                        year = excluded.year,
                        poster_url = excluded.poster_url,
                        backdrop_url = excluded.backdrop_url,
                        category_label = excluded.category_label
                    """,
                    (
                        category_path,
                        media_path,
                        item.get("tmdb_id"),
                        item.get("type"),
                        item.get("title"),
                        item.get("display_title"),
                        item.get("original_title"),
                        item.get("release_date"),
                        item.get("vote_average"),
                        scanned_at,
                        json.dumps(item, ensure_ascii=False),
                        str(
                            item.get("display_title") or item.get("title") or ""
                        ).lower(),
                        " ".join(
                            part.lower()
                            for part in [
                                item.get("title"),
                                item.get("display_title"),
                                item.get("original_title"),
                                item.get("category_label"),
                            ]
                            if part
                        ),
                        item.get("year"),
                        item.get("poster_url"),
                        item.get("backdrop_url"),
                        item.get("category_label"),
                    ),
                )
            conn.commit()

    def replace_media_item(
        self, category_path: str, media_path: str, item: dict[str, Any]
    ) -> None:
        cached = self.get_category_cache(category_path)
        if not cached:
            raise ValueError(f"Category cache not found: {category_path}")
        items = list(cached.get("items") or [])
        updated = False
        for index, existing in enumerate(items):
            if str(existing.get("openlist_path") or "").strip() != media_path:
                continue
            items[index] = item
            updated = True
            break
        if not updated:
            items.append(item)
        cached["items"] = items
        stats = dict(cached.get("stats") or {})
        stats["item_count"] = len(items)
        stats["movie_count"] = sum(1 for entry in items if entry.get("type") == "movie")
        stats["tv_count"] = sum(1 for entry in items if entry.get("type") == "tv")
        stats["episode_count"] = sum(
            int(entry.get("episode_count") or 0) for entry in items
        )
        cached["stats"] = stats
        self.upsert_category_cache(
            category_path=category_path,
            category_name=str(
                cached.get("category_name")
                or category_path.rstrip("/").split("/")[-1]
                or "/"
            ),
            parent_path=cached.get("parent_path"),
            payload=cached,
        )

    def clear_all_cache(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM media_items")
            conn.execute("DELETE FROM category_cache")
            conn.commit()

    def cache_is_fresh(self, category_path: str, ttl_seconds: int) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT scanned_at FROM category_cache WHERE category_path = ?",
                (category_path,),
            ).fetchone()
        if not row:
            return False
        return int(time.time()) - int(row["scanned_at"]) < ttl_seconds

    def category_cache_exists(self, category_path: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM category_cache WHERE category_path = ? LIMIT 1",
                (category_path,),
            ).fetchone()
        return row is not None

    def query_media_items(self, options: MediaQueryOptions) -> MediaQueryResult:
        page = max(options.page, 1)
        page_size = min(max(options.page_size, 1), 100)
        where_clauses: list[str] = []
        params: list[Any] = []
        if options.category_path:
            if options.include_descendants:
                where_clauses.append("(category_path = ? OR category_path LIKE ?)")
                params.extend(
                    [options.category_path, f"{options.category_path.rstrip('/')}/%"]
                )
            else:
                where_clauses.append("category_path = ?")
                params.append(options.category_path)
        if options.keyword:
            where_clauses.append("search_text LIKE ?")
            params.append(f"%{options.keyword.lower()}%")
        if options.media_type in {"movie", "tv"}:
            where_clauses.append("media_type = ?")
            params.append(options.media_type)
        if options.year is not None:
            where_clauses.append("year = ?")
            params.append(options.year)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        order_map = {
            "title": "sort_title",
            "year": "year",
            "rating": "vote_average",
            "updated_at": "updated_at",
        }
        order_column = order_map.get(options.sort_by, "updated_at")
        direction = "ASC" if str(options.sort_order).lower() == "asc" else "DESC"
        with self._connect() as conn:
            total = conn.execute(
                f"SELECT COUNT(1) AS count FROM media_items {where_sql}",
                params,
            ).fetchone()["count"]
            rows = conn.execute(
                f"""
                SELECT id, category_path, media_path, tmdb_id, media_type, title, display_title, original_title,
                       release_date, vote_average, updated_at, payload_json, year, poster_url, backdrop_url, category_label
                FROM media_items
                {where_sql}
                ORDER BY {order_column} {direction}, id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        items = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            payload["updated_at"] = row["updated_at"]
            payload["db_id"] = row["id"]
            items.append(payload)
        return MediaQueryResult(
            items=items, total=int(total), page=page, page_size=page_size
        )

    def list_available_years(
        self,
        category_path: str | None,
        include_descendants: bool,
    ) -> list[int]:
        where_clauses: list[str] = ["year IS NOT NULL"]
        params: list[Any] = []
        if category_path:
            if include_descendants:
                where_clauses.append("(category_path = ? OR category_path LIKE ?)")
                params.extend([category_path, f"{category_path.rstrip('/')}/%"])
            else:
                where_clauses.append("category_path = ?")
                params.append(category_path)
        where_sql = f"WHERE {' AND '.join(where_clauses)}"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT DISTINCT year FROM media_items {where_sql} ORDER BY year DESC",
                params,
            ).fetchall()
        return [int(row["year"]) for row in rows if row["year"] is not None]

    def get_media_item(self, media_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, category_path, payload_json, updated_at FROM media_items WHERE id = ?",
                (media_id,),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload_json"])
        payload["updated_at"] = row["updated_at"]
        payload["db_id"] = row["id"]
        payload["category_path"] = row["category_path"]
        return payload

    def record_play_history(
        self,
        media_id: int,
        media_title: str,
        media_type: str | None = None,
        poster_url: str | None = None,
        tmdb_id: int | None = None,
        release_year: int | None = None,
    ) -> None:
        played_at = int(time.time())
        with self._connect() as conn:
            if tmdb_id is not None:
                conn.execute(
                    """
                    DELETE FROM play_history
                    WHERE tmdb_id = ?
                       OR (
                            tmdb_id IS NULL
                        AND media_title = ?
                        AND COALESCE(media_type, '') = COALESCE(?, '')
                        AND (
                              release_year = ?
                           OR (release_year IS NULL AND ? IS NULL)
                        )
                       )
                    """,
                    (tmdb_id, media_title, media_type, release_year, release_year),
                )
            else:
                conn.execute(
                    """
                    DELETE FROM play_history
                    WHERE media_title = ?
                      AND COALESCE(media_type, '') = COALESCE(?, '')
                      AND (
                        release_year = ?
                        OR (release_year IS NULL AND ? IS NULL)
                      )
                    """,
                    (media_title, media_type, release_year, release_year),
                )
            conn.execute(
                """
                INSERT INTO play_history(media_id, media_title, media_type, tmdb_id, release_year, poster_url, played_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    media_id,
                    media_title,
                    media_type,
                    tmdb_id,
                    release_year,
                    poster_url,
                    played_at,
                ),
            )
            conn.commit()

    def get_recent_play_history(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT recent.id,
                       COALESCE(current_media.id, recent.media_id) AS media_id,
                       recent.media_title,
                       recent.media_type,
                       recent.effective_tmdb_id AS tmdb_id,
                       recent.effective_release_year AS release_year,
                       COALESCE(current_media.poster_url, recent.poster_url) AS poster_url,
                       recent.played_at,
                       current_media.vote_average
                FROM (
                    SELECT ph.id,
                           ph.media_id,
                           ph.media_title,
                           ph.media_type,
                           COALESCE(ph.tmdb_id, mi.tmdb_id) AS effective_tmdb_id,
                           COALESCE(ph.release_year, mi.year) AS effective_release_year,
                           ph.poster_url,
                           ph.played_at
                    FROM play_history ph
                    LEFT JOIN media_items mi ON mi.id = ph.media_id
                    INNER JOIN (
                        SELECT COALESCE(
                                   CAST(COALESCE(ph2.tmdb_id, mi2.tmdb_id) AS TEXT),
                                   COALESCE(ph2.media_type, '') || '|' || ph2.media_title || '|' || COALESCE(CAST(COALESCE(ph2.release_year, mi2.year) AS TEXT), '')
                               ) AS identity_key,
                               MAX(ph2.played_at) AS latest_played_at
                        FROM play_history ph2
                        LEFT JOIN media_items mi2 ON mi2.id = ph2.media_id
                        GROUP BY COALESCE(
                                   CAST(COALESCE(ph2.tmdb_id, mi2.tmdb_id) AS TEXT),
                                   COALESCE(ph2.media_type, '') || '|' || ph2.media_title || '|' || COALESCE(CAST(COALESCE(ph2.release_year, mi2.year) AS TEXT), '')
                               )
                    ) latest
                      ON latest.identity_key = COALESCE(
                           CAST(COALESCE(ph.tmdb_id, mi.tmdb_id) AS TEXT),
                           COALESCE(ph.media_type, '') || '|' || ph.media_title || '|' || COALESCE(CAST(COALESCE(ph.release_year, mi.year) AS TEXT), '')
                      )
                     AND latest.latest_played_at = ph.played_at
                ) recent
                LEFT JOIN media_items current_media
                  ON (
                       recent.effective_tmdb_id IS NOT NULL
                   AND current_media.tmdb_id = recent.effective_tmdb_id
                  )
                  OR (
                       recent.effective_tmdb_id IS NULL
                   AND current_media.title = recent.media_title
                   AND COALESCE(current_media.media_type, '') = COALESCE(recent.media_type, '')
                   AND (
                        current_media.year = recent.effective_release_year
                        OR (current_media.year IS NULL AND recent.effective_release_year IS NULL)
                   )
                  )
                ORDER BY recent.played_at DESC, recent.id DESC, current_media.updated_at DESC, current_media.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_media_item_by_path(
        self, category_path: str, media_path: str
    ) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, category_path, payload_json, updated_at
                FROM media_items
                WHERE category_path = ? AND media_path = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (category_path, media_path),
            ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload_json"])
        payload["updated_at"] = row["updated_at"]
        payload["db_id"] = row["id"]
        payload["category_path"] = row["category_path"]
        return payload
