from __future__ import annotations

from bisect import bisect_left
from collections.abc import Iterable
from datetime import date

import pandas as pd


def _as_dates(values: pd.Series) -> pd.Series:
    return pd.to_datetime(values, errors="coerce").dt.normalize()


def build_dynamic_universe(
    daily_bars: pd.DataFrame,
    security_master: pd.DataFrame,
    trade_calendar: pd.DataFrame,
    rebalance_dates: Iterable[date | str],
    *,
    top_n: int = 300,
    min_listing_days: int = 120,
    liquidity_window: int = 60,
    min_liquidity_observations: int = 48,
) -> pd.DataFrame:
    """Build an as-of universe without using today's index constituents."""
    if top_n <= 0 or min_listing_days <= 0 or liquidity_window <= 0:
        raise ValueError("Universe window and threshold parameters must be positive")
    if not 0 < min_liquidity_observations <= liquidity_window:
        raise ValueError("Liquidity observations must be within the rolling window")

    bar_required = {"instrument_id", "trade_date", "amount", "is_st", "trade_status"}
    master_required = {"instrument_id", "list_date", "delist_date"}
    calendar_required = {"trade_date", "is_trading_day"}
    for label, frame, required in (
        ("daily_bars", daily_bars, bar_required),
        ("security_master", security_master, master_required),
        ("trade_calendar", trade_calendar, calendar_required),
    ):
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"{label} missing columns: {', '.join(missing)}")

    bars = daily_bars.copy()
    bars["trade_date"] = _as_dates(bars["trade_date"])
    bars["amount"] = pd.to_numeric(bars["amount"], errors="coerce")
    master = security_master.copy()
    master["list_date"] = _as_dates(master["list_date"])
    master["delist_date"] = _as_dates(master["delist_date"])
    calendar = trade_calendar.copy()
    calendar["trade_date"] = _as_dates(calendar["trade_date"])
    trading_days = (
        calendar.loc[calendar["is_trading_day"].astype(bool), "trade_date"]
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    if not trading_days:
        raise ValueError("Trade calendar contains no trading days")
    if master["instrument_id"].duplicated().any():
        raise ValueError("Security master contains duplicate instruments")
    if bars.duplicated(["instrument_id", "trade_date"]).any():
        raise ValueError("Daily bars contain duplicate instrument/date rows")

    outputs: list[pd.DataFrame] = []
    for raw_rebalance_date in rebalance_dates:
        rebalance_date = pd.Timestamp(raw_rebalance_date).normalize()
        available_days = [day for day in trading_days if day <= rebalance_date]
        if not available_days or available_days[-1] != rebalance_date:
            raise ValueError(f"Rebalance date is not a trading day: {rebalance_date}")
        window_days = set(available_days[-liquidity_window:])
        window = bars.loc[bars["trade_date"].isin(window_days)]
        liquidity = (
            window.groupby("instrument_id", as_index=False)
            .agg(
                liquidity_score=("amount", "mean"),
                liquidity_observations=("amount", "count"),
            )
            .loc[lambda frame: frame["liquidity_observations"] >= min_liquidity_observations]
        )
        state = bars.loc[
            bars["trade_date"].eq(rebalance_date),
            ["instrument_id", "is_st", "trade_status"],
        ]
        candidates = master.merge(liquidity, on="instrument_id", how="inner").merge(
            state, on="instrument_id", how="inner"
        )
        candidates["listing_age_days"] = [
            len(available_days) - bisect_left(available_days, listed) if pd.notna(listed) else 0
            for listed in candidates["list_date"]
        ]
        active = candidates["list_date"].le(rebalance_date) & (
            candidates["delist_date"].isna() | candidates["delist_date"].gt(rebalance_date)
        )
        eligible = candidates.loc[
            active
            & candidates["listing_age_days"].ge(min_listing_days)
            & ~candidates["is_st"].astype(bool)
        ].copy()
        eligible = eligible.sort_values(
            ["liquidity_score", "instrument_id"], ascending=[False, True], kind="stable"
        ).head(top_n)
        eligible["liquidity_rank"] = range(1, len(eligible) + 1)
        eligible["liquidity_window_days"] = liquidity_window
        eligible["rebalance_date"] = rebalance_date
        outputs.append(
            eligible.loc[
                :,
                [
                    "rebalance_date",
                    "instrument_id",
                    "liquidity_score",
                    "liquidity_observations",
                    "liquidity_window_days",
                    "liquidity_rank",
                    "listing_age_days",
                    "trade_status",
                ],
            ]
        )

    if not outputs:
        return pd.DataFrame(
            columns=[
                "rebalance_date",
                "instrument_id",
                "liquidity_score",
                "liquidity_observations",
                "liquidity_window_days",
                "liquidity_rank",
                "listing_age_days",
                "trade_status",
            ]
        )
    return pd.concat(outputs, ignore_index=True)
