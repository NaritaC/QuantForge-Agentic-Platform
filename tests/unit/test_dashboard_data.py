from pathlib import Path

import pytest
import yaml

from quantforge.pipeline import run_pipeline_from_path
from quantforge.ui.data import (
    discover_runs,
    load_daily_bar_preview,
    load_indexed_close_series,
    quality_issues_frame,
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
    preview = load_daily_bar_preview(records[0].manifest, limit=5)
    prices = load_indexed_close_series(records[0].manifest)

    assert [record.run_id for record in records] == [manifest["run_id"]]
    assert len(preview) == 5
    assert preview.iloc[0]["trade_date"] >= preview.iloc[-1]["trade_date"]
    assert prices["instrument_id"].nunique() == 3
    assert prices.groupby("instrument_id")["indexed_close"].first().eq(100).all()


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

    assert set(issues["severity"]) == {"warning"}
    assert "missing_price_limits" in set(issues["check"])


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
    assert len(app.metric) >= 5
    assert len(app.dataframe) >= 1
