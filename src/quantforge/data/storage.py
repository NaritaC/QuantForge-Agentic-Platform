from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds


@dataclass(frozen=True)
class RawArtifact:
    dataset: str
    source: str
    checksum: str
    ingested_at: datetime
    data_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class ParquetSnapshot:
    layer: str
    dataset: str
    snapshot_id: str
    row_count: int
    path: Path
    checksum: str


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    os.replace(temporary, path)


class RawStore:
    """Content-addressed, append-only persistence for exact source bytes."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def persist_file(
        self,
        source_path: str | Path,
        *,
        dataset: str,
        source: str,
        adapter_version: str,
        request: dict[str, Any],
    ) -> RawArtifact:
        source_file = Path(source_path)
        content = source_file.read_bytes()
        checksum = hashlib.sha256(content).hexdigest()
        suffix = source_file.suffix.lower() or ".bin"
        folder = self.root / dataset / source / checksum[:2] / checksum
        data_path = folder / f"payload{suffix}"
        manifest_path = folder / "manifest.json"

        if manifest_path.exists() and data_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            return RawArtifact(
                dataset=dataset,
                source=source,
                checksum=checksum,
                ingested_at=datetime.fromisoformat(manifest["ingested_at"]),
                data_path=data_path,
                manifest_path=manifest_path,
            )

        folder.mkdir(parents=True, exist_ok=True)
        ingested_at = datetime.now(UTC)
        if not data_path.exists():
            shutil.copyfile(source_file, data_path)
        _atomic_json(
            manifest_path,
            {
                "dataset": dataset,
                "source": source,
                "source_filename": source_file.name,
                "checksum_algorithm": "sha256",
                "checksum": checksum,
                "ingested_at": ingested_at.isoformat(),
                "adapter_version": adapter_version,
                "request": request,
            },
        )
        return RawArtifact(dataset, source, checksum, ingested_at, data_path, manifest_path)


def _frame_checksum(frame: pd.DataFrame) -> str:
    stable = frame.copy()
    sort_columns = [column for column in ("instrument_id", "trade_date") if column in stable]
    if sort_columns:
        stable = stable.sort_values(sort_columns, kind="stable")
    payload = stable.to_csv(index=False, date_format="%Y-%m-%dT%H:%M:%S.%f%z").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ParquetSnapshotStore:
    """Immutable Parquet snapshots; an identical frame resolves to the same path."""

    def __init__(self, root: str | Path, *, layer: str) -> None:
        self.root = Path(root)
        self.layer = layer

    def write(self, frame: pd.DataFrame, *, dataset: str) -> ParquetSnapshot:
        checksum = _frame_checksum(frame)
        snapshot_id = checksum[:16]
        target = self.root / dataset / snapshot_id
        manifest_path = target / "_snapshot.json"
        if manifest_path.exists():
            return ParquetSnapshot(self.layer, dataset, snapshot_id, len(frame), target, checksum)

        temporary = target.parent / f".{snapshot_id}.{uuid.uuid4().hex}.tmp"
        temporary.mkdir(parents=True, exist_ok=False)
        output = frame.copy()
        output["trade_year"] = pd.to_datetime(output["trade_date"]).dt.year.astype("int16")
        table = pa.Table.from_pandas(output, preserve_index=False)
        ds.write_dataset(
            table,
            base_dir=str(temporary),
            format="parquet",
            partitioning=["trade_year"],
            partitioning_flavor="hive",
            existing_data_behavior="error",
        )
        _atomic_json(
            temporary / "_snapshot.json",
            {
                "layer": self.layer,
                "dataset": dataset,
                "snapshot_id": snapshot_id,
                "checksum_algorithm": "sha256",
                "checksum": checksum,
                "row_count": len(frame),
                "columns": list(frame.columns),
            },
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(temporary, target)
        except FileExistsError:
            shutil.rmtree(temporary)
        return ParquetSnapshot(self.layer, dataset, snapshot_id, len(frame), target, checksum)


def snapshot_to_dict(snapshot: ParquetSnapshot) -> dict[str, Any]:
    payload = asdict(snapshot)
    payload["path"] = str(snapshot.path)
    return payload
