from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Header, Request
from fastapi.responses import Response

from backend.dto.media_dto import (
    to_category_tree_dto,
    to_media_detail_dto,
    to_media_list_item_dto,
)
from backend.dto.responses import ok_response, paginated_response


class APIError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def create_media_router(api_prefix: str) -> APIRouter:
    router = APIRouter(prefix=api_prefix.rstrip("/"))

    def get_service(request: Request):
        return request.app.state.service

    def require_admin_token(
        request: Request,
        x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
    ) -> None:
        service = request.app.state.service
        admin_token = service.config.api.admin_token
        if admin_token and x_admin_token != admin_token:
            raise APIError("forbidden", "Invalid admin token.", 403)

    def require_admin_passcode(
        request: Request,
        x_access_passcode: str | None = Header(
            default=None, alias="X-Access-Passcode"
        ),
    ) -> None:
        service = request.app.state.service
        if not service.is_admin_passcode(x_access_passcode):
            raise APIError("forbidden", "Admin passcode required.", 403)

    @router.get("/health")
    def health(service=Depends(get_service)) -> dict[str, Any]:
        return ok_response(service.health())

    @router.get("/categories")
    def categories(
        path: str | None = None,
        service=Depends(get_service),
    ) -> dict[str, Any]:
        payload = service.get_category_tree(path)
        return ok_response(to_category_tree_dto(payload))

    @router.get("/settings")
    def get_settings(
        _admin: None = Depends(require_admin_passcode),
        service=Depends(get_service),
    ) -> dict[str, Any]:
        return ok_response(service.get_settings())

    @router.get("/media")
    def media_list(
        category_path: str | None = None,
        include_descendants: int = 0,
        year: int | None = None,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        type: str | None = None,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
        service=Depends(get_service),
    ) -> dict[str, Any]:
        payload = service.get_media_list(
            category_path,
            include_descendants == 1,
            year,
            page,
            page_size,
            keyword,
            type,
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
        return response

    @router.get("/media/{media_id}/last-episode")
    def last_played_episode(
        media_id: int,
        service=Depends(get_service),
    ) -> dict[str, Any]:
        if media_id <= 0:
            raise APIError("bad_request", "Invalid media id.", 400)
        payload = service.get_last_played_episode(media_id)
        if payload is None:
            raise APIError("not_found", "No last played episode.", 404)
        return ok_response(payload)

    @router.get("/media/{media_id}/played-episodes")
    def played_episodes(
        media_id: int,
        service=Depends(get_service),
    ) -> dict[str, Any]:
        if media_id <= 0:
            raise APIError("bad_request", "Invalid media id.", 400)
        return ok_response({"items": service.get_played_episodes(media_id)})

    @router.post("/media/{media_id}/played-episodes")
    def record_played_episodes(
        media_id: int,
        payload: dict[str, Any] = Body(default_factory=dict),
        service=Depends(get_service),
    ) -> dict[str, Any]:
        if media_id <= 0:
            raise APIError("bad_request", "Invalid media id.", 400)
        raw_paths = payload.get("file_paths")
        if raw_paths is None:
            raw_path = payload.get("file_path")
            raw_paths = [raw_path] if raw_path else []
        if not isinstance(raw_paths, list) or not raw_paths:
            raise APIError("bad_request", "Missing field: file_paths", 400)
        file_paths = [str(path).strip() for path in raw_paths if str(path).strip()]
        if not file_paths:
            raise APIError("bad_request", "Missing field: file_paths", 400)
        return ok_response({"items": service.record_played_episodes(media_id, file_paths)})

    @router.get("/media/{media_id}")
    def media_detail(media_id: int, service=Depends(get_service)) -> dict[str, Any]:
        if media_id <= 0:
            raise APIError("bad_request", "Invalid media id.", 400)
        payload = service.get_media_detail(media_id)
        if payload is None:
            raise APIError("not_found", "Media item not found.", 404)
        return ok_response(to_media_detail_dto(payload))

    @router.get("/refresh")
    def refresh_hint(
        _admin: None = Depends(require_admin_token),
    ) -> dict[str, Any]:
        return ok_response({"message": "Use POST /refresh with category_path or media_path."})

    @router.get("/recent-plays")
    def recent_plays(service=Depends(get_service)) -> dict[str, Any]:
        payload = service.get_recent_play_history(limit=10)
        return ok_response(payload)

    @router.get("/playlist/{playlist_id}.m3u")
    def playlist(playlist_id: str, service=Depends(get_service)) -> Response:
        if not playlist_id:
            raise APIError("bad_request", "Missing playlist id.", 400)
        text = service.get_playlist(playlist_id)
        if text is None:
            raise APIError("not_found", "Playlist not found or expired.", 404)
        return Response(
            content=text.encode("utf-8"),
            media_type="audio/x-mpegurl; charset=utf-8",
        )

    @router.post("/record-play")
    def record_play(
        payload: dict[str, Any] = Body(default_factory=dict),
        service=Depends(get_service),
    ) -> dict[str, Any]:
        media_id = payload.get("media_id")
        if not media_id:
            raise APIError("bad_request", "Missing field: media_id", 400)
        file_path = payload.get("file_path")
        file_path = str(file_path).strip() if file_path else None
        try:
            service.record_play_history(int(media_id), file_path or None)
        except (ValueError, TypeError):
            raise APIError("bad_request", "Invalid media_id", 400)
        return ok_response({"recorded": True})

    @router.post("/auth/login")
    def login(
        payload: dict[str, Any] = Body(default_factory=dict),
        service=Depends(get_service),
    ) -> dict[str, Any]:
        passcode = str(payload.get("passcode") or "").strip()
        if not passcode:
            raise APIError("bad_request", "Missing field: passcode", 400)
        authenticated = service.authenticate_access(passcode)
        if not authenticated:
            raise APIError("forbidden", "Invalid passcode.", 403)
        return ok_response(authenticated)

    @router.post("/play-link")
    def play_link(
        payload: dict[str, Any] = Body(default_factory=dict),
        service=Depends(get_service),
    ) -> dict[str, Any]:
        media_path = str(payload.get("path") or "").strip()
        if not media_path:
            raise APIError("bad_request", "Missing field: path", 400)
        return ok_response(service.get_play_link(media_path))

    @router.post("/playlist")
    def create_playlist(
        payload: dict[str, Any] = Body(default_factory=dict),
        service=Depends(get_service),
    ) -> dict[str, Any]:
        raw_paths = payload.get("paths")
        if not isinstance(raw_paths, list) or not raw_paths:
            raise APIError("bad_request", "Missing or invalid field: paths", 400)
        try:
            result = service.create_playlist([str(p) for p in raw_paths])
        except ValueError as exc:
            raise APIError("bad_request", str(exc), 400)
        return ok_response(result)

    @router.post("/settings")
    def update_settings(
        payload: dict[str, Any] = Body(default_factory=dict),
        _admin: None = Depends(require_admin_passcode),
        service=Depends(get_service),
    ) -> dict[str, Any]:
        try:
            result = service.update_settings(payload)
        except ValueError as exc:
            raise APIError("bad_request", str(exc), 400)
        return ok_response(
            {
                "settings": result["saved"],
                "restart_required": result["restart_required"],
                "changed_fields": result["changed_fields"],
            },
            message="settings_saved",
        )

    @router.post("/refresh")
    def refresh(
        payload: dict[str, Any] = Body(default_factory=dict),
        _admin: None = Depends(require_admin_token),
        service=Depends(get_service),
    ) -> dict[str, Any]:
        media_path = str(payload.get("media_path") or "").strip()
        if media_path:
            refreshed = service.refresh_media_item(
                media_path, force_remote_refresh=True
            )
            return ok_response(
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
            raise APIError(
                "bad_request", "Missing field: category_path or media_path", 400
            )
        refreshed = service.refresh_category_shallow(
            category_path, force_remote_refresh=True
        )
        return ok_response(
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

    return router
