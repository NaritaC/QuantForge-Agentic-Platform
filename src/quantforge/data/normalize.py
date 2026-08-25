from __future__ import annotations

from datetime import datetime

import pandas as pd

from quantforge.data.contracts import DAILY_BAR_COLUMNS

VENDOR_REQUIRED_COLUMNS = {
    "symbol",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "preclose",
    "volume",
    "amount",
    "tradestatus",
    "is_st",
    "upper_limit",
    "lower_limit",
}


def normalize_instrument_id(value: object) -> str:
    raw = str(value).strip().upper()
    if raw.startswith(("SH.", "SZ.", "BJ.")):
        market, code = raw.split(".", maxsplit=1)
        return f"{code}.{market}"
    if "." in raw:
        code, market = raw.split(".", maxsplit=1)
        return f"{code.zfill(6)}.{market}"
    code = raw.zfill(6)
    market = "SH" if code.startswith(("5", "6", "9")) else "SZ"
    return f"{code}.{market}"


def _parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def normalize_daily_bars(
    vendor_frame: pd.DataFrame,
    *,
    source: str,
    ingested_at: datetime,
) -> pd.DataFrame:
    missing = sorted(VENDOR_REQUIRED_COLUMNS - set(vendor_frame.columns))
    if missing:
        raise ValueError(f"Vendor daily bars missing columns: {', '.join(missing)}")

    frame = vendor_frame.copy()
    frame["instrument_id"] = frame["symbol"].map(normalize_instrument_id).astype("string")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.date

    numeric_columns = [
        "open",
        "high",
        "low",
        "close",
        "preclose",
        "volume",
        "amount",
        "upper_limit",
        "lower_limit",
    ]
    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype("float64")

    if "price_limit_source" not in frame:
        supplied = frame[["upper_limit", "lower_limit"]].notna().all(axis=1)
        frame["price_limit_source"] = supplied.map(
            {True: "vendor", False: "unavailable"}
        )
    frame["price_limit_source"] = frame["price_limit_source"].astype("string")

    status = frame["tradestatus"].astype("string").str.strip().str.lower()
    frame["trade_status"] = status.map(
        {
            "1": "TRADE",
            "true": "TRADE",
            "trade": "TRADE",
            "0": "SUSPENDED",
            "false": "SUSPENDED",
            "suspended": "SUSPENDED",
        }
    ).astype("string")
    frame["is_st"] = frame["is_st"].map(_parse_bool).astype("bool")
    frame["source"] = source
    frame["ingested_at"] = pd.Timestamp(ingested_at).tz_convert("UTC")

    return frame.loc[:, DAILY_BAR_COLUMNS].copy()
