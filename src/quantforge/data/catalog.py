from __future__ import annotations

from pathlib import Path

import duckdb


def query_daily_bar_summary(snapshot_path: str | Path) -> list[dict[str, object]]:
    parquet_glob = (Path(snapshot_path) / "**" / "*.parquet").as_posix()
    connection = duckdb.connect(database=":memory:")
    try:
        relation = connection.execute(
            """
            SELECT
                source,
                COUNT(*) AS row_count,
                COUNT(DISTINCT instrument_id) AS instrument_count,
                MIN(trade_date) AS first_trade_date,
                MAX(trade_date) AS last_trade_date
            FROM read_parquet(?, hive_partitioning = true)
            GROUP BY source
            ORDER BY source
            """,
            [parquet_glob],
        )
        columns = [item[0] for item in relation.description]
        return [dict(zip(columns, row, strict=True)) for row in relation.fetchall()]
    finally:
        connection.close()
