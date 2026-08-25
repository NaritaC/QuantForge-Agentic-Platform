from __future__ import annotations

from pathlib import Path

import pandas as pd

from quantforge.data.adapters.base import AdapterBatch


class FixtureDailyBarAdapter:
    """Offline adapter used by tests and the public reproducible demo."""

    name = "fixture"
    version = "1.0.0"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).resolve()

    def fetch_daily_bars(self) -> AdapterBatch:
        if not self.path.is_file():
            raise FileNotFoundError(f"Fixture data not found: {self.path}")
        frame = pd.read_csv(self.path, dtype={"symbol": "string", "is_st": "string"})
        return AdapterBatch(
            dataset="daily_bars",
            source=self.name,
            adapter_version=self.version,
            source_path=self.path,
            request={"kind": "offline_fixture", "filename": self.path.name},
            frame=frame,
        )
