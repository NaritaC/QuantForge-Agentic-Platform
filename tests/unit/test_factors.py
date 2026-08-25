import pandas as pd
import pytest

from quantforge.research.factors import (
    build_equal_weight_signals,
    compute_price_factors,
    select_rebalance_dates,
)


def _bars() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=10)
    rows = []
    for index, instrument in enumerate(("A.SH", "B.SH", "C.SH")):
        previous = 10.0 + index
        for day, trade_date in enumerate(dates):
            close = previous * (1.0 + 0.002 * (index + 1) + 0.001 * day)
            rows.append(
                {
                    "instrument_id": instrument,
                    "trade_date": trade_date,
                    "close": close,
                    "preclose": previous,
                }
            )
            previous = close
    return pd.DataFrame(rows)


def test_price_factors_are_point_in_time_and_build_equal_weights() -> None:
    bars = _bars()
    signal_date = pd.Timestamp("2024-01-10")
    universe = pd.DataFrame(
        {
            "rebalance_date": signal_date,
            "instrument_id": ["A.SH", "B.SH", "C.SH"],
        }
    )

    factors = compute_price_factors(
        bars,
        universe,
        momentum_lookback_days=4,
        momentum_skip_days=1,
        volatility_window_days=3,
        volatility_min_observations=2,
    )
    future_changed = bars.copy()
    future_changed.loc[future_changed["trade_date"] > signal_date, "close"] *= 20
    factors_after_future_change = compute_price_factors(
        future_changed,
        universe,
        momentum_lookback_days=4,
        momentum_skip_days=1,
        volatility_window_days=3,
        volatility_min_observations=2,
    )
    signals = build_equal_weight_signals(factors, portfolio_size=2)

    pd.testing.assert_series_equal(
        factors["composite_score"],
        factors_after_future_change["composite_score"],
        check_names=False,
    )
    assert len(signals) == 2
    assert signals["target_weight"].sum() == pytest.approx(1.0)
    assert signals["signal_available_at"].eq(signal_date).all()


def test_select_rebalance_dates_excludes_last_date_without_next_open() -> None:
    dates = pd.bdate_range("2024-01-02", "2024-02-29")

    selected = select_rebalance_dates(dates, frequency="monthly")

    assert selected == [pd.Timestamp("2024-01-31"), pd.Timestamp("2024-02-28")]
