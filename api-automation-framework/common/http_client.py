"""HTTP 客户端封装层。

HttpClient 基于 requests.Session，统一处理：
- Base URL 拼接与去尾部斜杠
- 默认超时、共享 Headers / Cookies（登录态由 Fixture 注入 Bearer Token）
- GET / POST / PUT / PATCH / DELETE 等常用方法
- 每次请求 / 响应 / 网络异常的日志记录与 Allure 附件
- 敏感字段脱敏（调用 logger 中的 sanitize_* 函数）

HttpClient 只提供 HTTP 技术能力，不判断登录、库存、订单状态等业务规则，
业务断言仍由测试层负责。
"""

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

# 查询参数类型：可以是 dict-like，也可以是 [(key, value), ...] 列表
QueryParams = Mapping[str, Any] | Sequence[tuple[str, Any]]


def _attach_json(name: str, content: Mapping[str, Any]) -> None:
    """把 dict 作为 JSON 附件写入 Allure 报告。

    使用 format_json(pretty=True) 格式化，便于在报告里阅读。
    """
    allure.attach(
        format_json(content, pretty=True),
        name=name,
        attachment_type=allure.attachment_type.JSON,
    )


def _response_body(response: Response) -> Any:
    """解析响应体：优先按 JSON 解析，失败则回退为纯文本。

    FastAPI 错误响应可能不是 JSON（如 502 返回 HTML），用 text 兜底。
    """
    try:
        return response.json()
    except ValueError:
        return response.text


class HttpClient:
    """基于 requests.Session 的 HTTP 客户端。

    用法：
        with HttpClient(base_url=..., headers={"Authorization": "Bearer ..."}) as client:
            resp = client.get("/api/users/me")

    所有请求都会被记录日志并生成 Allure 附件，敏感字段自动脱敏。
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        headers: Mapping[str, str] | None = None,
        cookies: Mapping[str, str] | None = None,
    ) -> None:
        # 去掉 base_url 末尾斜杠，避免拼接出双斜杠
        normalized_base_url = base_url.rstrip("/")
        if not normalized_base_url:
            raise ValueError("base_url must not be empty")
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")

        self.base_url = normalized_base_url
        self.timeout = timeout
        # 复用 Session：底层连接池可复用，共享 headers/cookies，登录态只注入一次
        self._session = requests.Session()

        # 默认 headers / cookies，认证 Client 会在 Fixture 里注入 Bearer Token
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
        """发送一次 HTTP 请求并返回 Response。

        Args:
            method: HTTP 方法，大小写不敏感（内部 upper()）。
            path: 相对路径，会拼到 base_url 后；前导斜杠会被去掉。
            timeout: 单次请求超时，None 表示用实例默认 timeout。
            headers / cookies: 本次请求额外覆盖的 headers/cookies。
            params: URL query 参数。
            json: JSON 请求体（与 data 二选一）。
            data: form / 原始请求体。

        Returns:
            requests.Response。

        请求前后都会写日志和 Allure 附件；网络异常会记录失败详情后重新抛出。
        """
        method_name = method.upper()
        # 拼接最终 URL：base_url + 去掉前导斜杠的 path
        url = f"{self.base_url}/{path.lstrip('/')}"
        # 单次请求未指定超时则用实例默认值
        request_timeout = self.timeout if timeout is None else timeout
        # 合并 headers：Session 默认 + 本次覆盖（本次优先）
        request_headers = dict(self._session.headers)
        request_headers.update(headers or {})
        # 合并 cookies：Session 已有 + 本次覆盖
        request_cookies = self._session.cookies.get_dict()
        request_cookies.update(cookies or {})
        # 组装用于日志/附件的诊断信息，并先做脱敏
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
        # 请求信息写入日志和 Allure
        logger.info("HTTP Request %s", format_json(request_details))
        _attach_json("HTTP Request", request_details)

        # 计时开始
        started_at = perf_counter()
        try:
            # 真正发送请求
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
            # 网络层异常（连接超时、DNS 失败等）：记录失败详情后重新抛出
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

        # 组装响应诊断信息并脱敏：状态码、响应头、响应体、耗时
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

    # 下面是常用 HTTP 方法的快捷封装，透传 kwargs 给 request()
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
        """关闭底层 Session，释放连接池资源。"""
        self._session.close()

    # 支持 with 语法，离开作用域自动 close
    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
