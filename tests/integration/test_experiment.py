from pathlib import Path

import pandas as pd
import yaml

from quantforge.experiment import run_experiment_from_path


def test_synthetic_experiment_closes_data_to_portfolio_loop(tmp_path: Path) -> None:
    config = {
        "project_root": str(tmp_path),
        "pipeline": {
            "adapter": "synthetic_fixture",
            "dataset": "daily_bars",
            "source": "synthetic_fixture",
            "start_date": "2022-01-03",
            "periods": 320,
            "instrument_count": 5,
        },
        "quality": {"fail_on_error": True},
        "storage": {
            "raw_dir": "data/raw",
            "staging_dir": "data/staging",
            "curated_dir": "data/curated",
            "artifacts_dir": "artifacts/runs",
            "reports_dir": "reports",
        },
        "research": {
            "rebalance_frequency": "monthly",
            "universe_top_n": 5,
            "min_listing_days": 20,
            "liquidity_window_days": 20,
            "min_liquidity_observations": 15,
            "momentum_lookback_days": 60,
            "momentum_skip_days": 5,
            "volatility_window_days": 20,
            "volatility_min_observations": 15,
            "portfolio_size": 2,
            "require_price_limits": True,
        },
    }
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")

    manifest = run_experiment_from_path(config_path)
    research = manifest["research"]

    assert research["status"] == "succeeded"
    assert research["baseline_comparison"]["status"] == "deferred"
    assert set(research["artifacts"]) == {
        "universe",
        "factors",
        "signals",
        "orders",
        "fills",
        "holdings",
        "nav",
    }
    assert all(Path(item["path"]).is_file() for item in research["artifacts"].values())
    fills = pd.read_parquet(research["artifacts"]["fills"]["path"])
    assert not fills.empty
    assert (fills["trade_date"] > fills["signal_date"]).all()
    assert research["metrics"]["trade_count"] == len(fills)
