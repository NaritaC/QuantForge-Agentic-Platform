from pathlib import Path

import pytest
import yaml

from quantforge.pipeline import run_pipeline_from_path
from quantforge.ui.data import (
    discover_runs,
    field_lineage_frame,
    load_daily_bar_preview,
    load_indexed_close_series,
    load_raw_preview,
    processing_steps_frame,
    quality_checks_frame,
    quality_issues_frame,
    row_reconciliation_frame,
    trace_inventory,
)

SOURCE_FIXTURE = Path(__file__).parents[1] / "fixtures" / "daily_bars.csv"


def _run_fixture_pipeline(tmp_path: Path) -> dict:
    fixture = tmp_path / "daily_bars.csv"
    fixture.write_bytes(SOURCE_FIXTURE.read_bytes())
    config = {
        "project_root": str(tmp_path),
        "pipeline": {
            "adapter": "fixture",
            "fixture_path": str(fixture),
            "dataset": "daily_bars",
            "source": "fixture",
        },
        "quality": {"fail_on_error": True},
        "storage": {
            "raw_dir": "data/raw",
            "staging_dir": "data/staging",
            "curated_dir": "data/curated",
            "artifacts_dir": "artifacts/runs",
            "reports_dir": "reports",
        },
    }
    path = tmp_path / "dashboard-test.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return run_pipeline_from_path(path)


def test_dashboard_read_model_discovers_and_queries_run(tmp_path: Path) -> None:
    manifest = _run_fixture_pipeline(tmp_path)

    records = discover_runs(tmp_path)
    raw = load_raw_preview(records[0].manifest, limit=5)
    preview = load_daily_bar_preview(records[0].manifest, limit=5)
    prices = load_indexed_close_series(records[0].manifest)
    steps = processing_steps_frame(records[0].manifest, language="中文")
    fields = field_lineage_frame(records[0].manifest, language="English")
    reconciliation = row_reconciliation_frame(records[0].manifest)
    inventory = trace_inventory(records[0].manifest)

    assert [record.run_id for record in records] == [manifest["run_id"]]
    assert len(raw) == 5
    assert len(preview) == 5
    assert preview.iloc[0]["trade_date"] >= preview.iloc[-1]["trade_date"]
    assert prices["instrument_id"].nunique() == 3
    assert prices.groupby("instrument_id")["indexed_close"].first().eq(100).all()
    assert len(steps) == 6
    assert len(fields) == 16
    assert reconciliation["delta_from_previous"].dropna().eq(0).all()
    assert int(inventory["status"].eq("present").sum()) == 8
    assert inventory.loc[inventory["evidence"].eq("git_commit"), "status"].item() == "missing"


def test_quality_issues_frame_flattens_warnings(tmp_path: Path) -> None:
    manifest = _run_fixture_pipeline(tmp_path)
    manifest["quality"]["issues"] = [
        {
            "check": "missing_price_limits",
            "severity": "warning",
            "count": 15,
            "message": "Price limits are unavailable.",
            "sample": [],
        }
    ]

    issues = quality_issues_frame(manifest)
    checks = quality_checks_frame(manifest)

    assert set(issues["severity"]) == {"warning"}
    assert "missing_price_limits" in set(issues["check"])
    assert len(checks) == 11


def test_discover_runs_ignores_malformed_manifest(tmp_path: Path) -> None:
    malformed = tmp_path / "artifacts" / "runs" / "broken" / "run.json"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("not-json", encoding="utf-8")

    assert discover_runs(tmp_path) == []


def test_dashboard_app_renders_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    streamlit_testing = pytest.importorskip("streamlit.testing.v1")
    _run_fixture_pipeline(tmp_path)
    monkeypatch.setenv("QUANTFORGE_PROJECT_ROOT", str(tmp_path))
    app_path = Path(__file__).parents[2] / "src" / "quantforge" / "ui" / "app.py"

    app = streamlit_testing.AppTest.from_file(app_path, default_timeout=10).run()

    assert not app.exception
    assert len(app.metric) >= 4
    assert len(app.dataframe) >= 1
    assert len(app.tabs) >= 5
