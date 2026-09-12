"""配置加载模块。

本模块负责把 ``config/config.yaml``（环境相关的 Base URL / 超时）和
``.env`` / 环境变量（数据库连接、可选覆盖项）合并成不可变的 Settings 对象，
供 HttpClient、数据库客户端和 Fixture 使用。

配置优先级（从高到低）：
    命令行 --env 参数  >  环境变量 TEST_ENV  >  默认 "test"
    API_BASE_URL / API_TIMEOUT 环境变量  >  YAML 中对应字段
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from utils.yaml_util import load_yaml

# 框架根目录（api-automation-framework/），用于定位 .env 文件
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# config.yaml 与本文件同目录
CONFIG_PATH = Path(__file__).with_name("config.yaml")
# .env 放在框架根目录，存放数据库连接等敏感配置，已加入 .gitignore
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True, slots=True)
class Settings:
    """API 测试运行配置。

    frozen=True 使实例不可变，避免被意外修改导致不同用例看到不同配置；
    slots=True 节省内存并防止动态新增属性。
    """

    environment: str  # 当前环境名，如 "test" / "pre"
    base_url: str  # 被测服务的基础地址，HttpClient 会拼接在每次请求前
    timeout: float  # 单次 HTTP 请求超时（秒）


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    """MySQL 连接配置。

    password 使用 field(repr=False)，打印对象时不会泄漏密码，
    对日志和错误信息更友好。
    """

    host: str
    port: int
    user: str
    password: str = field(repr=False)  # repr 中隐藏，防止日志泄漏
    name: str  # 数据库名
    connect_timeout: int = 3  # 连接超时（秒），默认 3，避免测试长时间卡住


def load_config(environment: str | None = None) -> Settings:
    """加载 API 测试配置。

    Args:
        environment: 指定环境名（对应 config.yaml 的顶层 key）；
                     为 None 时依次回退到 TEST_ENV 环境变量、"test"。

    Returns:
        构造好的 Settings 对象。

    Raises:
        ValueError: 环境不存在、base_url 缺失或 timeout 非正数时抛出。
    """
    # 读取 .env 和系统环境变量，环境变量优先级更高
    environment_values = _load_environment_values()
    # 确定最终使用的环境：参数 > TEST_ENV > "test"
    selected_environment = environment or environment_values.get("TEST_ENV") or "test"
    # 读取 config.yaml
    raw_config = _load_yaml_config()

    # 取出对应环境的配置块
    environment_config = raw_config.get(selected_environment)
    if not isinstance(environment_config, Mapping):
        # 配置文件里没有这个环境，列出可用环境名方便排查
        available_environments = ", ".join(sorted(raw_config))
        raise ValueError(
            f"Unknown environment '{selected_environment}'. "
            f"Available environments: {available_environments}"
        )

    # base_url 优先用环境变量 API_BASE_URL，其次用 YAML 里的 base_url
    base_url = environment_values.get("API_BASE_URL") or environment_config.get(
        "base_url"
    )
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError(f"Environment '{selected_environment}' requires a base_url")

    # timeout 同样允许环境变量 API_TIMEOUT 覆盖
    timeout_value = environment_values.get("API_TIMEOUT") or environment_config.get(
        "timeout"
    )
    try:
        timeout = float(timeout_value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Environment '{selected_environment}' requires a numeric timeout"
        ) from error

    if timeout <= 0:
        raise ValueError(
            f"Environment '{selected_environment}' requires a positive timeout"
        )

    return Settings(
        environment=selected_environment,
        base_url=base_url.strip(),
        timeout=timeout,
    )


def load_database_config() -> DatabaseSettings:
    """加载 MySQL 连接配置。

    所有字段都来自 .env / 环境变量（DB_HOST、DB_PORT、DB_USER、DB_PASSWORD、
    DB_NAME，可选 DB_CONNECT_TIMEOUT）。任一必填项缺失都会直接抛错，
    避免后续连接时才暴露配置问题。

    Returns:
        构造好的 DatabaseSettings 对象。

    Raises:
        ValueError: 必填项缺失、端口非整数或超出 1~65535 时抛出。
    """
    environment_values = _load_environment_values()
    # 数据库连接的必填项
    required_names = ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME")
    # 收集值为空的环境变量名，便于一次性提示所有缺失项
    missing_names = [
        name
        for name in required_names
        if not environment_values.get(name, "").strip()
    ]
    if missing_names:
        raise ValueError(
            "Missing database configuration: " + ", ".join(missing_names)
        )

    # 端口必须是 1~65535 之间的整数
    try:
        port = int(environment_values["DB_PORT"])
    except ValueError as error:
        raise ValueError("DB_PORT must be an integer") from error
    if not 1 <= port <= 65_535:
        raise ValueError("DB_PORT must be between 1 and 65535")

    # 连接超时可选，默认 3 秒
    timeout_value = environment_values.get("DB_CONNECT_TIMEOUT", "3")
    try:
        connect_timeout = int(timeout_value)
    except ValueError as error:
        raise ValueError("DB_CONNECT_TIMEOUT must be an integer") from error
    if connect_timeout <= 0:
        raise ValueError("DB_CONNECT_TIMEOUT must be greater than zero")

    return DatabaseSettings(
        host=environment_values["DB_HOST"].strip(),
        port=port,
        user=environment_values["DB_USER"].strip(),
        password=environment_values["DB_PASSWORD"],
        name=environment_values["DB_NAME"].strip(),
        connect_timeout=connect_timeout,
    )


def _load_environment_values() -> dict[str, str]:
    """合并 .env 文件与系统环境变量。

    dotenv_values 只读取 .env 文件，不会写回系统环境；
    os.environ 会覆盖 .env 中同名的值，从而让 CI 通过 Secrets 注入的配置
    能覆盖本地 .env。
    """
    file_values = {
        key: value
        for key, value in dotenv_values(ENV_PATH).items()
        if value is not None
    }
    # os.environ 在后，相同 key 以系统环境变量为准
    return {**file_values, **os.environ}


def _load_yaml_config() -> dict[str, Any]:
    """读取并校验 config.yaml。

    Returns:
        解析后的配置字典（key 为环境名，value 为该环境的配置块）。

    Raises:
        ValueError: 文件不存在、为空或顶层不是 dict 时抛出。
    """
    raw_config = load_yaml(CONFIG_PATH)

    if not isinstance(raw_config, dict) or not raw_config:
        raise ValueError(f"Configuration file is empty or invalid: {CONFIG_PATH}")

    return raw_config
