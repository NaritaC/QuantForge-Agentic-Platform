from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from quantforge.data.adapters import FixtureDailyBarAdapter
from quantforge.data.normalize import normalize_daily_bars
from quantforge.data.quality import DataQualityError, validate_daily_bars

FIXTURE = Path(__file__).parents[1] / "fixtures" / "daily_bars.csv"


def _valid_frame() -> pd.DataFrame:
    batch = FixtureDailyBarAdapter(FIXTURE).fetch_daily_bars()
    return normalize_daily_bars(
        batch.frame,
        source=batch.source,
        ingested_at=datetime(2024, 1, 9, tzinfo=UTC),
    )


def test_valid_fixture_passes_quality_gate() -> None:
    report = validate_daily_bars(_valid_frame())

    assert report.passed
    assert report.row_count == 15
    assert report.issues == ()


def test_duplicate_primary_key_fails_instead_of_silent_deduplication() -> None:
    frame = _valid_frame()
    duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)

    report = validate_daily_bars(duplicated)

    assert not report.passed
    assert "duplicate_primary_key" in {issue.check for issue in report.issues}
    try:
        report.raise_if_failed()
    except DataQualityError as error:
        assert error.report is report
    else:
        raise AssertionError("Expected the quality gate to fail")


def test_invalid_ohlc_fails_quality_gate() -> None:
    frame = _valid_frame()
    frame.loc[0, "high"] = frame.loc[0, "low"] - 0.01

    report = validate_daily_bars(frame)

    assert "invalid_ohlc" in {issue.check for issue in report.issues}
