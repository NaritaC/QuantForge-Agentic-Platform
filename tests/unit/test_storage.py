from pathlib import Path

from quantforge.data.storage import RawStore


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
