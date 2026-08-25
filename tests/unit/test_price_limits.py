from decimal import Decimal

import pandas as pd

from quantforge.data.price_limits import (
    PRICE_LIMIT_POLICY_VERSION,
    a_share_limit_rate,
    derive_a_share_price_limits,
)


def test_limit_rate_covers_board_reforms_and_st_precedence() -> None:
    assert a_share_limit_rate("600000.SH", "2024-01-02", is_st=False) == Decimal("0.10")
    assert a_share_limit_rate("688001.SH", "2024-01-02", is_st=False) == Decimal("0.20")
    assert a_share_limit_rate("300001.SZ", "2020-08-21", is_st=False) == Decimal("0.10")
    assert a_share_limit_rate("300001.SZ", "2020-08-24", is_st=False) == Decimal("0.20")
    assert a_share_limit_rate("430047.BJ", "2024-01-02", is_st=False) == Decimal("0.30")
    assert a_share_limit_rate("688001.SH", "2024-01-02", is_st=True) == Decimal("0.20")
    assert a_share_limit_rate("300001.SZ", "2024-01-02", is_st=True) == Decimal("0.20")
    assert a_share_limit_rate("600000.SH", "2025-01-02", is_st=True) == Decimal("0.05")
    assert a_share_limit_rate("600000.SH", "2026-07-06", is_st=True) == Decimal("0.10")


def test_derivation_uses_half_up_fen_rounding_and_records_policy() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "sh.600000",
                "trade_date": "2024-01-02",
                "preclose": "10.05",
                "is_st": "0",
            }
        ]
    )

    result = derive_a_share_price_limits(
        frame,
        listing_dates={"600000.SH": "1999-11-10"},
    )

    assert result.loc[0, "upper_limit"] == 11.06
    assert result.loc[0, "lower_limit"] == 9.05
    assert result.loc[0, "price_limit_source"] == PRICE_LIMIT_POLICY_VERSION


def test_recent_ipo_guard_keeps_limits_unavailable() -> None:
    frame = pd.DataFrame(
        [
            {
                "symbol": "sz.301001",
                "trade_date": "2024-01-10",
                "preclose": "25.00",
                "is_st": "0",
            }
        ]
    )

    result = derive_a_share_price_limits(
        frame,
        listing_dates={"301001.SZ": "2024-01-02"},
    )

    assert pd.isna(result.loc[0, "upper_limit"])
    assert pd.isna(result.loc[0, "lower_limit"])
    assert result.loc[0, "price_limit_source"] == "unavailable_recent_ipo"
