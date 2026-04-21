from __future__ import annotations

from urllib.parse import parse_qs

from backend.dto.media_dto import (
    to_category_tree_dto,
    to_media_detail_dto,
    to_media_list_item_dto,
)
from backend.dto.responses import RawResponse, error_response, ok_response, paginated_response


class MediaRoutes:
    def __init__(
        self, service, api_prefix: str, admin_token: str | None = None
    ) -> None:
        self.service = service
        self.api_prefix = api_prefix.rstrip("/")
        self.admin_token = admin_token

    def handle(self, path: str, query: str, headers) -> tuple[int, dict]:
        if path == f"{self.api_prefix}/health":
            return 200, ok_response(self.service.health())
        if path == f"{self.api_prefix}/categories":
            params = parse_qs(query)
            category_path = (params.get("path") or [None])[0]
            payload = self.service.get_category_tree(category_path)
            return 200, ok_response(to_category_tree_dto(payload))
        if path == f"{self.api_prefix}/settings":
            passcode = headers.get("X-Access-Passcode")
            if not self.service.is_admin_passcode(passcode):
                return error_response("forbidden", "Admin passcode required.", 403)
            return 200, ok_response(self.service.get_settings())
        if path == f"{self.api_prefix}/media":
            params = parse_qs(query)
            page = self._parse_int((params.get("page") or ["1"])[0], default=1)
            page_size = self._parse_int(
                (params.get("page_size") or ["20"])[0], default=20
            )
            category_path = (params.get("category_path") or [None])[0]
            include_descendants = (params.get("include_descendants") or ["0"])[0] == "1"
            year = self._parse_int((params.get("year") or [""])[0], default=0) or None
            keyword = (params.get("keyword") or [None])[0]
            media_type = (params.get("type") or [None])[0]
            sort_by = (params.get("sort_by") or ["updated_at"])[0]
            sort_order = (params.get("sort_order") or ["desc"])[0]
            payload = self.service.get_media_list(
                category_path,
                include_descendants,
                year,
                page,
                page_size,
                keyword,
                media_type,
                sort_by,
                sort_order,
            )
            response = paginated_response(
                [to_media_list_item_dto(item) for item in payload["items"]],
                payload["total"],
                payload["page"],
                payload["page_size"],
            )
            response["data"]["years"] = payload.get("years", [])
            return 200, response
        if path.startswith(f"{self.api_prefix}/media/") and path.endswith(
            "/last-episode"
        ):
            media_id_text = path[len(f"{self.api_prefix}/media/") : -len("/last-episode")]
            media_id = self._parse_int(media_id_text, default=0)
            if media_id <= 0:
                return error_response("bad_request", "Invalid media id.", 400)
            payload = self.service.get_last_played_episode(media_id)
            if payload is None:
                return error_response("not_found", "No last played episode.", 404)
            return 200, ok_response(payload)
        if path.startswith(f"{self.api_prefix}/media/"):
            media_id_text = path.rsplit("/", 1)[-1]
            media_id = self._parse_int(media_id_text, default=0)
            if media_id <= 0:
                return error_response("bad_request", "Invalid media id.", 400)
            payload = self.service.get_media_detail(media_id)
            if payload is None:
                return error_response("not_found", "Media item not found.", 404)
            return 200, ok_response(to_media_detail_dto(payload))
        if path == f"{self.api_prefix}/refresh":
            if self.admin_token and headers.get("X-Admin-Token") != self.admin_token:
                return error_response("forbidden", "Invalid admin token.", 403)
            return 200, ok_response(
                {"message": "Use POST /refresh with category_path or media_path."}
            )
        if path == f"{self.api_prefix}/recent-plays":
            payload = self.service.get_recent_play_history(limit=10)
            return 200, ok_response(payload)
        if path.startswith(f"{self.api_prefix}/playlist/") and path.endswith(".m3u"):
            playlist_id = path[len(f"{self.api_prefix}/playlist/") : -len(".m3u")]
            if not playlist_id:
                return error_response("bad_request", "Missing playlist id.", 400)
            text = self.service.get_playlist(playlist_id)
            if text is None:
                return error_response("not_found", "Playlist not found or expired.", 404)
            return 200, RawResponse(
                body=text.encode("utf-8"), content_type="audio/x-mpegurl; charset=utf-8"
            )
        return error_response("not_found", "Route not found.", 404)

    def handle_post(self, path: str, payload: dict, headers) -> tuple[int, dict]:
        if path == f"{self.api_prefix}/record-play":
            media_id = payload.get("media_id")
            if not media_id:
                return error_response("bad_request", "Missing field: media_id", 400)
            file_path = payload.get("file_path")
            file_path = str(file_path).strip() if file_path else None
            try:
                self.service.record_play_history(int(media_id), file_path or None)
                return 200, ok_response({"recorded": True})
            except (ValueError, TypeError):
                return error_response("bad_request", "Invalid media_id", 400)
        if path == f"{self.api_prefix}/auth/login":
            passcode = str(payload.get("passcode") or "").strip()
            if not passcode:
                return error_response("bad_request", "Missing field: passcode", 400)
            authenticated = self.service.authenticate_access(passcode)
            if not authenticated:
                return error_response("forbidden", "Invalid passcode.", 403)
            return 200, ok_response(authenticated)
        if path == f"{self.api_prefix}/play-link":
            media_path = str(payload.get("path") or "").strip()
            if not media_path:
                return error_response("bad_request", "Missing field: path", 400)
            return 200, ok_response(self.service.get_play_link(media_path))
        if path == f"{self.api_prefix}/playlist":
            raw_paths = payload.get("paths")
            if not isinstance(raw_paths, list) or not raw_paths:
                return error_response(
                    "bad_request", "Missing or invalid field: paths", 400
                )
            try:
                result = self.service.create_playlist([str(p) for p in raw_paths])
            except ValueError as exc:
                return error_response("bad_request", str(exc), 400)
            return 200, ok_response(result)
        if path == f"{self.api_prefix}/settings":
            passcode = headers.get("X-Access-Passcode")
            if not self.service.is_admin_passcode(passcode):
                return error_response("forbidden", "Admin passcode required.", 403)
            try:
                result = self.service.update_settings(payload)
            except ValueError as exc:
                return error_response("bad_request", str(exc), 400)
            return 200, ok_response(
                {
                    "settings": result["saved"],
                    "restart_required": result["restart_required"],
                    "changed_fields": result["changed_fields"],
                },
                message="settings_saved",
            )
        if path != f"{self.api_prefix}/refresh":
            return error_response("not_found", "Route not found.", 404)
        if self.admin_token and headers.get("X-Admin-Token") != self.admin_token:
            return error_response("forbidden", "Invalid admin token.", 403)
        media_path = str(payload.get("media_path") or "").strip()
        if media_path:
            refreshed = self.service.refresh_media_item(
                media_path, force_remote_refresh=True
            )
            return 200, ok_response(
                {
                    "category_path": refreshed.get("category_path"),
                    "category_name": refreshed.get("category_name"),
                    "item_count": refreshed.get("stats", {}).get("item_count", 0),
                    "failed_path_count": refreshed.get("stats", {}).get(
                        "failed_path_count", 0
                    ),
                    "cache_hit": refreshed.get("cache_hit", False),
                    "media_id": refreshed.get("media_id"),
                    "media_path": refreshed.get("media_path"),
                    "openlist_refreshed": refreshed.get("openlist_refreshed", False),
                }
            )
        category_path = str(payload.get("category_path") or "").strip()
        if not category_path:
            return error_response(
                "bad_request", "Missing field: category_path or media_path", 400
            )
        refreshed = self.service.refresh_category(
            category_path, force_remote_refresh=True
        )
        return 200, ok_response(
            {
                "category_path": refreshed.get("category_path"),
                "category_name": refreshed.get("category_name"),
                "item_count": refreshed.get("stats", {}).get("item_count", 0),
                "failed_path_count": refreshed.get("stats", {}).get(
                    "failed_path_count", 0
                ),
                "cache_hit": refreshed.get("cache_hit", False),
            }
        )

    def _parse_int(self, value: str, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default
