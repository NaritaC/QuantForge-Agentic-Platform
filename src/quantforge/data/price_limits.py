from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from quantforge.data.normalize import normalize_instrument_id

PRICE_LIMIT_POLICY_VERSION = "cn_a_share_exchange_rules_v1"
CHINEXT_REFORM_DATE = date(2020, 8, 24)
MAINBOARD_ST_REFORM_DATE = date(2026, 7, 6)
IPO_GUARD_CALENDAR_DAYS = 30


def a_share_limit_rate(
    instrument_id: str,
    trade_date: object,
    *,
    is_st: bool,
) -> Decimal:
    """Return the standard daily A-share limit rate for a mature listed security."""

    code, market = normalize_instrument_id(instrument_id).split(".", maxsplit=1)
    day = pd.Timestamp(trade_date).date()
    if market == "BJ":
        return Decimal("0.30")
    if market == "SH" and code.startswith(("688", "689")):
        return Decimal("0.20")
    if market == "SZ" and code.startswith(("300", "301")) and day >= CHINEXT_REFORM_DATE:
        return Decimal("0.20")
    if is_st and day < MAINBOARD_ST_REFORM_DATE:
        return Decimal("0.05")
    return Decimal("0.10")


def _round_to_fen(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def derive_a_share_price_limits(
    frame: pd.DataFrame,
    *,
    listing_dates: dict[str, object] | None = None,
) -> pd.DataFrame:
    """Derive standard limits while leaving recent-IPO observations explicitly unavailable.

    The 30-calendar-day IPO guard is intentionally wider than the ordinary first-five-trading-day
    no-limit window. It avoids fabricating a limit when this adapter lacks an exact historical IPO
    session calendar. Corporate-action and exceptional-market cases should later be replaced by
    vendor-supplied daily limits.
    """

    required = {"symbol", "trade_date", "preclose", "is_st"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Cannot derive price limits without: {', '.join(missing)}")

    listing_dates = listing_dates or {}
    result = frame.copy()
    upper: list[object] = []
    lower: list[object] = []
    provenance: list[str] = []

    for row in result.loc[:, ["symbol", "trade_date", "preclose", "is_st"]].itertuples(
        index=False
    ):
        instrument_id = normalize_instrument_id(row.symbol)
        trade_day = pd.Timestamp(row.trade_date).date()
        previous_close = pd.to_numeric(pd.Series([row.preclose]), errors="coerce").iloc[0]
        listed_value = listing_dates.get(instrument_id)
        listed_day = pd.Timestamp(listed_value).date() if pd.notna(listed_value) else None
        recent_ipo = (
            listed_day is not None
            and 0 <= (trade_day - listed_day).days < IPO_GUARD_CALENDAR_DAYS
        )
        if pd.isna(previous_close) or float(previous_close) <= 0 or recent_ipo:
            upper.append(pd.NA)
            lower.append(pd.NA)
            provenance.append("unavailable_recent_ipo" if recent_ipo else "unavailable")
            continue

        rate = a_share_limit_rate(
            instrument_id,
            trade_day,
            is_st=str(row.is_st).strip().lower() in {"1", "true", "t", "yes", "y"},
        )
        base = Decimal(str(previous_close))
        upper.append(_round_to_fen(base * (Decimal("1") + rate)))
        lower.append(_round_to_fen(base * (Decimal("1") - rate)))
        provenance.append(PRICE_LIMIT_POLICY_VERSION)

    result["upper_limit"] = upper
    result["lower_limit"] = lower
    result["price_limit_source"] = provenance
    return result
