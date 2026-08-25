import pandas as pd
import pytest

from quantforge.research.backtest import run_next_open_backtest


def _bars(*, suspended_execution: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=3)
    return pd.DataFrame(
        {
            "trade_date": dates,
            "instrument_id": "A.SH",
            "open": [9.5, 10.0, 10.5],
            "close": [9.8, 11.0, 10.8],
            "trade_status": [
                "TRADE",
                "SUSPENDED" if suspended_execution else "TRADE",
                "TRADE",
            ],
            "upper_limit": [11.0, 11.0, 12.1],
            "lower_limit": [9.0, 9.0, 9.9],
        }
    )


def _signals() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "signal_date": [pd.Timestamp("2024-01-02")],
            "instrument_id": ["A.SH"],
            "target_weight": [1.0],
        }
    )


def test_backtest_executes_close_known_signal_at_next_open() -> None:
    result = run_next_open_backtest(
        _bars(),
        _signals(),
        initial_cash=10_000,
        commission_bps=0,
        minimum_commission=0,
        stamp_duty_bps=0,
        slippage_bps=0,
    )

    assert result.fills.iloc[0]["signal_date"] == pd.Timestamp("2024-01-02")
    assert result.fills.iloc[0]["trade_date"] == pd.Timestamp("2024-01-03")
    assert result.fills.iloc[0]["fill_price"] == pytest.approx(10.0)
    assert result.fills.iloc[0]["quantity"] == 1000
    assert result.nav.iloc[0]["nav"] == pytest.approx(1.1)


def test_suspended_order_retries_then_fills() -> None:
    result = run_next_open_backtest(
        _bars(suspended_execution=True),
        _signals(),
        initial_cash=10_000,
        commission_bps=0,
        minimum_commission=0,
        stamp_duty_bps=0,
        slippage_bps=0,
        unfilled_retry_days=2,
    )

    assert result.orders["status"].tolist() == ["retry_pending", "filled"]
    assert result.orders.iloc[0]["reason"] == "suspended"
    assert result.fills.iloc[0]["trade_date"] == pd.Timestamp("2024-01-04")
