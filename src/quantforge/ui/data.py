from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


@dataclass(frozen=True)
class RunRecord:
    """A validated run manifest and its local source path."""

    path: Path
    manifest: dict[str, Any]

    @property
    def run_id(self) -> str:
        return str(self.manifest["run_id"])

    @property
    def label(self) -> str:
        started_at = str(self.manifest.get("started_at", "unknown"))
        source = str(self.manifest.get("config", {}).get("source", "unknown"))
        status = str(self.manifest.get("status", "unknown"))
        return f"{started_at[:19]}  ·  {source}  ·  {status}"


def _read_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not payload.get("run_id"):
        raise ValueError(f"Invalid run manifest: {path}")
    return payload


def discover_runs(project_root: str | Path) -> list[RunRecord]:
    """Return readable run manifests, newest first; malformed runs are ignored."""

    artifacts_dir = Path(project_root).resolve() / "artifacts" / "runs"
    records: list[RunRecord] = []
    for path in artifacts_dir.glob("*/run.json"):
        try:
            records.append(RunRecord(path=path, manifest=_read_manifest(path)))
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            continue
    return sorted(
        records,
        key=lambda item: str(item.manifest.get("started_at", "")),
        reverse=True,
    )


def _parquet_glob(manifest: dict[str, Any]) -> str:
    snapshot_path = manifest.get("curated", {}).get("path")
    if not snapshot_path:
        raise ValueError("Run manifest does not contain a curated snapshot path")
    path = Path(str(snapshot_path))
    if not path.exists():
        raise FileNotFoundError(f"Curated snapshot is not available locally: {path}")
    return (path / "**" / "*.parquet").as_posix()


def load_daily_bar_preview(manifest: dict[str, Any], *, limit: int = 200) -> pd.DataFrame:
    """Load a bounded, human-readable sample without materializing the full dataset."""

    if limit < 1:
        raise ValueError("limit must be positive")
    connection = duckdb.connect(database=":memory:")
    try:
        return connection.execute(
            """
            SELECT
                trade_date,
                instrument_id,
                open,
                high,
                low,
                close,
                volume,
                amount,
                trade_status,
                source
            FROM read_parquet(?, hive_partitioning = true)
            ORDER BY trade_date DESC, instrument_id
            LIMIT ?
            """,
            [_parquet_glob(manifest), limit],
        ).fetchdf()
    finally:
        connection.close()


def load_indexed_close_series(
    manifest: dict[str, Any],
    *,
    instrument_limit: int = 8,
    trading_day_limit: int = 252,
) -> pd.DataFrame:
    """Load recent closes for liquid instruments and rebase each series to 100."""

    if instrument_limit < 1 or trading_day_limit < 2:
        raise ValueError("instrument_limit must be positive and trading_day_limit at least two")
    parquet_glob = _parquet_glob(manifest)
    connection = duckdb.connect(database=":memory:")
    try:
        frame = connection.execute(
            """
            WITH selected_instruments AS (
                SELECT instrument_id
                FROM read_parquet(?, hive_partitioning = true)
                GROUP BY instrument_id
                ORDER BY AVG(amount) DESC NULLS LAST, instrument_id
                LIMIT ?
            ),
            recent_dates AS (
                SELECT DISTINCT trade_date
                FROM read_parquet(?, hive_partitioning = true)
                ORDER BY trade_date DESC
                LIMIT ?
            )
            SELECT bars.trade_date, bars.instrument_id, bars.close
            FROM read_parquet(?, hive_partitioning = true) AS bars
            INNER JOIN selected_instruments USING (instrument_id)
            INNER JOIN recent_dates USING (trade_date)
            WHERE bars.close IS NOT NULL
            ORDER BY bars.trade_date, bars.instrument_id
            """,
            [parquet_glob, instrument_limit, parquet_glob, trading_day_limit, parquet_glob],
        ).fetchdf()
    finally:
        connection.close()
    if frame.empty:
        return frame
    frame["indexed_close"] = frame.groupby("instrument_id", sort=False)["close"].transform(
        lambda series: series / series.iloc[0] * 100
    )
    return frame[["trade_date", "instrument_id", "indexed_close"]]


def quality_issues_frame(manifest: dict[str, Any]) -> pd.DataFrame:
    """Flatten main and reference quality issues for UI display."""

    rows: list[dict[str, Any]] = []
    reports: list[tuple[str, dict[str, Any]]] = [("daily_bars", manifest.get("quality", {}))]
    for dataset, payload in manifest.get("reference_data", {}).items():
        reports.append((str(dataset), payload.get("quality", {})))
    for dataset, report in reports:
        for issue in report.get("issues", []):
            rows.append(
                {
                    "dataset": dataset,
                    "severity": issue.get("severity", "unknown"),
                    "check": issue.get("check", "unknown"),
                    "count": issue.get("count", 0),
                    "message": issue.get("message", ""),
                }
            )
    return pd.DataFrame(rows, columns=["dataset", "severity", "check", "count", "message"])
