from time import perf_counter
from types import TracebackType
from typing import Any, Mapping, Sequence

import allure
import requests
from requests import Response

from common.logger import (
    format_json,
    get_logger,
    sanitize_data,
    sanitize_text,
    sanitize_url,
)

QueryParams = Mapping[str, Any] | Sequence[tuple[str, Any]]


def _attach_json(name: str, content: Mapping[str, Any]) -> None:
    allure.attach(
        format_json(content, pretty=True),
        name=name,
        attachment_type=allure.attachment_type.JSON,
    )


def _response_body(response: Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return response.text


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
        method_name = method.upper()
        url = f"{self.base_url}/{path.lstrip('/')}"
        request_timeout = self.timeout if timeout is None else timeout
        request_headers = dict(self._session.headers)
        request_headers.update(headers or {})
        request_cookies = self._session.cookies.get_dict()
        request_cookies.update(cookies or {})
        request_details = sanitize_data(
            {
                "method": method_name,
                "url": sanitize_url(url),
                "headers": request_headers,
                "cookies": request_cookies,
                "params": params,
                "body": json if json is not None else data,
                "timeout": request_timeout,
            }
        )

        logger = get_logger()
        logger.info("HTTP Request %s", format_json(request_details))
        _attach_json("HTTP Request", request_details)

        started_at = perf_counter()
        try:
            response = self._session.request(
                method=method_name,
                url=url,
                timeout=request_timeout,
                headers=headers,
                cookies=cookies,
                params=params,
                json=json,
                data=data,
                **kwargs,
            )
        except requests.RequestException as exc:
            failure_details = {
                "method": method_name,
                "url": sanitize_url(url),
                "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
                "error_type": type(exc).__name__,
                "message": sanitize_text(str(exc)),
            }
            logger.error("HTTP Failure %s", format_json(failure_details))
            _attach_json("HTTP Failure", failure_details)
            raise

        response_details = sanitize_data(
            {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": _response_body(response),
                "elapsed_ms": round((perf_counter() - started_at) * 1000, 2),
            }
        )
        logger.info("HTTP Response %s", format_json(response_details))
        _attach_json("HTTP Response", response_details)
        return response

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
