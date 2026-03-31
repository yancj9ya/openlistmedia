class OpenListError(Exception):
    """Base exception for the OpenList SDK."""


class OpenListHTTPError(OpenListError):
    """Raised when the HTTP layer fails."""

    def __init__(self, status_code: int, message: str, response_text: str = "") -> None:
        super().__init__(f"HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message
        self.response_text = response_text


class OpenListAPIError(OpenListError):
    """Raised when the OpenList API returns a non-success code."""

    def __init__(self, code: int, message: str, data=None) -> None:
        super().__init__(f"OpenList API error {code}: {message}")
        self.code = code
        self.message = message
        self.data = data
