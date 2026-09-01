from pathlib import Path
from typing import Any

import yaml


def load_yaml(file_path: str | Path) -> Any:
    path = Path(file_path)
    with path.open(encoding="utf-8") as yaml_file:
        data = yaml.safe_load(yaml_file)

    if data is None:
        raise ValueError(f"YAML file is empty: {path}")

    return data
