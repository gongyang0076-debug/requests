from types import TracebackType
from typing import Any, Mapping, Sequence

import requests
from requests import Response

QueryParams = Mapping[str, Any] | Sequence[tuple[str, Any]]


class HttpClient:
    """Send HTTP requests through one reusable Requests session."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        headers: Mapping[str, str] | None = None,
        cookies: Mapping[str, str] | None = None,
    ) -> None:
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self.base_url = normalized_base_url
        self.timeout = timeout
        self._session = requests.Session()

        if headers:
            self._session.headers.update(headers)
        if cookies:
            self._session.cookies.update(cookies)

    def request(
        self,
        method: str,
        path: str,
        *,
        timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
        cookies: Mapping[str, str] | None = None,
        params: QueryParams | None = None,
        json: Any = None,
        data: Any = None,
        **kwargs: Any,
    ) -> Response:
        url = f"{self.base_url}/{path.lstrip('/')}"
        request_timeout = self.timeout if timeout is None else timeout

        return self._session.request(
            method=method.upper(),
            url=url,
            timeout=request_timeout,
            headers=headers,
            cookies=cookies,
            params=params,
            json=json,
            data=data,
            **kwargs,
        )

    def get(self, path: str, **kwargs: Any) -> Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> Response:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> Response:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> Response:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> Response:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
