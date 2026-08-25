from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from quantforge.config import PipelineConfig, load_config
from quantforge.pipeline import run_pipeline_from_path
from quantforge.research.backtest import BacktestResult, run_next_open_backtest
from quantforge.research.factors import (
    build_equal_weight_signals,
    compute_price_factors,
    select_rebalance_dates,
)
from quantforge.research.universe import build_dynamic_universe


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    os.replace(temporary, path)


def _write_frame(path: Path, frame: pd.DataFrame) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{uuid.uuid4().hex}.tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)
    return {
        "path": str(path),
        "row_count": len(frame),
        "checksum_algorithm": "sha256",
        "checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _load_snapshot(payload: dict[str, Any], label: str) -> pd.DataFrame:
    value = payload.get("curated", {}).get("path")
    if not value:
        raise ValueError(f"Experiment requires curated {label}")
    path = Path(str(value))
    if not path.exists():
        raise FileNotFoundError(f"Curated {label} is unavailable: {path}")
    return pd.read_parquet(path)


def _research_parameters(config: PipelineConfig) -> dict[str, Any]:
    values = config.research
    return {
        "rebalance_frequency": str(values.get("rebalance_frequency", "monthly")),
        "top_n": int(values.get("universe_top_n", 300)),
        "min_listing_days": int(values.get("min_listing_days", 120)),
        "liquidity_window": int(values.get("liquidity_window_days", 60)),
        "min_liquidity_observations": int(values.get("min_liquidity_observations", 48)),
        "momentum_lookback_days": int(values.get("momentum_lookback_days", 252)),
        "momentum_skip_days": int(values.get("momentum_skip_days", 21)),
        "volatility_window_days": int(values.get("volatility_window_days", 60)),
        "volatility_min_observations": int(values.get("volatility_min_observations", 48)),
        "winsor_mad_multiplier": float(values.get("winsor_mad_multiplier", 5.0)),
        "portfolio_size": int(values.get("portfolio_size", 30)),
        "initial_cash": float(values.get("initial_cash", 1_000_000.0)),
        "lot_size": int(values.get("lot_size", 100)),
        "commission_bps": float(values.get("commission_bps", 0.86)),
        "minimum_commission": float(values.get("minimum_commission", 5.0)),
        "stamp_duty_bps": float(values.get("stamp_duty_bps", 5.0)),
        "slippage_bps": float(values.get("slippage_bps", 2.0)),
        "unfilled_retry_days": int(values.get("unfilled_retry_days", 5)),
        "require_price_limits": bool(values.get("require_price_limits", True)),
    }


def _research_lineage(
    universe: pd.DataFrame,
    factors: pd.DataFrame,
    signals: pd.DataFrame,
    result: BacktestResult,
) -> list[dict[str, Any]]:
    return [
        {
            "order": 1,
            "step": "dynamic_universe",
            "implementation": "quantforge.research.universe:build_dynamic_universe",
            "output_rows": len(universe),
            "evidence": "listing age + lifecycle + ST state + trailing turnover rank",
        },
        {
            "order": 2,
            "step": "price_factors",
            "implementation": "quantforge.research.factors:compute_price_factors",
            "output_rows": len(factors),
            "evidence": "12-1 momentum + 60-day low volatility + MAD winsorization + z-score",
        },
        {
            "order": 3,
            "step": "target_weights",
            "implementation": "quantforge.research.factors:build_equal_weight_signals",
            "output_rows": len(signals),
            "evidence": "top composite ranks with equal target weights",
        },
        {
            "order": 4,
            "step": "orders_and_fills",
            "implementation": "quantforge.research.backtest:run_next_open_backtest",
            "output_rows": len(result.fills),
            "evidence": "next open + board lots + costs + suspension/limit retry",
        },
        {
            "order": 5,
            "step": "portfolio_accounting",
            "implementation": "quantforge.research.backtest:run_next_open_backtest",
            "output_rows": len(result.nav),
            "evidence": "cash + holdings + close valuation + NAV + deterministic metrics",
        },
    ]


def run_research(manifest: dict[str, Any], config: PipelineConfig) -> dict[str, Any]:
    """Complete one deterministic research loop from curated inputs to experiment evidence."""

    references = manifest.get("reference_data", {})
    if "trade_calendar" not in references or "security_master" not in references:
        raise ValueError(
            "A closed-loop experiment requires curated trade_calendar and security_master"
        )
    bars = _load_snapshot(manifest, "daily_bars")
    calendar = _load_snapshot(references["trade_calendar"], "trade_calendar")
    master = _load_snapshot(references["security_master"], "security_master")
    parameters = _research_parameters(config)
    trading_dates = calendar.loc[calendar["is_trading_day"].astype(bool), "trade_date"]
    rebalance_dates = select_rebalance_dates(
        trading_dates, frequency=parameters["rebalance_frequency"]
    )
    universe = build_dynamic_universe(
        bars,
        master,
        calendar,
        rebalance_dates,
        top_n=parameters["top_n"],
        min_listing_days=parameters["min_listing_days"],
        liquidity_window=parameters["liquidity_window"],
        min_liquidity_observations=parameters["min_liquidity_observations"],
    )
    factors = compute_price_factors(
        bars,
        universe,
        momentum_lookback_days=parameters["momentum_lookback_days"],
        momentum_skip_days=parameters["momentum_skip_days"],
        volatility_window_days=parameters["volatility_window_days"],
        volatility_min_observations=parameters["volatility_min_observations"],
        winsor_mad_multiplier=parameters["winsor_mad_multiplier"],
    )
    signals = build_equal_weight_signals(factors, portfolio_size=parameters["portfolio_size"])
    if signals.empty:
        raise ValueError("No research signals were produced; inspect warm-up and universe settings")
    result = run_next_open_backtest(
        bars,
        signals,
        initial_cash=parameters["initial_cash"],
        lot_size=parameters["lot_size"],
        commission_bps=parameters["commission_bps"],
        minimum_commission=parameters["minimum_commission"],
        stamp_duty_bps=parameters["stamp_duty_bps"],
        slippage_bps=parameters["slippage_bps"],
        unfilled_retry_days=parameters["unfilled_retry_days"],
        require_price_limits=parameters["require_price_limits"],
    )

    run_dir = config.storage.artifacts_dir / str(manifest["run_id"])
    research_dir = run_dir / "research"
    artifacts = {
        "universe": _write_frame(research_dir / "universe.parquet", universe),
        "factors": _write_frame(research_dir / "factors.parquet", factors),
        "signals": _write_frame(research_dir / "signals.parquet", signals),
        "orders": _write_frame(research_dir / "orders.parquet", result.orders),
        "fills": _write_frame(research_dir / "fills.parquet", result.fills),
        "holdings": _write_frame(research_dir / "holdings.parquet", result.holdings),
        "nav": _write_frame(research_dir / "nav.parquet", result.nav),
    }
    _write_json(research_dir / "metrics.json", result.metrics)
    limitations: list[str] = []
    source = manifest.get("config", {}).get("source")
    source_request = manifest.get("lineage", {}).get("source_request", {})
    if source == "synthetic_fixture":
        limitations.append(
            "Synthetic fixture proves functionality and is not market research evidence."
        )
    if source == "baostock" and source_request.get("symbols"):
        limitations.append(
            "The configured symbol list is a real-data integration sample, not a "
            "point-in-time full-market constituent history."
        )
    if source_request.get("price_limit_mode") == "derived_exchange_rules":
        limitations.append(
            "Daily price limits are deterministic exchange-rule estimates; validate exceptional "
            "sessions against vendor snapshot limits before treating results as research evidence."
        )

    research = {
        "status": "succeeded",
        "completed_at": datetime.now(UTC).isoformat(),
        "strategy_id": "price_momentum_low_volatility_v1",
        "data_run_id": manifest["run_id"],
        "data_snapshot_id": manifest.get("curated", {}).get("snapshot_id"),
        "parameters": parameters,
        "lineage": _research_lineage(universe, factors, signals, result),
        "leakage_controls": [
            "signals are formed only on period-end close-known data",
            "orders are first attempted on the next trading-day open",
            "universe membership is recomputed as-of each signal date",
            "factor windows use only current and prior observations",
        ],
        "artifacts": artifacts,
        "metrics": result.metrics,
        "baseline_comparison": {
            "status": "deferred",
            "strategies": ["buy_and_hold", "grid_trading", "periodic_investment"],
        },
        "limitations": limitations,
    }
    _write_json(research_dir / "experiment.json", research)
    manifest["research"] = research
    _write_json(run_dir / "run.json", manifest)
    _write_json(config.storage.artifacts_dir / "latest.json", manifest)
    return manifest


def run_experiment_from_path(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    manifest = run_pipeline_from_path(config_path)
    return run_research(manifest, load_config(config_path))
