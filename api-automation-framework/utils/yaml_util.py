"""YAML 文件加载工具。

提供统一的 load_yaml 函数，供 config 模块和 data 目录的测试数据读取复用。
"""

from pathlib import Path
from typing import Any

import yaml


def load_yaml(file_path: str | Path) -> Any:
    """读取并解析 YAML 文件。

    Args:
        file_path: YAML 文件路径。

    Returns:
        解析后的 Python 对象（通常是 dict / list）。

    Raises:
        ValueError: 文件为空（safe_load 返回 None）时抛出，避免下游拿到 None
                    还在做 .get() 导致 AttributeError。
    """
    path = Path(file_path)
    # 使用 utf-8 编码，兼容中文内容
    with path.open(encoding="utf-8") as yaml_file:
        # safe_load 避免加载任意 Python 对象，安全性更好
        data = yaml.safe_load(yaml_file)

    if data is None:
        # 空文件 / 全注释文件会解析为 None，直接报错便于排查
        raise ValueError(f"YAML file is empty: {path}")

    return data
