from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class StorageConfig:
    raw_dir: Path
    staging_dir: Path
    curated_dir: Path
    artifacts_dir: Path
    reports_dir: Path


@dataclass(frozen=True)
class PipelineConfig:
    project_root: Path
    adapter: str
    fixture_path: Path
    dataset: str
    source: str
    fail_on_error: bool
    storage: StorageConfig
    research: dict[str, Any]


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def load_config(path: str | Path) -> PipelineConfig:
    config_path = Path(path).resolve()
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration must be a mapping: {config_path}")

    project_value = payload.get("project_root", "..")
    project_root = _resolve(config_path.parent, project_value)
    pipeline = payload.get("pipeline", {})
    storage = payload.get("storage", {})

    required_pipeline = {"adapter", "fixture_path", "dataset", "source"}
    missing = sorted(required_pipeline - set(pipeline))
    if missing:
        raise ValueError(f"Missing pipeline configuration keys: {', '.join(missing)}")

    return PipelineConfig(
        project_root=project_root,
        adapter=str(pipeline["adapter"]),
        fixture_path=_resolve(project_root, str(pipeline["fixture_path"])),
        dataset=str(pipeline["dataset"]),
        source=str(pipeline["source"]),
        fail_on_error=bool(payload.get("quality", {}).get("fail_on_error", True)),
        storage=StorageConfig(
            raw_dir=_resolve(project_root, str(storage.get("raw_dir", "data/raw"))),
            staging_dir=_resolve(project_root, str(storage.get("staging_dir", "data/staging"))),
            curated_dir=_resolve(project_root, str(storage.get("curated_dir", "data/curated"))),
            artifacts_dir=_resolve(
                project_root, str(storage.get("artifacts_dir", "artifacts/runs"))
            ),
            reports_dir=_resolve(project_root, str(storage.get("reports_dir", "reports"))),
        ),
        research=dict(payload.get("research", {})),
    )
