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


def load_raw_preview(manifest: dict[str, Any], *, limit: int = 200) -> pd.DataFrame:
    """Load a bounded preview of the exact local Raw artifact when its format is supported."""

    if limit < 1:
        raise ValueError("limit must be positive")
    value = manifest.get("raw", {}).get("data_path")
    if not value:
        raise ValueError("Run manifest does not contain a Raw artifact path")
    path = Path(str(value))
    if not path.exists():
        raise FileNotFoundError(f"Raw artifact is not available locally: {path}")
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, nrows=limit)
    if path.suffix.lower() == ".parquet":
        return pd.read_parquet(path).head(limit)
    raise ValueError(f"Raw preview is not supported for {path.suffix or 'binary'} artifacts")


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


def quality_checks_frame(manifest: dict[str, Any]) -> pd.DataFrame:
    """Flatten all executed checks, including checks that passed."""

    rows: list[dict[str, Any]] = []
    reports: list[tuple[str, dict[str, Any]]] = [("daily_bars", manifest.get("quality", {}))]
    for dataset, payload in manifest.get("reference_data", {}).items():
        reports.append((str(dataset), payload.get("quality", {})))
    for dataset, report in reports:
        checks = report.get("checks", [])
        if not checks:
            checks = [
                {
                    "check": issue.get("check", "unknown"),
                    "severity": issue.get("severity", "unknown"),
                    "status": ("failed" if issue.get("severity") == "error" else "warning"),
                    "violations": issue.get("count"),
                    "message": issue.get("message", ""),
                }
                for issue in report.get("issues", [])
            ]
        for check in checks:
            rows.append({"dataset": dataset, **check})
    return pd.DataFrame(
        rows,
        columns=["dataset", "check", "severity", "status", "violations", "message"],
    )


def processing_steps_frame(manifest: dict[str, Any], *, language: str) -> pd.DataFrame:
    """Return ordered processing evidence for the selected language."""

    name_key = "name_zh" if language == "中文" else "name_en"
    rule_key = "rule_zh" if language == "中文" else "rule_en"
    rows = []
    for step in manifest.get("lineage", {}).get("processing_steps", []):
        rows.append(
            {
                "order": step.get("order"),
                "step": step.get("step"),
                "name": step.get(name_key, step.get("step")),
                "rule": step.get(rule_key, ""),
                "input_rows": step.get("input_rows"),
                "output_rows": step.get("output_rows"),
                "status": step.get("status"),
                "implementation": step.get("implementation"),
                "output_checksum": step.get("output_checksum"),
            }
        )
    return pd.DataFrame(rows)


def field_lineage_frame(manifest: dict[str, Any], *, language: str) -> pd.DataFrame:
    """Return source-to-canonical field mappings for the selected language."""

    rule_key = "rule_zh" if language == "中文" else "rule_en"
    rows = [
        {
            "source_field": field.get("source_field"),
            "canonical_field": field.get("canonical_field"),
            "rule": field.get(rule_key, ""),
            "implementation": field.get("implementation"),
        }
        for field in manifest.get("lineage", {}).get("field_lineage", [])
    ]
    return pd.DataFrame(rows)


def row_reconciliation_frame(manifest: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(manifest.get("lineage", {}).get("row_reconciliation", []))


def flatten_mapping(payload: dict[str, Any], *, prefix: str = "") -> pd.DataFrame:
    """Flatten configuration and request mappings into readable key/value rows."""

    rows: list[dict[str, str]] = []
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            rows.extend(flatten_mapping(value, prefix=path).to_dict(orient="records"))
        else:
            display = ", ".join(map(str, value)) if isinstance(value, (list, tuple)) else str(value)
            rows.append({"parameter": path, "value": display})
    return pd.DataFrame(rows, columns=["parameter", "value"])


def trace_inventory(manifest: dict[str, Any]) -> pd.DataFrame:
    """Explain which evidence needed for exact reproduction is present."""

    lineage = manifest.get("lineage", {})
    reproduction = manifest.get("reproduction", {})
    items = [
        ("source_request", bool(lineage.get("source_request"))),
        ("raw_checksum", bool(manifest.get("raw", {}).get("checksum"))),
        ("processing_steps", bool(lineage.get("processing_steps"))),
        ("field_lineage", bool(lineage.get("field_lineage"))),
        ("quality_checks", bool(manifest.get("quality", {}).get("checks"))),
        ("curated_checksum", bool(manifest.get("curated", {}).get("checksum"))),
        ("git_commit", bool(manifest.get("git_commit"))),
        ("config_checksum", bool(reproduction.get("config_checksum"))),
        ("reproduction_command", bool(reproduction.get("command"))),
    ]
    return pd.DataFrame(
        [
            {"evidence": name, "status": "present" if present else "missing"}
            for name, present in items
        ]
    )


def research_artifacts_frame(manifest: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {"artifact": name, **payload}
        for name, payload in manifest.get("research", {}).get("artifacts", {}).items()
    ]
    return pd.DataFrame(rows)


def load_research_artifact(
    manifest: dict[str, Any], name: str, *, limit: int = 500
) -> pd.DataFrame:
    if limit < 1:
        raise ValueError("limit must be positive")
    payload = manifest.get("research", {}).get("artifacts", {}).get(name)
    if not payload or not payload.get("path"):
        raise ValueError(f"Research artifact is not recorded: {name}")
    path = Path(str(payload["path"]))
    if not path.exists():
        raise FileNotFoundError(f"Research artifact is unavailable: {path}")
    return pd.read_parquet(path).head(limit)
