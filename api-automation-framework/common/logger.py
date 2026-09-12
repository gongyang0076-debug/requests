"""日志与脱敏模块。

本模块提供框架统一的日志器，以及一组脱敏函数：在把请求/响应/异常信息写入
日志或 Allure 附件之前，先遮蔽 Authorization、Token、密码、Cookie 等敏感字段，
防止凭据泄漏到日志文件或 CI Artifact 中。

脱敏只作用于"用于诊断的副本"，不修改真实 HTTP 请求、响应或测试断言。
"""

import json
import logging
import os
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# 敏感字段被替换成的占位符
MASK = "***"
# 框架日志器的名字，HttpClient 等模块通过 get_logger() 获取
LOGGER_NAME = "api_automation"
# 框架根目录（api-automation-framework/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# 串行执行时的日志文件路径
LOG_FILE = PROJECT_ROOT / "logs" / "api_test.log"

# 判断一个 key 是否敏感的子串集合（全部小写比较）
# 命中 authorization / token / password / passwd / secret / apikey / cookie
_SENSITIVE_KEY_PARTS = (
    "authorization", "token", "password", "passwd", "secret", "apikey", "cookie",
)
# 用于从纯文本（如异常 message）中匹配 "key: value" 或 "key=value" 形式的敏感信息
# 支持 bearer 前缀，常用于 Authorization: Bearer xxx
_SENSITIVE_TEXT_PATTERN = re.compile(
    r"(?i)\b(authorization|access[_-]?token|refresh[_-]?token|token|password|"
    r"set-cookie|cookie)\b(\s*[:=]\s*)(?:bearer\s+)?([^\s,;&]+)"
)


def _is_sensitive_key(key: object) -> bool:
    """判断某个字段名是否属于敏感字段。

    将 key 转成小写并去掉所有非字母数字字符后再做子串匹配，
    例如 "X-Access-Token" 会被规范化为 "xaccesstoken"，命中 "token"。
    """
    normalized_key = re.sub(r"[^a-z0-9]", "", str(key).lower())
    return any(part in normalized_key for part in _SENSITIVE_KEY_PARTS)


def sanitize_data(value: Any) -> Any:
    """递归地把 dict / list 中的敏感字段值替换为 MASK。

    保留原有结构，便于日志可读；只有命中的值被替换，其余字段原样保留。

    特殊处理：FastAPI / Pydantic 返回的 422 校验错误里，每个错误对象包含
    loc（出错字段路径）和 input（用户实际传入的值）。如果 loc 指向敏感字段
    （如 password），则把同一对象的 input 字段整体替换为 "[REDACTED]"，
    非敏感字段的 input 仍保留，便于排查。
    """
    if isinstance(value, Mapping):
        # 取出 422 错误对象里的 loc，判断它是否指向敏感字段
        location = value.get("loc")
        sensitive_input = (
            isinstance(location, (list, tuple))
            and bool(location)
            and _is_sensitive_key(location[-1])
        )
        return {
            # 422 错误对象：loc 指向敏感字段时，遮蔽 input
            str(key): "[REDACTED]" if key == "input" and sensitive_input
            # 普通 key：敏感则整体遮蔽，否则递归处理其值
            else MASK if _is_sensitive_key(key) else sanitize_data(item)
            for key, item in value.items()
        }

    # 处理 list：若元素是 (key, value) 二元组且 key 敏感，则遮蔽 value；
    # 这是为了兼容 cookies/headers 的 [(k,v), ...] 表示形式
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        if len(value) == 2 and isinstance(value[0], str) and _is_sensitive_key(value[0]):
            return [value[0], MASK]
        return [sanitize_data(item) for item in value]

    # 标量（str/int/bool 等）原样返回
    return value


def sanitize_url(url: str) -> str:
    """遮蔽 URL query 中敏感参数的值。

    例如 ``https://x/y?token=abc`` -> ``https://x/y?token=***``。
    保留 key 名方便排查，只遮蔽 value。
    """
    parts = urlsplit(url)
    sanitized_query = [
        (key, MASK if _is_sensitive_key(key) else value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(sanitized_query), parts.fragment)
    )


def sanitize_text(value: str) -> str:
    """遮蔽纯文本中形如 key: value / key=value 的敏感信息。

    主要用于异常 message 中可能携带的凭据。若文本看起来是 URL，
    先走 sanitize_url 处理 query 参数，再用正则遮蔽文本中的 key-value 对。
    """
    sanitized_value = sanitize_url(value) if "://" in value else value
    # 把匹配到的 key+分隔符保留，只把值替换成 MASK
    return _SENSITIVE_TEXT_PATTERN.sub(rf"\1\2{MASK}", sanitized_value)


def format_json(value: Any, *, pretty: bool = False) -> str:
    """把诊断数据序列化为 JSON 字符串，供日志和 Allure 附件统一格式。

    ensure_ascii=False 让中文等字符直接输出，便于阅读；
    default=str 兜底处理不可被 JSON 序列化的对象（如 datetime）。
    """
    return json.dumps(
        value,
        ensure_ascii=False,
        default=str,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    )


def get_log_file() -> Path:
    """返回当前进程对应的日志文件路径。

    串行执行时使用 logs/api_test.log；
    pytest-xdist 并行时每个 worker 有自己的 worker id（如 gw0/gw1），
    分别写入 api_test_gw0.log、api_test_gw1.log，避免多进程竞争同一文件句柄。
    """
    worker_id = os.getenv("PYTEST_XDIST_WORKER")
    if not worker_id:
        return LOG_FILE

    # 对 worker id 做安全清洗，避免特殊字符进入文件名
    safe_worker_id = re.sub(r"[^a-zA-Z0-9_-]", "_", worker_id)
    return LOG_FILE.with_name(f"api_test_{safe_worker_id}.log")


def get_logger() -> logging.Logger:
    """返回框架日志器，同时输出到控制台和文件。

    首次调用时创建 handler 并绑定格式；后续调用直接复用，避免重复添加 handler
    导致日志重复输出。propagate=False 阻止日志向 root logger 冒泡，避免重复。
    """
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        # 已初始化过，直接返回
        return logger

    log_file = get_log_file()
    # 确保 logs 目录存在
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.setLevel(logging.INFO)
    # 不向 root logger 冒泡，避免与第三方库日志重复
    logger.propagate = False

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 控制台 handler，方便实时查看
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件 handler，持久化日志便于排查
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
