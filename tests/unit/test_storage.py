from pathlib import Path

import pandas as pd

from quantforge.data.storage import ParquetSnapshotStore, RawStore


def test_raw_store_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    source.write_bytes(b"symbol,close\n600000,10.00\n")
    store = RawStore(tmp_path / "raw")

    first = store.persist_file(
        source,
        dataset="daily_bars",
        source="fixture",
        adapter_version="1.0.0",
        request={"kind": "test"},
    )
    second = store.persist_file(
        source,
        dataset="daily_bars",
        source="fixture",
        adapter_version="1.0.0",
        request={"kind": "test"},
    )

    assert first.checksum == second.checksum
    assert first.data_path == second.data_path
    assert first.ingested_at == second.ingested_at
    assert first.data_path.read_bytes() == source.read_bytes()


def test_raw_store_persists_network_payload_without_a_temporary_source_file(
    tmp_path: Path,
) -> None:
    store = RawStore(tmp_path / "raw")
    payload = b"date,code,close\n2024-01-02,sh.600000,6.60\n"

    artifact = store.persist_bytes(
        payload,
        dataset="daily_bars",
        source="baostock",
        adapter_version="1.0.0",
        request={"adjustflag": "3"},
        suffix=".csv",
        source_filename="baostock_daily_bars.csv",
    )

    assert artifact.data_path.read_bytes() == payload
    assert artifact.data_path.suffix == ".csv"


def test_parquet_snapshot_supports_reference_data_without_trade_date(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        {
            "instrument_id": ["600000.SH"],
            "list_date": [pd.Timestamp("1999-11-10").date()],
        }
    )

    snapshot = ParquetSnapshotStore(tmp_path / "curated", layer="curated").write(
        frame, dataset="security_master"
    )

    files = list(snapshot.path.glob("*.parquet"))
    assert len(files) == 1
    assert pd.read_parquet(files[0])["instrument_id"].tolist() == ["600000.SH"]
