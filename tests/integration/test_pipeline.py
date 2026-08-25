from pathlib import Path

import yaml

from quantforge.pipeline import run_pipeline_from_path

SOURCE_FIXTURE = Path(__file__).parents[1] / "fixtures" / "daily_bars.csv"


def test_pipeline_runs_raw_to_duckdb_and_is_idempotent(tmp_path: Path) -> None:
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
        "research": {"rebalance_frequency": "monthly"},
    }
    config_path = tmp_path / "mvp.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    first = run_pipeline_from_path(config_path)
    second = run_pipeline_from_path(config_path)

    assert first["status"] == "succeeded"
    assert first["quality"]["passed"] is True
    assert first["raw"]["checksum"] == second["raw"]["checksum"]
    assert first["curated"]["snapshot_id"] == second["curated"]["snapshot_id"]
    assert first["duckdb_summary"] == [
        {
            "source": "fixture",
            "row_count": 15,
            "instrument_count": 3,
            "first_trade_date": first["duckdb_summary"][0]["first_trade_date"],
            "last_trade_date": first["duckdb_summary"][0]["last_trade_date"],
        }
    ]
