from datetime import date

import pandas as pd

from quantforge.research.universe import build_dynamic_universe


def test_dynamic_universe_uses_as_of_lifecycle_st_and_liquidity() -> None:
    days = pd.date_range("2024-01-02", periods=5, freq="B").date
    calendar = pd.DataFrame({"trade_date": days, "is_trading_day": True})
    master = pd.DataFrame(
        {
            "instrument_id": ["A.SH", "B.SH", "C.SH", "D.SH", "E.SH"],
            "list_date": [days[0], days[0], days[3], days[0], days[0]],
            "delist_date": [pd.NaT, pd.NaT, pd.NaT, pd.NaT, days[4]],
        }
    )
    rows: list[dict[str, object]] = []
    amounts = {"A.SH": 100.0, "B.SH": 250.0, "C.SH": 500.0, "D.SH": 300.0, "E.SH": 400.0}
    for trade_date in days:
        for instrument_id, amount in amounts.items():
            rows.append(
                {
                    "instrument_id": instrument_id,
                    "trade_date": trade_date,
                    "amount": 0.0 if instrument_id == "D.SH" and trade_date == days[4] else amount,
                    "is_st": instrument_id == "B.SH" and trade_date == days[4],
                    "trade_status": (
                        "SUSPENDED"
                        if instrument_id == "D.SH" and trade_date == days[4]
                        else "TRADE"
                    ),
                }
            )
    bars = pd.DataFrame(rows)

    result = build_dynamic_universe(
        bars,
        master,
        calendar,
        [days[4]],
        top_n=2,
        min_listing_days=3,
        liquidity_window=3,
        min_liquidity_observations=3,
    )

    assert result["instrument_id"].tolist() == ["D.SH", "A.SH"]
    assert result["liquidity_rank"].tolist() == [1, 2]
    assert result.loc[0, "trade_status"] == "SUSPENDED"


def test_dynamic_universe_rejects_non_trading_rebalance_date() -> None:
    calendar = pd.DataFrame({"trade_date": [date(2024, 1, 2)], "is_trading_day": [True]})
    master = pd.DataFrame(
        {"instrument_id": ["A.SH"], "list_date": [date(2020, 1, 1)], "delist_date": [pd.NaT]}
    )
    bars = pd.DataFrame(
        {
            "instrument_id": ["A.SH"],
            "trade_date": [date(2024, 1, 2)],
            "amount": [1.0],
            "is_st": [False],
            "trade_status": ["TRADE"],
        }
    )

    try:
        build_dynamic_universe(
            bars,
            master,
            calendar,
            [date(2024, 1, 3)],
            top_n=1,
            min_listing_days=1,
            liquidity_window=1,
            min_liquidity_observations=1,
        )
    except ValueError as error:
        assert "not a trading day" in str(error)
    else:
        raise AssertionError("Expected a non-trading rebalance date to be rejected")


def test_dynamic_universe_handles_all_missing_delist_dates_after_parquet_roundtrip(
    tmp_path,
) -> None:
    trade_date = pd.Timestamp("2024-01-02")
    calendar = pd.DataFrame({"trade_date": [trade_date], "is_trading_day": [True]})
    master = pd.DataFrame(
        {
            "instrument_id": ["A.SH"],
            "list_date": [pd.Timestamp("2020-01-01")],
            "delist_date": pd.Series([pd.NaT], dtype="datetime64[ns]"),
        }
    )
    path = tmp_path / "master.parquet"
    master.to_parquet(path, index=False)
    roundtripped_master = pd.read_parquet(path)
    bars = pd.DataFrame(
        {
            "instrument_id": ["A.SH"],
            "trade_date": [trade_date],
            "amount": [100.0],
            "is_st": [False],
            "trade_status": ["TRADE"],
        }
    )

    result = build_dynamic_universe(
        bars,
        roundtripped_master,
        calendar,
        [trade_date],
        top_n=1,
        min_listing_days=1,
        liquidity_window=1,
        min_liquidity_observations=1,
    )

    assert result["instrument_id"].tolist() == ["A.SH"]
