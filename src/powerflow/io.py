from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from powerflow.case import Case


def load_case(path: str | Path) -> Case:
    with Path(path).open(encoding="utf-8") as handle:
        payload: dict[str, Any] = json.load(handle)
    return Case.from_dict(payload)


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)
