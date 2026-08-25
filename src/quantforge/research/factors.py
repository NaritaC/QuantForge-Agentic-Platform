from __future__ import annotations

from collections.abc import Iterable
from datetime import date

import pandas as pd


def _winsorized_zscore(values: pd.Series, mad_multiplier: float) -> pd.Series:
    median = values.median()
    mad = (values - median).abs().median()
    clipped = (
        values
        if pd.isna(mad) or mad == 0
        else values.clip(median - mad_multiplier * mad, median + mad_multiplier * mad)
    )
    standard_deviation = clipped.std(ddof=0)
    if pd.isna(standard_deviation) or standard_deviation == 0:
        return pd.Series(0.0, index=values.index, dtype="float64")
    return (clipped - clipped.mean()) / standard_deviation


def compute_price_factors(
    daily_bars: pd.DataFrame,
    universe: pd.DataFrame,
    *,
    momentum_lookback_days: int = 252,
    momentum_skip_days: int = 21,
    volatility_window_days: int = 60,
    volatility_min_observations: int = 48,
    winsor_mad_multiplier: float = 5.0,
) -> pd.DataFrame:
    """Compute close-known price factors only at point-in-time universe dates."""

    if momentum_lookback_days <= momentum_skip_days or momentum_skip_days < 1:
        raise ValueError("Momentum lookback must exceed a positive skip window")
    if not 1 < volatility_min_observations <= volatility_window_days:
        raise ValueError("Volatility observations must be within the rolling window")
    if winsor_mad_multiplier <= 0:
        raise ValueError("MAD multiplier must be positive")
    required = {"instrument_id", "trade_date", "close", "preclose"}
    missing = sorted(required - set(daily_bars.columns))
    if missing:
        raise ValueError(f"Daily bars missing factor columns: {', '.join(missing)}")
    universe_required = {"instrument_id", "rebalance_date"}
    missing_universe = sorted(universe_required - set(universe.columns))
    if missing_universe:
        raise ValueError(f"Universe missing factor keys: {', '.join(missing_universe)}")

    bars = daily_bars.loc[:, list(required)].copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    bars = bars.sort_values(["instrument_id", "trade_date"], kind="stable")
    grouped = bars.groupby("instrument_id", sort=False)
    bars["momentum_12_1"] = grouped["close"].transform(
        lambda values: values.shift(momentum_skip_days) / values.shift(momentum_lookback_days) - 1.0
    )
    bars["daily_return"] = bars["close"] / bars["preclose"] - 1.0
    bars["low_volatility_60d"] = -grouped["daily_return"].transform(
        lambda values: values.rolling(
            volatility_window_days, min_periods=volatility_min_observations
        ).std(ddof=0)
    )

    eligible = universe.copy()
    eligible["rebalance_date"] = pd.to_datetime(eligible["rebalance_date"]).dt.normalize()
    factors = eligible.merge(
        bars[
            [
                "instrument_id",
                "trade_date",
                "momentum_12_1",
                "low_volatility_60d",
            ]
        ],
        left_on=["instrument_id", "rebalance_date"],
        right_on=["instrument_id", "trade_date"],
        how="left",
        validate="one_to_one",
    ).drop(columns="trade_date")
    factors = factors.dropna(subset=["momentum_12_1", "low_volatility_60d"]).copy()
    for raw_column in ("momentum_12_1", "low_volatility_60d"):
        z_column = f"{raw_column}_z"
        factors[z_column] = factors.groupby("rebalance_date", group_keys=False)[
            raw_column
        ].transform(lambda values: _winsorized_zscore(values, winsor_mad_multiplier))
    factors["composite_score"] = factors[["momentum_12_1_z", "low_volatility_60d_z"]].mean(axis=1)
    factors = factors.sort_values(
        ["rebalance_date", "composite_score", "instrument_id"],
        ascending=[True, False, True],
        kind="stable",
    )
    factors["factor_rank"] = factors.groupby("rebalance_date").cumcount() + 1
    factors["signal_available_at"] = factors["rebalance_date"]
    return factors.reset_index(drop=True)


def build_equal_weight_signals(
    factors: pd.DataFrame,
    *,
    portfolio_size: int,
) -> pd.DataFrame:
    """Select the highest composite scores and emit close-known target weights."""

    if portfolio_size <= 0:
        raise ValueError("Portfolio size must be positive")
    required = {"rebalance_date", "instrument_id", "composite_score", "factor_rank"}
    missing = sorted(required - set(factors.columns))
    if missing:
        raise ValueError(f"Factors missing signal columns: {', '.join(missing)}")
    selected = factors.loc[factors["factor_rank"] <= portfolio_size].copy()
    counts = selected.groupby("rebalance_date")["instrument_id"].transform("count")
    selected["target_weight"] = 1.0 / counts
    selected = selected.rename(columns={"rebalance_date": "signal_date"})
    return selected[
        [
            "signal_date",
            "instrument_id",
            "target_weight",
            "factor_rank",
            "composite_score",
            "signal_available_at",
        ]
    ].reset_index(drop=True)


def select_rebalance_dates(
    trading_dates: Iterable[date | str | pd.Timestamp], *, frequency: str
) -> list[pd.Timestamp]:
    """Select period-end signal dates and exclude the final date without a next-open execution."""

    dates = pd.Series(pd.to_datetime(list(trading_dates))).dropna().drop_duplicates().sort_values()
    if len(dates) < 2:
        return []
    frame = pd.DataFrame({"trade_date": dates.iloc[:-1]})
    if frequency == "monthly":
        periods = frame["trade_date"].dt.to_period("M")
    elif frequency == "weekly":
        periods = frame["trade_date"].dt.to_period("W-FRI")
    else:
        raise ValueError(f"Unsupported rebalance frequency: {frequency}")
    return frame.groupby(periods, sort=True)["trade_date"].max().tolist()
