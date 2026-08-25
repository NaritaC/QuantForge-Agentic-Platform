from __future__ import annotations

import json
import platform
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quantforge.config import PipelineConfig, load_config
from quantforge.data.adapters import FixtureDailyBarAdapter
from quantforge.data.catalog import query_daily_bar_summary
from quantforge.data.normalize import normalize_daily_bars
from quantforge.data.quality import validate_daily_bars
from quantforge.data.storage import (
    ParquetSnapshotStore,
    RawStore,
    snapshot_to_dict,
)


def _git_commit(project_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )


def run_pipeline(config: PipelineConfig) -> dict[str, Any]:
    if config.adapter != "fixture":
        raise ValueError(f"Day-1 slice supports adapter='fixture', got {config.adapter!r}")

    started_at = datetime.now(UTC)
    run_id = f"{started_at:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = config.storage.artifacts_dir / run_id

    adapter = FixtureDailyBarAdapter(config.fixture_path)
    batch = adapter.fetch_daily_bars()
    raw = RawStore(config.storage.raw_dir).persist_file(
        batch.source_path,
        dataset=batch.dataset,
        source=batch.source,
        adapter_version=batch.adapter_version,
        request=batch.request,
    )

    staging = normalize_daily_bars(
        batch.frame,
        source=config.source,
        ingested_at=raw.ingested_at,
    )
    quality = validate_daily_bars(staging)
    _write_json(run_dir / "quality.json", quality.to_dict())
    if config.fail_on_error:
        quality.raise_if_failed()

    staging_snapshot = ParquetSnapshotStore(config.storage.staging_dir, layer="staging").write(
        staging, dataset=config.dataset
    )

    curated = staging.sort_values(["trade_date", "instrument_id"], kind="stable").reset_index(
        drop=True
    )
    curated_snapshot = ParquetSnapshotStore(config.storage.curated_dir, layer="curated").write(
        curated, dataset=config.dataset
    )
    sql_summary = query_daily_bar_summary(curated_snapshot.path)

    completed_at = datetime.now(UTC)
    manifest = {
        "run_id": run_id,
        "status": "succeeded" if quality.passed else "completed_with_quality_errors",
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": (completed_at - started_at).total_seconds(),
        "git_commit": _git_commit(config.project_root),
        "python": sys.version,
        "platform": platform.platform(),
        "config": {
            "adapter": config.adapter,
            "dataset": config.dataset,
            "source": config.source,
            "research": config.research,
        },
        "raw": {
            "checksum": raw.checksum,
            "ingested_at": raw.ingested_at.isoformat(),
            "data_path": str(raw.data_path),
            "manifest_path": str(raw.manifest_path),
        },
        "staging": snapshot_to_dict(staging_snapshot),
        "curated": snapshot_to_dict(curated_snapshot),
        "quality": quality.to_dict(),
        "duckdb_summary": sql_summary,
    }
    _write_json(run_dir / "run.json", manifest)
    _write_json(config.storage.artifacts_dir / "latest.json", manifest)
    return manifest


def run_pipeline_from_path(path: str | Path) -> dict[str, Any]:
    return run_pipeline(load_config(path))
