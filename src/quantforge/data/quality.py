from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

import pandas as pd

from quantforge.data.contracts import (
    DAILY_BAR_COLUMNS,
    DAILY_BAR_PRIMARY_KEY,
    TRADE_STATUSES,
)

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class QualityIssue:
    check: str
    severity: Severity
    count: int
    message: str
    sample: list[dict[str, Any]]


@dataclass(frozen=True)
class QualityReport:
    dataset: str
    row_count: int
    issues: tuple[QualityIssue, ...]

    @property
    def passed(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "row_count": self.row_count,
            "passed": self.passed,
            "issues": [asdict(issue) for issue in self.issues],
        }

    def raise_if_failed(self) -> None:
        if not self.passed:
            checks = ", ".join(issue.check for issue in self.issues if issue.severity == "error")
            raise DataQualityError(f"Data quality gate failed: {checks}", self)


class DataQualityError(ValueError):
    def __init__(self, message: str, report: QualityReport) -> None:
        super().__init__(message)
        self.report = report


def _records(frame: pd.DataFrame, mask: pd.Series, columns: list[str]) -> list[dict[str, Any]]:
    sample = frame.loc[mask, columns].head(5).copy()
    return sample.astype("string").to_dict(orient="records")


def validate_daily_bars(frame: pd.DataFrame) -> QualityReport:
    issues: list[QualityIssue] = []
    missing_columns = [column for column in DAILY_BAR_COLUMNS if column not in frame.columns]
    if missing_columns:
        issues.append(
            QualityIssue(
                check="required_columns",
                severity="error",
                count=len(missing_columns),
                message=f"Missing required columns: {', '.join(missing_columns)}",
                sample=[],
            )
        )
        return QualityReport("daily_bars", len(frame), tuple(issues))

    null_key = frame[list(DAILY_BAR_PRIMARY_KEY)].isna().any(axis=1)
    if null_key.any():
        issues.append(
            QualityIssue(
                "null_primary_key",
                "error",
                int(null_key.sum()),
                "Primary-key fields must be present.",
                _records(frame, null_key, list(DAILY_BAR_PRIMARY_KEY)),
            )
        )

    duplicate = frame.duplicated(list(DAILY_BAR_PRIMARY_KEY), keep=False)
    if duplicate.any():
        issues.append(
            QualityIssue(
                "duplicate_primary_key",
                "error",
                int(duplicate.sum()),
                "Duplicate instrument/date records are quarantined, never silently deduplicated.",
                _records(frame, duplicate, list(DAILY_BAR_PRIMARY_KEY)),
            )
        )

    price_columns = ["open", "high", "low", "close", "preclose"]
    missing_price = frame[price_columns].isna().any(axis=1)
    if missing_price.any():
        issues.append(
            QualityIssue(
                "missing_price",
                "error",
                int(missing_price.sum()),
                "OHLC and previous close are required, including explicit suspension rows.",
                _records(frame, missing_price, [*DAILY_BAR_PRIMARY_KEY, *price_columns]),
            )
        )

    nonpositive_price = frame[price_columns].le(0).any(axis=1)
    if nonpositive_price.any():
        issues.append(
            QualityIssue(
                "nonpositive_price",
                "error",
                int(nonpositive_price.sum()),
                "Prices must be strictly positive.",
                _records(frame, nonpositive_price, [*DAILY_BAR_PRIMARY_KEY, *price_columns]),
            )
        )

    invalid_ohlc = frame["high"].lt(frame[["open", "close", "low"]].max(axis=1)) | frame["low"].gt(
        frame[["open", "close", "high"]].min(axis=1)
    )
    if invalid_ohlc.any():
        issues.append(
            QualityIssue(
                "invalid_ohlc",
                "error",
                int(invalid_ohlc.sum()),
                "High/low must bound open and close.",
                _records(
                    frame, invalid_ohlc, [*DAILY_BAR_PRIMARY_KEY, "open", "high", "low", "close"]
                ),
            )
        )

    negative_activity = frame[["volume", "amount"]].lt(0).any(axis=1)
    if negative_activity.any():
        issues.append(
            QualityIssue(
                "negative_volume_or_amount",
                "error",
                int(negative_activity.sum()),
                "Volume and amount cannot be negative.",
                _records(frame, negative_activity, [*DAILY_BAR_PRIMARY_KEY, "volume", "amount"]),
            )
        )

    invalid_status = ~frame["trade_status"].isin(TRADE_STATUSES)
    if invalid_status.any():
        issues.append(
            QualityIssue(
                "invalid_trade_status",
                "error",
                int(invalid_status.sum()),
                "Trade status must map to the canonical enumeration.",
                _records(frame, invalid_status, [*DAILY_BAR_PRIMARY_KEY, "trade_status"]),
            )
        )

    suspended_activity = frame["trade_status"].eq("SUSPENDED") & (
        frame["volume"].ne(0) | frame["amount"].ne(0)
    )
    if suspended_activity.any():
        issues.append(
            QualityIssue(
                "suspended_with_activity",
                "warning",
                int(suspended_activity.sum()),
                "Suspended rows normally have zero volume and amount; verify vendor semantics.",
                _records(frame, suspended_activity, [*DAILY_BAR_PRIMARY_KEY, "volume", "amount"]),
            )
        )

    limit_order = frame["upper_limit"].lt(frame["lower_limit"])
    if limit_order.any():
        issues.append(
            QualityIssue(
                "invalid_price_limits",
                "error",
                int(limit_order.sum()),
                "Upper price limit cannot be below lower price limit.",
                _records(
                    frame, limit_order, [*DAILY_BAR_PRIMARY_KEY, "upper_limit", "lower_limit"]
                ),
            )
        )

    return QualityReport("daily_bars", len(frame), tuple(issues))
