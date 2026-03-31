from __future__ import annotations

from typing import Any


def ok_response(data: Any, message: str = "ok") -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def paginated_response(
    items: list[dict[str, Any]], total: int, page: int, page_size: int
) -> dict[str, Any]:
    return ok_response(
        {
            "items": items,
            "years": [],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "has_next": page * page_size < total,
            },
        }
    )


def error_response(
    code: str, message: str, status: int, details: Any = None
) -> tuple[int, dict[str, Any]]:
    payload = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }
    if details is not None:
        payload["error"]["details"] = details
    return status, payload
