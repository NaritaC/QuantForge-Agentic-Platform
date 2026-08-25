from __future__ import annotations

from datetime import datetime

import pandas as pd

from quantforge.data.contracts import SECURITY_MASTER_COLUMNS, TRADE_CALENDAR_COLUMNS
from quantforge.data.normalize import normalize_instrument_id
from quantforge.data.quality import QualityIssue, QualityReport


def normalize_trade_calendar(
    vendor_frame: pd.DataFrame,
    *,
    source: str,
    ingested_at: datetime,
) -> pd.DataFrame:
    required = {"calendar_date", "is_trading_day"}
    missing = sorted(required - set(vendor_frame.columns))
    if missing:
        raise ValueError(f"Vendor trade calendar missing columns: {', '.join(missing)}")
    frame = vendor_frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["calendar_date"], errors="coerce").dt.date
    frame["is_trading_day"] = (
        frame["is_trading_day"].astype("string").str.strip().map({"1": True, "0": False})
    ).astype("boolean")
    frame["source"] = source
    frame["ingested_at"] = pd.Timestamp(ingested_at).tz_convert("UTC")
    return frame.loc[:, TRADE_CALENDAR_COLUMNS].copy()


def normalize_security_master(
    vendor_frame: pd.DataFrame,
    *,
    source: str,
    ingested_at: datetime,
) -> pd.DataFrame:
    required = {"code", "code_name", "ipoDate", "outDate", "type", "status"}
    missing = sorted(required - set(vendor_frame.columns))
    if missing:
        raise ValueError(f"Vendor security master missing columns: {', '.join(missing)}")
    frame = vendor_frame.copy()
    frame["instrument_id"] = frame["code"].map(normalize_instrument_id).astype("string")
    frame["display_name"] = frame["code_name"].astype("string").str.strip()
    frame["list_date"] = pd.to_datetime(frame["ipoDate"], errors="coerce").dt.date
    frame["delist_date"] = pd.to_datetime(
        frame["outDate"].replace("", pd.NA), errors="coerce"
    ).dt.date
    frame["instrument_type_code"] = frame["type"].astype("string").str.strip()
    frame["current_status"] = frame["status"].astype("string").str.strip()
    frame["source"] = source
    frame["ingested_at"] = pd.Timestamp(ingested_at).tz_convert("UTC")
    return frame.loc[:, SECURITY_MASTER_COLUMNS].copy()


def validate_trade_calendar(frame: pd.DataFrame) -> QualityReport:
    issues: list[QualityIssue] = []
    missing = [column for column in TRADE_CALENDAR_COLUMNS if column not in frame]
    if missing:
        issues.append(
            QualityIssue(
                "required_columns",
                "error",
                len(missing),
                f"Missing trade-calendar columns: {', '.join(missing)}",
                [],
            )
        )
        return QualityReport("trade_calendar", len(frame), tuple(issues))
    duplicate = frame["trade_date"].duplicated(keep=False)
    if duplicate.any():
        issues.append(
            QualityIssue(
                "duplicate_trade_date",
                "error",
                int(duplicate.sum()),
                "A source calendar must contain one row per calendar date.",
                frame.loc[duplicate, ["trade_date"]]
                .astype("string")
                .head(5)
                .to_dict(orient="records"),
            )
        )
    invalid = frame[["trade_date", "is_trading_day"]].isna().any(axis=1)
    if invalid.any():
        issues.append(
            QualityIssue(
                "invalid_calendar_value",
                "error",
                int(invalid.sum()),
                "Calendar date and trading-day flag must be valid.",
                frame.loc[invalid, ["trade_date", "is_trading_day"]]
                .astype("string")
                .head(5)
                .to_dict(orient="records"),
            )
        )
    return QualityReport("trade_calendar", len(frame), tuple(issues))


def validate_security_master(frame: pd.DataFrame) -> QualityReport:
    issues: list[QualityIssue] = []
    missing = [column for column in SECURITY_MASTER_COLUMNS if column not in frame]
    if missing:
        issues.append(
            QualityIssue(
                "required_columns",
                "error",
                len(missing),
                f"Missing security-master columns: {', '.join(missing)}",
                [],
            )
        )
        return QualityReport("security_master", len(frame), tuple(issues))
    duplicate = frame["instrument_id"].duplicated(keep=False)
    if duplicate.any():
        issues.append(
            QualityIssue(
                "duplicate_instrument",
                "error",
                int(duplicate.sum()),
                "A security-master snapshot must have one row per instrument.",
                frame.loc[duplicate, ["instrument_id"]]
                .astype("string")
                .head(5)
                .to_dict(orient="records"),
            )
        )
    invalid_list_date = frame["list_date"].isna()
    if invalid_list_date.any():
        issues.append(
            QualityIssue(
                "missing_list_date",
                "error",
                int(invalid_list_date.sum()),
                "Listing date is required for point-in-time universe eligibility.",
                frame.loc[invalid_list_date, ["instrument_id", "list_date"]]
                .astype("string")
                .head(5)
                .to_dict(orient="records"),
            )
        )
    invalid_lifecycle = frame["delist_date"].notna() & (frame["delist_date"] < frame["list_date"])
    if invalid_lifecycle.any():
        issues.append(
            QualityIssue(
                "invalid_listing_lifecycle",
                "error",
                int(invalid_lifecycle.sum()),
                "Delisting date cannot precede listing date.",
                frame.loc[invalid_lifecycle, ["instrument_id", "list_date", "delist_date"]]
                .astype("string")
                .head(5)
                .to_dict(orient="records"),
            )
        )
    return QualityReport("security_master", len(frame), tuple(issues))
