from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, BinaryIO, Mapping
from urllib.parse import quote

import requests

from .exceptions import OpenListAPIError, OpenListHTTPError


JsonMapping = Mapping[str, Any]


class OpenListClient:
    """
    Lightweight Python SDK for the OpenList HTTP API.

    Docs source: https://openlist.apifox.cn/
    """

    HASH_LOGIN_SUFFIX = "-https://github.com/alist-org/alist"

    def __init__(
        self,
        base_url: str,
        token: str | None = None,
        *,
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        if session is None:
            self.session.trust_env = False
        self.token = token
        if token:
            self.set_token(token)

    def set_token(self, token: str | None) -> None:
        self.token = token
        if token:
            self.session.headers["Authorization"] = token
        else:
            self.session.headers.pop("Authorization", None)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "OpenListClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def hash_password(password: str) -> str:
        digest = hashlib.sha256()
        digest.update(f"{password}{OpenListClient.HASH_LOGIN_SUFFIX}".encode("utf-8"))
        return digest.hexdigest()

    def login(self, username: str, password: str) -> str:
        data = self.post("/api/auth/login", json={"username": username, "password": password})
        if not isinstance(data, dict) or "token" not in data:
            raise OpenListAPIError(code=-1, message="Login response did not contain a token", data=data)
        token = data["token"]
        self.set_token(token)
        return token

    def login_hashed(self, username: str, password: str) -> str:
        hashed_password = self.hash_password(password)
        data = self.post(
            "/api/auth/login/hash",
            json={"username": username, "password": hashed_password},
        )
        if not isinstance(data, dict) or "token" not in data:
            raise OpenListAPIError(code=-1, message="Hashed login response did not contain a token", data=data)
        token = data["token"]
        self.set_token(token)
        return token

    def me(self) -> JsonMapping:
        return self.get("/api/me")

    def ping(self) -> str:
        response = self.session.get(f"{self.base_url}/ping", timeout=self.timeout)
        if not response.ok:
            raise OpenListHTTPError(response.status_code, "Ping request failed", response.text)
        return response.text

    def public_settings(self) -> JsonMapping:
        return self.get("/api/public/settings")

    def list_dir(
        self,
        path: str,
        *,
        password: str = "",
        page: int = 1,
        per_page: int = 0,
        refresh: bool = False,
    ) -> JsonMapping:
        return self.post(
            "/api/fs/list",
            json={
                "path": path,
                "password": password,
                "page": page,
                "per_page": per_page,
                "refresh": refresh,
            },
        )

    def get_fs_info(self, path: str, *, password: str = "") -> JsonMapping:
        return self.post("/api/fs/get", json={"path": path, "password": password})

    def get_directory(self, path: str, *, password: str = "") -> JsonMapping:
        return self.post("/api/fs/dirs", json={"path": path, "password": password})

    def search(
        self,
        parent: str,
        keywords: str,
        *,
        scope: int = 0,
        page: int = 1,
        per_page: int = 0,
        password: str = "",
    ) -> JsonMapping:
        return self.post(
            "/api/fs/search",
            json={
                "parent": parent,
                "keywords": keywords,
                "scope": scope,
                "page": page,
                "per_page": per_page,
                "password": password,
            },
        )

    def mkdir(self, path: str) -> Any:
        return self.post("/api/fs/mkdir", json={"path": path})

    def rename(self, path: str, name: str) -> Any:
        return self.post("/api/fs/rename", json={"path": path, "name": name})

    def batch_rename(self, src_dir: str, rename_objects: list[dict[str, str]]) -> Any:
        return self.post(
            "/api/fs/batch_rename",
            json={"src_dir": src_dir, "rename_objects": rename_objects},
        )

    def regex_rename(self, src_dir: str, src_name_regex: str, new_name_regex: str) -> Any:
        return self.post(
            "/api/fs/regex_rename",
            json={
                "src_dir": src_dir,
                "src_name_regex": src_name_regex,
                "new_name_regex": new_name_regex,
            },
        )

    def move(self, src_dir: str, dst_dir: str, names: list[str]) -> Any:
        return self.post(
            "/api/fs/move",
            json={"src_dir": src_dir, "dst_dir": dst_dir, "names": names},
        )

    def recursive_move(self, src_dir: str, dst_dir: str) -> Any:
        return self.post("/api/fs/recursive_move", json={"src_dir": src_dir, "dst_dir": dst_dir})

    def copy(self, src_dir: str, dst_dir: str, names: list[str]) -> Any:
        return self.post(
            "/api/fs/copy",
            json={"src_dir": src_dir, "dst_dir": dst_dir, "names": names},
        )

    def remove(self, dir_path: str, names: list[str]) -> Any:
        return self.post("/api/fs/remove", json={"dir": dir_path, "names": names})

    def remove_empty_directory(self, src_dir: str) -> Any:
        return self.post("/api/fs/remove_empty_directory", json={"src_dir": src_dir})

    def add_offline_download(self, payload: JsonMapping) -> Any:
        return self.post("/api/fs/add_offline_download", json=dict(payload))

    def upload_file(
        self,
        remote_dir: str,
        local_path: str | Path,
        *,
        as_task: bool = True,
        password: str = "",
    ) -> JsonMapping:
        local_path = Path(local_path)
        headers = {
            "File-Path": quote(remote_dir, safe="/"),
            "As-Task": str(as_task).lower(),
        }
        if password:
            headers["Password"] = password
        with local_path.open("rb") as handle:
            files = {"file": (local_path.name, handle)}
            return self.put("/api/fs/form", files=files, headers=headers)

    def upload_stream(
        self,
        remote_path: str,
        stream: BinaryIO,
        *,
        as_task: bool = True,
        password: str = "",
        content_type: str = "application/octet-stream",
    ) -> JsonMapping:
        headers = {
            "File-Path": quote(remote_path, safe="/"),
            "As-Task": str(as_task).lower(),
            "Content-Type": content_type,
        }
        if password:
            headers["Password"] = password
        return self.put("/api/fs/put", data=stream, headers=headers)

    def list_settings(self) -> list[JsonMapping]:
        return self.get("/api/admin/setting/list")

    def get_setting(self, key: str) -> JsonMapping:
        return self.get("/api/admin/setting/get", params={"key": key})

    def save_setting(self, payload: JsonMapping) -> Any:
        return self.post("/api/admin/setting/save", json=dict(payload))

    def reset_token(self) -> Any:
        return self.post("/api/admin/setting/reset_token")

    def list_users(self, page: int = 1, per_page: int = 0) -> JsonMapping:
        return self.get("/api/admin/user/list", params={"page": page, "per_page": per_page})

    def get_user(self, user_id: int) -> JsonMapping:
        return self.get("/api/admin/user/get", params={"id": user_id})

    def create_user(self, payload: JsonMapping) -> JsonMapping:
        return self.post("/api/admin/user/create", json=dict(payload))

    def update_user(self, payload: JsonMapping) -> Any:
        return self.post("/api/admin/user/update", json=dict(payload))

    def cancel_user_2fa(self, user_id: int) -> Any:
        return self.post("/api/admin/user/cancel_2fa", params={"id": user_id})

    def delete_user(self, user_id: int) -> Any:
        return self.post("/api/admin/user/delete", params={"id": user_id})

    def clear_user_cache(self, user_id: int) -> Any:
        return self.post("/api/admin/user/clear_cache", params={"id": user_id})

    def list_storages(self) -> list[JsonMapping]:
        return self.get("/api/admin/storage/list")

    def get_storage(self, storage_id: int) -> JsonMapping:
        return self.get("/api/admin/storage/get", params={"id": storage_id})

    def create_storage(self, payload: JsonMapping) -> JsonMapping:
        return self.post("/api/admin/storage/create", json=dict(payload))

    def update_storage(self, payload: JsonMapping) -> Any:
        return self.post("/api/admin/storage/update", json=dict(payload))

    def enable_storage(self, storage_id: int) -> Any:
        return self.post("/api/admin/storage/enable", params={"id": storage_id})

    def disable_storage(self, storage_id: int) -> Any:
        return self.post("/api/admin/storage/disable", params={"id": storage_id})

    def delete_storage(self, storage_id: int) -> Any:
        return self.post("/api/admin/storage/delete", params={"id": storage_id})

    def reload_storages(self) -> Any:
        return self.post("/api/admin/storage/load_all")

    def list_driver_templates(self) -> list[JsonMapping]:
        return self.get("/api/admin/driver/list")

    def list_driver_names(self) -> list[str]:
        return self.get("/api/admin/driver/names")

    def get_driver_info(self, driver_name: str) -> JsonMapping:
        return self.get("/api/admin/driver/info", params={"driver": driver_name})

    def list_meta(self) -> JsonMapping:
        return self.get("/api/admin/meta/list")

    def get_meta(self, meta_id: int) -> JsonMapping:
        return self.get("/api/admin/meta/get", params={"id": meta_id})

    def create_meta(self, payload: JsonMapping) -> JsonMapping:
        return self.post("/api/admin/meta/create", json=dict(payload))

    def update_meta(self, payload: JsonMapping) -> Any:
        return self.post("/api/admin/meta/update", json=dict(payload))

    def delete_meta(self, meta_id: int) -> Any:
        return self.post("/api/admin/meta/delete", params={"id": meta_id})

    def upload_task_info(self) -> list[JsonMapping]:
        return self.post("/api/admin/task/upload/info")

    def upload_task_done(self) -> list[JsonMapping]:
        return self.get("/api/admin/task/upload/done")

    def upload_task_undone(self) -> list[JsonMapping]:
        return self.get("/api/admin/task/upload/undone")

    def delete_upload_task(self, task_id: str) -> Any:
        return self.post("/api/admin/task/upload/delete", params={"tid": task_id})

    def cancel_upload_task(self, task_id: str) -> Any:
        return self.post("/api/admin/task/upload/cancel", params={"tid": task_id})

    def retry_upload_task(self, task_id: str) -> Any:
        return self.post("/api/admin/task/upload/retry", params={"tid": task_id})

    def clear_upload_done(self) -> Any:
        return self.post("/api/admin/task/upload/clear_done")

    def clear_upload_succeeded(self) -> Any:
        return self.post("/api/admin/task/upload/clear_succeeded")

    def get(self, path: str, **kwargs: Any) -> Any:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self._request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Any:
        return self._request("PUT", path, **kwargs)

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        return self._request(method, path, **kwargs)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = self._url(path)
        timeout = kwargs.pop("timeout", self.timeout)
        response = self.session.request(method.upper(), url, timeout=timeout, **kwargs)

        if not response.ok:
            raise OpenListHTTPError(response.status_code, response.reason, response.text)

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return response.text

        payload = response.json()
        if not isinstance(payload, dict):
            return payload

        code = payload.get("code", 200)
        if code != 200:
            raise OpenListAPIError(code=code, message=payload.get("message", "Unknown error"), data=payload.get("data"))
        return payload.get("data")

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"
