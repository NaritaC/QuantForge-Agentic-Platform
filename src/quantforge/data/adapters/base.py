from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pandas as pd


@dataclass(frozen=True)
class AdapterBatch:
    dataset: str
    source: str
    adapter_version: str
    source_path: Path
    request: dict[str, Any]
    frame: pd.DataFrame


class DailyBarAdapter(Protocol):
    name: str
    version: str

    def fetch_daily_bars(self) -> AdapterBatch:
        """Return vendor-shaped records plus enough metadata to persist Raw."""
