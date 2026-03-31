from __future__ import annotations

from typing import Any

import requests


class TMDbError(Exception):
    """Base exception for the TMDb SDK."""


class TMDbHTTPError(TMDbError):
    """Raised when TMDb returns a non-2xx HTTP response."""

    def __init__(self, status_code: int, message: str, response_text: str = "") -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.response_text = response_text


class TMDbAPIError(TMDbError):
    """Raised when TMDb returns an API payload describing an error."""

    def __init__(self, status_code: int | None, message: str, payload: Any = None) -> None:
        label = f"TMDb API error {status_code}: {message}" if status_code is not None else message
        super().__init__(label)
        self.status_code = status_code
        self.message = message
        self.payload = payload


class TMDbClient:
    """
    Minimal Python SDK for TMDb v3.

    Official docs:
    https://developer.themoviedb.org/reference/configuration-details
    """

    def __init__(
        self,
        read_access_token: str | None = None,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.themoviedb.org/3",
        timeout: float = 30.0,
        session: requests.Session | None = None,
    ) -> None:
        if not read_access_token and not api_key:
            raise ValueError("Provide read_access_token or api_key.")

        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        if session is None:
            self.session.trust_env = False
        self.read_access_token = read_access_token
        self.api_key = api_key

        self.session.headers.setdefault("Accept", "application/json")
        if read_access_token:
            self.session.headers["Authorization"] = f"Bearer {read_access_token}"

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "TMDbClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        final_params = dict(params or {})
        if self.api_key and "api_key" not in final_params:
            final_params["api_key"] = self.api_key

        response = self.session.request(
            method.upper(),
            self._url(path),
            params=self._clean(final_params),
            json=json,
            timeout=self.timeout,
        )

        if not response.ok:
            raise TMDbHTTPError(response.status_code, response.reason, response.text)

        payload = response.json()
        if isinstance(payload, dict) and payload.get("success") is False:
            raise TMDbAPIError(payload.get("status_code"), payload.get("status_message", "TMDb request failed"), payload)
        return payload

    def get(self, path: str, **kwargs: Any) -> Any:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Any:
        return self.request("POST", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Any:
        return self.request("DELETE", path, **kwargs)

    def configuration_details(self) -> dict[str, Any]:
        return self.get("/configuration")

    def configuration_countries(self) -> list[dict[str, Any]]:
        return self.get("/configuration/countries")

    def configuration_jobs(self) -> list[dict[str, Any]]:
        return self.get("/configuration/jobs")

    def configuration_languages(self) -> list[dict[str, Any]]:
        return self.get("/configuration/languages")

    def configuration_primary_translations(self) -> list[str]:
        return self.get("/configuration/primary_translations")

    def configuration_timezones(self) -> list[dict[str, Any]]:
        return self.get("/configuration/timezones")

    def search_movie(
        self,
        query: str,
        *,
        language: str | None = None,
        page: int | None = None,
        include_adult: bool | None = None,
        region: str | None = None,
        year: int | None = None,
        primary_release_year: int | None = None,
    ) -> dict[str, Any]:
        return self.get(
            "/search/movie",
            params={
                "query": query,
                "language": language,
                "page": page,
                "include_adult": include_adult,
                "region": region,
                "year": year,
                "primary_release_year": primary_release_year,
            },
        )

    def search_tv(
        self,
        query: str,
        *,
        language: str | None = None,
        page: int | None = None,
        include_adult: bool | None = None,
        first_air_date_year: int | None = None,
    ) -> dict[str, Any]:
        return self.get(
            "/search/tv",
            params={
                "query": query,
                "language": language,
                "page": page,
                "include_adult": include_adult,
                "first_air_date_year": first_air_date_year,
            },
        )

    def search_person(
        self,
        query: str,
        *,
        language: str | None = None,
        page: int | None = None,
        include_adult: bool | None = None,
    ) -> dict[str, Any]:
        return self.get(
            "/search/person",
            params={
                "query": query,
                "language": language,
                "page": page,
                "include_adult": include_adult,
            },
        )

    def search_multi(
        self,
        query: str,
        *,
        language: str | None = None,
        page: int | None = None,
        include_adult: bool | None = None,
    ) -> dict[str, Any]:
        return self.get(
            "/search/multi",
            params={
                "query": query,
                "language": language,
                "page": page,
                "include_adult": include_adult,
            },
        )

    def movie_details(
        self,
        movie_id: int,
        *,
        language: str | None = None,
        append_to_response: str | None = None,
    ) -> dict[str, Any]:
        return self.get(
            f"/movie/{movie_id}",
            params={"language": language, "append_to_response": append_to_response},
        )

    def movie_images(self, movie_id: int, *, language: str | None = None, include_image_language: str | None = None) -> dict[str, Any]:
        return self.get(
            f"/movie/{movie_id}/images",
            params={"language": language, "include_image_language": include_image_language},
        )

    def movie_videos(self, movie_id: int, *, language: str | None = None) -> dict[str, Any]:
        return self.get(f"/movie/{movie_id}/videos", params={"language": language})

    def movie_watch_providers(self, movie_id: int) -> dict[str, Any]:
        return self.get(f"/movie/{movie_id}/watch/providers")

    def popular_movies(self, *, language: str | None = None, page: int | None = None, region: str | None = None) -> dict[str, Any]:
        return self.get("/movie/popular", params={"language": language, "page": page, "region": region})

    def top_rated_movies(self, *, language: str | None = None, page: int | None = None, region: str | None = None) -> dict[str, Any]:
        return self.get("/movie/top_rated", params={"language": language, "page": page, "region": region})

    def now_playing_movies(self, *, language: str | None = None, page: int | None = None, region: str | None = None) -> dict[str, Any]:
        return self.get("/movie/now_playing", params={"language": language, "page": page, "region": region})

    def upcoming_movies(self, *, language: str | None = None, page: int | None = None, region: str | None = None) -> dict[str, Any]:
        return self.get("/movie/upcoming", params={"language": language, "page": page, "region": region})

    def tv_details(
        self,
        series_id: int,
        *,
        language: str | None = None,
        append_to_response: str | None = None,
    ) -> dict[str, Any]:
        return self.get(
            f"/tv/{series_id}",
            params={"language": language, "append_to_response": append_to_response},
        )

    def tv_season_details(self, series_id: int, season_number: int, *, language: str | None = None, append_to_response: str | None = None) -> dict[str, Any]:
        return self.get(
            f"/tv/{series_id}/season/{season_number}",
            params={"language": language, "append_to_response": append_to_response},
        )

    def tv_episode_details(
        self,
        series_id: int,
        season_number: int,
        episode_number: int,
        *,
        language: str | None = None,
        append_to_response: str | None = None,
    ) -> dict[str, Any]:
        return self.get(
            f"/tv/{series_id}/season/{season_number}/episode/{episode_number}",
            params={"language": language, "append_to_response": append_to_response},
        )

    def popular_tv(self, *, language: str | None = None, page: int | None = None) -> dict[str, Any]:
        return self.get("/tv/popular", params={"language": language, "page": page})

    def top_rated_tv(self, *, language: str | None = None, page: int | None = None) -> dict[str, Any]:
        return self.get("/tv/top_rated", params={"language": language, "page": page})

    def airing_today_tv(self, *, language: str | None = None, page: int | None = None, timezone: str | None = None) -> dict[str, Any]:
        return self.get("/tv/airing_today", params={"language": language, "page": page, "timezone": timezone})

    def on_the_air_tv(self, *, language: str | None = None, page: int | None = None, timezone: str | None = None) -> dict[str, Any]:
        return self.get("/tv/on_the_air", params={"language": language, "page": page, "timezone": timezone})

    def person_details(self, person_id: int, *, language: str | None = None, append_to_response: str | None = None) -> dict[str, Any]:
        return self.get(
            f"/person/{person_id}",
            params={"language": language, "append_to_response": append_to_response},
        )

    def person_movie_credits(self, person_id: int, *, language: str | None = None) -> dict[str, Any]:
        return self.get(f"/person/{person_id}/movie_credits", params={"language": language})

    def person_tv_credits(self, person_id: int, *, language: str | None = None) -> dict[str, Any]:
        return self.get(f"/person/{person_id}/tv_credits", params={"language": language})

    def trending(self, media_type: str = "all", time_window: str = "day", *, language: str | None = None) -> dict[str, Any]:
        return self.get(f"/trending/{media_type}/{time_window}", params={"language": language})

    def discover_movie(self, **params: Any) -> dict[str, Any]:
        return self.get("/discover/movie", params=params)

    def discover_tv(self, **params: Any) -> dict[str, Any]:
        return self.get("/discover/tv", params=params)

    def movie_genres(self, *, language: str | None = None) -> dict[str, Any]:
        return self.get("/genre/movie/list", params={"language": language})

    def tv_genres(self, *, language: str | None = None) -> dict[str, Any]:
        return self.get("/genre/tv/list", params={"language": language})

    def find(self, external_id: str, external_source: str, *, language: str | None = None) -> dict[str, Any]:
        return self.get(
            f"/find/{external_id}",
            params={"external_source": external_source, "language": language},
        )

    def build_image_url(self, file_path: str, *, size: str = "original", secure: bool = True) -> str:
        config = self.configuration_details()
        image_config = config["images"]
        base = image_config["secure_base_url"] if secure else image_config["base_url"]
        clean_path = file_path if file_path.startswith("/") else f"/{file_path}"
        return f"{base}{size}{clean_path}"

    @staticmethod
    def _clean(params: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in params.items() if value is not None}

    def _url(self, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"
