from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from quantforge.settings import load_local_env


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
    adapter_options: dict[str, Any]
    dataset: str
    source: str
    fail_on_error: bool
    storage: StorageConfig
    research: dict[str, Any]


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def _reject_inline_secrets(options: dict[str, Any]) -> None:
    sensitive_markers = ("token", "password", "secret", "api_key", "private_key")
    unsafe = sorted(
        key
        for key in options
        if any(marker in key.lower() for marker in sensitive_markers)
        and not key.lower().endswith("_env")
    )
    if unsafe:
        raise ValueError(
            "Secrets must not be stored in YAML. Configure them in the local .env file and "
            f"reference environment-variable names instead: {', '.join(unsafe)}"
        )


def load_config(path: str | Path) -> PipelineConfig:
    config_path = Path(path).resolve()
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Configuration must be a mapping: {config_path}")

    project_value = payload.get("project_root", "..")
    project_root = _resolve(config_path.parent, project_value)
    load_local_env(project_root)
    pipeline = payload.get("pipeline", {})
    storage = payload.get("storage", {})

    required_pipeline = {"adapter", "dataset", "source"}
    missing = sorted(required_pipeline - set(pipeline))
    if missing:
        raise ValueError(f"Missing pipeline configuration keys: {', '.join(missing)}")

    adapter_name = str(pipeline["adapter"])
    adapter_options = {
        key: value for key, value in pipeline.items() if key not in {"adapter", "dataset", "source"}
    }
    _reject_inline_secrets(adapter_options)
    if adapter_name == "fixture":
        fixture_path = adapter_options.get("fixture_path")
        if not fixture_path:
            raise ValueError("Fixture adapter requires pipeline.fixture_path")
        adapter_options["fixture_path"] = _resolve(project_root, str(fixture_path))

    return PipelineConfig(
        project_root=project_root,
        adapter=adapter_name,
        adapter_options=adapter_options,
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
