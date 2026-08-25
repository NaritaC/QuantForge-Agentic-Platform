from __future__ import annotations

from typing import Any


def daily_bar_field_lineage(source: str) -> list[dict[str, str]]:
    """Describe field-level transformations from vendor payload to canonical bars."""

    raw_fields = {
        "instrument_id": "code" if source == "baostock" else "symbol",
        "trade_date": "date" if source == "baostock" else "trade_date",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "preclose": "preclose",
        "volume": "volume",
        "amount": "amount",
        "trade_status": "tradestatus",
        "is_st": "isST" if source == "baostock" else "is_st",
        "upper_limit": "not supplied" if source == "baostock" else "upper_limit",
        "lower_limit": "not supplied" if source == "baostock" else "lower_limit",
        "source": "adapter identity",
        "ingested_at": "Raw persistence timestamp",
    }
    rules = {
        "instrument_id": (
            "交易所前缀转为后缀，代码补足六位并转大写",
            "Move exchange prefix to suffix, zero-pad code, and uppercase.",
        ),
        "trade_date": ("解析为无时区交易日期", "Parse as a timezone-free trading date."),
        "open": ("转为 float64；非法值转为空", "Cast to float64; invalid values become null."),
        "high": ("转为 float64；非法值转为空", "Cast to float64; invalid values become null."),
        "low": ("转为 float64；非法值转为空", "Cast to float64; invalid values become null."),
        "close": ("转为 float64；非法值转为空", "Cast to float64; invalid values become null."),
        "preclose": ("转为 float64；非法值转为空", "Cast to float64; invalid values become null."),
        "volume": ("转为 float64；保留供应商单位", "Cast to float64; preserve vendor units."),
        "amount": ("转为 float64；保留供应商单位", "Cast to float64; preserve vendor units."),
        "trade_status": (
            "1/true/trade → TRADE；0/false/suspended → SUSPENDED",
            "Map vendor states to TRADE or SUSPENDED.",
        ),
        "is_st": ("1/true/yes → true，其余为 false", "Map truthy vendor values to boolean."),
        "upper_limit": (
            "BaoStock 不提供，显式保留为空并触发质量警告",
            "BaoStock omits it; retain null and emit a quality warning.",
        ),
        "lower_limit": (
            "BaoStock 不提供，显式保留为空并触发质量警告",
            "BaoStock omits it; retain null and emit a quality warning.",
        ),
        "source": ("写入适配器名称常量", "Stamp the adapter source name."),
        "ingested_at": ("写入 Raw 首次落盘的 UTC 时间", "Stamp first Raw persistence time in UTC."),
    }
    return [
        {
            "source_field": raw_fields[canonical],
            "canonical_field": canonical,
            "rule_zh": rules[canonical][0],
            "rule_en": rules[canonical][1],
            "implementation": "quantforge.data.normalize:normalize_daily_bars",
        }
        for canonical in raw_fields
    ]


def build_daily_bar_lineage(
    *,
    source: str,
    adapter_version: str,
    request: dict[str, Any],
    raw_rows: int,
    raw_checksum: str,
    staging_rows: int,
    staging_checksum: str,
    curated_rows: int,
    curated_checksum: str,
    quality: dict[str, Any],
) -> dict[str, Any]:
    """Build a portable, UI-ready evidence graph for one daily-bar run."""

    field_lineage = daily_bar_field_lineage(source)
    steps = [
        {
            "order": 1,
            "step": "acquire",
            "name_zh": "供应商采集",
            "name_en": "Vendor acquisition",
            "rule_zh": "按已记录请求获取数据；不在适配器中填补市场事实。",
            "rule_en": "Fetch the recorded request; do not repair market facts in the adapter.",
            "implementation": f"quantforge.data.adapters.{source}",
            "input_rows": None,
            "output_rows": raw_rows,
            "status": "passed",
        },
        {
            "order": 2,
            "step": "raw_persist",
            "name_zh": "Raw 原样留存",
            "name_en": "Raw byte preservation",
            "rule_zh": "原始字节按 SHA-256 寻址，仅追加、不覆盖。",
            "rule_en": "Content-address exact bytes by SHA-256; append only.",
            "implementation": "quantforge.data.storage:RawStore",
            "input_rows": raw_rows,
            "output_rows": raw_rows,
            "status": "passed",
            "output_checksum": raw_checksum,
        },
        {
            "order": 3,
            "step": "normalize",
            "name_zh": "字段与语义统一",
            "name_en": "Schema and semantic normalization",
            "rule_zh": f"执行 {len(field_lineage)} 条字段映射；非法类型转为空，交给质量门禁处理。",
            "rule_en": (
                f"Apply {len(field_lineage)} field mappings; coerce invalid types to null for "
                "the quality gate."
            ),
            "implementation": "quantforge.data.normalize:normalize_daily_bars",
            "input_rows": raw_rows,
            "output_rows": staging_rows,
            "status": "passed",
            "output_checksum": staging_checksum,
        },
        {
            "order": 4,
            "step": "quality_gate",
            "name_zh": "确定性质量门禁",
            "name_en": "Deterministic quality gate",
            "rule_zh": "逐项执行结构、主键、价格、成交、状态与涨跌停约束。",
            "rule_en": "Execute schema, key, price, activity, status, and limit checks.",
            "implementation": "quantforge.data.quality:validate_daily_bars",
            "input_rows": staging_rows,
            "output_rows": staging_rows,
            "status": "passed" if quality.get("passed") else "failed",
            "check_count": len(quality.get("checks", [])),
        },
        {
            "order": 5,
            "step": "curate",
            "name_zh": "研究快照生成",
            "name_en": "Research snapshot materialization",
            "rule_zh": "按交易日和证券稳定排序，以年份分区写入不可变 Parquet。",
            "rule_en": "Stable-sort by date/instrument and write immutable yearly Parquet.",
            "implementation": "quantforge.data.storage:ParquetSnapshotStore",
            "input_rows": staging_rows,
            "output_rows": curated_rows,
            "status": "passed",
            "output_checksum": curated_checksum,
        },
        {
            "order": 6,
            "step": "research_query",
            "name_zh": "DuckDB 研究查询",
            "name_en": "DuckDB research query",
            "rule_zh": "直接查询 Curated Parquet，生成覆盖范围与证券数量摘要。",
            "rule_en": "Query Curated Parquet directly for coverage and instrument summary.",
            "implementation": "quantforge.data.catalog:query_daily_bar_summary",
            "input_rows": curated_rows,
            "output_rows": curated_rows,
            "status": "passed",
        },
    ]
    counts = [
        ("vendor_frame", raw_rows),
        ("raw", raw_rows),
        ("staging", staging_rows),
        ("curated", curated_rows),
    ]
    return {
        "schema_version": "1.0",
        "adapter": {"name": source, "version": adapter_version},
        "source_request": request,
        "processing_steps": steps,
        "field_lineage": field_lineage,
        "row_reconciliation": [
            {
                "stage": stage,
                "row_count": count,
                "delta_from_previous": None if index == 0 else count - counts[index - 1][1],
            }
            for index, (stage, count) in enumerate(counts)
        ],
        "quality_checks": quality.get("checks", []),
    }
