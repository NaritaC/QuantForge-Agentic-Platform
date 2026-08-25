from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from quantforge.config import PipelineConfig, load_config
from quantforge.data.adapters import (
    BaoStockAdapter,
    FixtureDailyBarAdapter,
    SyntheticResearchAdapter,
)
from quantforge.data.adapters.base import AdapterBatch, DailyBarAdapter
from quantforge.data.catalog import query_daily_bar_summary
from quantforge.data.lineage import build_daily_bar_lineage
from quantforge.data.normalize import normalize_daily_bars
from quantforge.data.quality import validate_daily_bars
from quantforge.data.reference import (
    normalize_security_master,
    normalize_trade_calendar,
    validate_security_master,
    validate_trade_calendar,
)
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


def _build_adapter(config: PipelineConfig) -> DailyBarAdapter:
    if config.adapter == "fixture":
        return FixtureDailyBarAdapter(config.adapter_options["fixture_path"])
    if config.adapter == "baostock":
        required = {"symbols", "start_date", "end_date"}
        missing = sorted(required - set(config.adapter_options))
        if missing:
            raise ValueError(f"BaoStock adapter missing configuration: {', '.join(missing)}")
        return BaoStockAdapter(
            symbols=config.adapter_options["symbols"],
            start_date=str(config.adapter_options["start_date"]),
            end_date=str(config.adapter_options["end_date"]),
            adjustflag=str(config.adapter_options.get("adjustflag", "3")),
            timeout_seconds=float(config.adapter_options.get("timeout_seconds", 30.0)),
        )
    if config.adapter == "synthetic_fixture":
        return SyntheticResearchAdapter(**config.adapter_options)
    raise ValueError(f"Unsupported adapter: {config.adapter!r}")


def _persist_raw(config: PipelineConfig, batch: AdapterBatch):
    store = RawStore(config.storage.raw_dir)
    common = {
        "dataset": batch.dataset,
        "source": batch.source,
        "adapter_version": batch.adapter_version,
        "request": batch.request,
    }
    if batch.source_path is not None:
        return store.persist_file(batch.source_path, **common)
    if batch.raw_payload is not None:
        return store.persist_bytes(
            batch.raw_payload,
            suffix=batch.raw_suffix,
            source_filename=batch.source_filename,
            **common,
        )
    raise ValueError(f"Adapter {batch.source!r} returned no Raw payload")


def _build_reference_dataset(
    config: PipelineConfig,
    batch: AdapterBatch,
    *,
    run_dir: Path,
) -> dict[str, Any]:
    raw = _persist_raw(config, batch)
    if batch.dataset == "trade_calendar":
        frame = normalize_trade_calendar(
            batch.frame, source=batch.source, ingested_at=raw.ingested_at
        )
        quality = validate_trade_calendar(frame)
        sort_columns = ["trade_date"]
    elif batch.dataset == "security_master":
        frame = normalize_security_master(
            batch.frame, source=batch.source, ingested_at=raw.ingested_at
        )
        quality = validate_security_master(frame)
        sort_columns = ["instrument_id"]
    else:
        raise ValueError(f"Unsupported reference dataset: {batch.dataset}")
    _write_json(run_dir / f"quality-{batch.dataset}.json", quality.to_dict())
    if config.fail_on_error:
        quality.raise_if_failed()
    staging = ParquetSnapshotStore(config.storage.staging_dir, layer="staging").write(
        frame, dataset=batch.dataset
    )
    curated_frame = frame.sort_values(sort_columns, kind="stable").reset_index(drop=True)
    curated = ParquetSnapshotStore(config.storage.curated_dir, layer="curated").write(
        curated_frame, dataset=batch.dataset
    )
    return {
        "raw": {
            "checksum": raw.checksum,
            "ingested_at": raw.ingested_at.isoformat(),
            "data_path": str(raw.data_path),
            "manifest_path": str(raw.manifest_path),
        },
        "staging": snapshot_to_dict(staging),
        "curated": snapshot_to_dict(curated),
        "quality": quality.to_dict(),
    }


def _reproduction_metadata(config: PipelineConfig, config_path: Path | None) -> dict[str, Any]:
    if config_path is None:
        return {
            "config_path": None,
            "config_checksum": None,
            "command": None,
        }
    resolved = config_path.resolve()
    try:
        display_path = resolved.relative_to(config.project_root).as_posix()
    except ValueError:
        display_path = str(resolved)
    return {
        "config_path": display_path,
        "config_checksum": hashlib.sha256(resolved.read_bytes()).hexdigest(),
        "command": f"python -m quantforge pipeline --config {display_path}",
    }


def run_pipeline(
    config: PipelineConfig, *, config_path: str | Path | None = None
) -> dict[str, Any]:
    started_at = datetime.now(UTC)
    run_id = f"{started_at:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    run_dir = config.storage.artifacts_dir / run_id

    adapter = _build_adapter(config)
    batch = adapter.fetch_daily_bars()
    if batch.source != config.source:
        raise ValueError(
            f"Configured source {config.source!r} does not match adapter source {batch.source!r}"
        )
    raw = _persist_raw(config, batch)

    reference_data: dict[str, Any] = {}
    if isinstance(adapter, (BaoStockAdapter, SyntheticResearchAdapter)):
        for reference_batch in (
            adapter.fetch_trade_calendar(),
            adapter.fetch_security_master(),
        ):
            reference_data[reference_batch.dataset] = _build_reference_dataset(
                config, reference_batch, run_dir=run_dir
            )

    staging = normalize_daily_bars(
        batch.frame,
        source=batch.source,
        ingested_at=raw.ingested_at,
    )
    quality = validate_daily_bars(staging)
    quality_payload = quality.to_dict()
    _write_json(run_dir / "quality.json", quality_payload)
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
    lineage = build_daily_bar_lineage(
        source=batch.source,
        adapter_version=batch.adapter_version,
        request=batch.request,
        raw_rows=len(batch.frame),
        raw_checksum=raw.checksum,
        staging_rows=staging_snapshot.row_count,
        staging_checksum=staging_snapshot.checksum,
        curated_rows=curated_snapshot.row_count,
        curated_checksum=curated_snapshot.checksum,
        quality=quality_payload,
    )

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
            "adapter_options": config.adapter_options,
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
        "quality": quality_payload,
        "duckdb_summary": sql_summary,
        "reference_data": reference_data,
        "lineage": lineage,
        "reproduction": _reproduction_metadata(
            config, Path(config_path) if config_path is not None else None
        ),
    }
    _write_json(run_dir / "run.json", manifest)
    _write_json(config.storage.artifacts_dir / "latest.json", manifest)
    return manifest


def run_pipeline_from_path(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    return run_pipeline(load_config(config_path), config_path=config_path)
