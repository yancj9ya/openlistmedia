from __future__ import annotations

from typing import Any


def to_category_tree_dto(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": payload.get("path"),
        "parent_path": payload.get("parent_path"),
        "root": payload.get("root"),
        "children": payload.get("children", []),
        "skip_directories": payload.get("skip_directories", []),
    }


def to_media_list_item_dto(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("db_id"),
        "tmdb_id": item.get("tmdb_id"),
        "title": item.get("title"),
        "display_title": item.get("display_title"),
        "original_title": item.get("original_title"),
        "year": item.get("year"),
        "type": item.get("type"),
        "overview": item.get("overview"),
        "vote_average": item.get("vote_average"),
        "poster_url": item.get("poster_url"),
        "backdrop_url": item.get("backdrop_url"),
        "release_date": item.get("release_date"),
        "category_label": item.get("category_label"),
        "category_path": item.get("category_path"),
        "openlist_path": item.get("openlist_path"),
        "openlist_url": item.get("openlist_url"),
        "updated_at": item.get("updated_at"),
    }


def to_media_detail_dto(item: dict[str, Any]) -> dict[str, Any]:
    files = []
    for file_item in item.get("files") or []:
        files.append(
            {
                "name": file_item.get("name"),
                "path": file_item.get("path"),
                "episode_numbers": file_item.get("episode_numbers") or [],
                "openlist_url": file_item.get("openlist_url"),
                "direct_url": file_item.get("direct_url"),
                "mpv_url": file_item.get("mpv_url"),
            }
        )

    seasons = []
    for season in item.get("seasons") or []:
        seasons.append(
            {
                "season_number": season.get("season_number"),
                "name": season.get("name"),
                "episodes": [
                    {
                        "name": episode.get("name"),
                        "path": episode.get("path"),
                        "episode_numbers": episode.get("episode_numbers") or [],
                        "openlist_url": episode.get("openlist_url"),
                        "direct_url": episode.get("direct_url"),
                        "mpv_url": episode.get("mpv_url"),
                    }
                    for episode in season.get("episodes") or []
                ],
            }
        )

    return {
        **to_media_list_item_dto(item),
        "genres": item.get("genres") or [],
        "file_count": item.get("file_count") or 0,
        "season_count": item.get("season_count") or 0,
        "episode_count": item.get("episode_count") or 0,
        "direct_url": item.get("direct_url"),
        "mpv_url": item.get("mpv_url"),
        "files": files,
        "seasons": seasons,
    }
