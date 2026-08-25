from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

import streamlit as st

from quantforge.ui.data import (
    RunRecord,
    discover_runs,
    load_daily_bar_preview,
    load_indexed_close_series,
    quality_issues_frame,
)


def _project_root() -> Path:
    environment_root = os.environ.get("QUANTFORGE_PROJECT_ROOT")
    if environment_root:
        return Path(environment_root).resolve()
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--project-root", default=".")
    args, _ = parser.parse_known_args()
    return Path(args.project_root).resolve()


COPY: dict[str, dict[str, str]] = {
    "中文": {
        "eyebrow": "QUANTFORGE / 研究审计台",
        "title": "让每一个数字，\n都能回到证据。",
        "subtitle": "A 股量化研究的数据血缘、质量门禁与实验记录。",
        "language": "语言 / Language",
        "run": "选择运行记录",
        "status": "运行状态",
        "quality": "质量门禁",
        "rows": "行情记录",
        "instruments": "证券数量",
        "coverage": "覆盖区间",
        "passed": "通过",
        "failed": "未通过",
        "market": "行情透视",
        "market_note": "最多展示成交额靠前的 8 只证券，首日收盘价标准化为 100。",
        "quality_title": "质量台账",
        "quality_clear": "没有发现需要报告的质量问题。",
        "preview": "数据样本",
        "preview_note": "展示最新 200 行清洗后行情；完整数据仍保存在不可变 Parquet 快照中。",
        "lineage": "数据血缘",
        "raw": "RAW / 原始留存",
        "staging": "STAGING / 语义统一",
        "curated": "CURATED / 研究就绪",
        "references": "参考数据",
        "roadmap": "研究模块",
        "ready": "已接通",
        "coming": "待接通",
        "bars": "日线与质量",
        "universe": "动态股票池",
        "factors": "因子诊断",
        "backtest": "回测归因",
        "no_runs": "还没有可展示的运行记录。请先运行一次数据流水线。",
        "missing_data": "运行记录存在，但对应的本地 Parquet 快照不可用。",
        "source": "数据源",
        "run_id": "运行编号",
        "warning": "警告",
        "error": "错误",
    },
    "English": {
        "eyebrow": "QUANTFORGE / RESEARCH LEDGER",
        "title": "Every number\nreturns to evidence.",
        "subtitle": "A-share research lineage, quality gates, and experiment records.",
        "language": "Language / 语言",
        "run": "Select run",
        "status": "Run status",
        "quality": "Quality gate",
        "rows": "Market rows",
        "instruments": "Instruments",
        "coverage": "Coverage",
        "passed": "Passed",
        "failed": "Failed",
        "market": "Market lens",
        "market_note": "Up to 8 instruments by average turnover; first close is rebased to 100.",
        "quality_title": "Quality ledger",
        "quality_clear": "No reportable quality issues were found.",
        "preview": "Data sample",
        "preview_note": (
            "Latest 200 curated rows; the complete dataset remains in immutable Parquet."
        ),
        "lineage": "Data lineage",
        "raw": "RAW / SOURCE EVIDENCE",
        "staging": "STAGING / NORMALIZED",
        "curated": "CURATED / RESEARCH READY",
        "references": "Reference data",
        "roadmap": "Research modules",
        "ready": "Connected",
        "coming": "Coming next",
        "bars": "Bars & quality",
        "universe": "Dynamic universe",
        "factors": "Factor diagnostics",
        "backtest": "Backtest attribution",
        "no_runs": "No run is available yet. Run the data pipeline first.",
        "missing_data": "The run exists, but its local Parquet snapshot is unavailable.",
        "source": "Source",
        "run_id": "Run ID",
        "warning": "Warning",
        "error": "Error",
    },
}


def _inject_style() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Noto+Serif+SC:wght@500;700;900&display=swap');
        :root {
          --paper: #f2efe6;
          --ink: #171915;
          --muted: #686b60;
          --acid: #d8ff52;
          --rust: #c4482d;
          --line: rgba(23, 25, 21, 0.18);
        }
        .stApp {
          color: var(--ink);
          background:
            linear-gradient(rgba(23,25,21,.035) 1px, transparent 1px),
            linear-gradient(90deg, rgba(23,25,21,.035) 1px, transparent 1px),
            var(--paper);
          background-size: 28px 28px;
        }
        [data-testid="stHeader"] { background: rgba(242,239,230,.82); }
        [data-testid="stSidebar"] {
          background: #1b1d19;
          border-right: 1px solid #34372f;
        }
        [data-testid="stSidebar"] * { color: #f2efe6; }
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
          background: #292c26;
          border-color: #4b4f45;
        }
        .block-container { max-width: 1220px; padding-top: 3.6rem; }
        h1, h2, h3 { font-family: "Noto Serif SC", "Songti SC", serif !important; }
        p, label, [data-testid="stMetricLabel"] {
          font-family: "DM Mono", "Cascadia Code", monospace !important;
        }
        .qf-hero {
          position: relative;
          min-height: 290px;
          padding: 34px 42px;
          overflow: hidden;
          color: #f4f1e8;
          background: #171915;
          border-radius: 3px;
          box-shadow: 14px 14px 0 #d8ff52;
          margin: 0 14px 42px 0;
        }
        .qf-hero::after {
          content: "QF";
          position: absolute;
          right: -24px;
          bottom: -74px;
          font: 900 210px/1 "Noto Serif SC", serif;
          color: rgba(216,255,82,.09);
          letter-spacing: -24px;
        }
        .qf-eyebrow {
          color: #d8ff52;
          font: 500 12px/1.5 "DM Mono", monospace;
          letter-spacing: .16em;
        }
        .qf-hero h1 {
          max-width: 720px;
          margin: 34px 0 18px;
          color: #f4f1e8;
          font-size: clamp(38px, 6vw, 72px);
          line-height: .98;
          letter-spacing: -.045em;
          white-space: pre-line;
        }
        .qf-hero p { color: #aeb1a5; font-size: 13px; }
        .qf-section {
          margin-top: 44px;
          padding-top: 12px;
          border-top: 2px solid var(--ink);
          font: 500 12px/1.5 "DM Mono", monospace;
          letter-spacing: .12em;
          text-transform: uppercase;
        }
        [data-testid="stMetric"] {
          min-height: 116px;
          padding: 16px 18px;
          border: 1px solid var(--line);
          background: rgba(255,255,255,.34);
        }
        [data-testid="stMetricValue"] {
          font-family: "DM Mono", "Cascadia Code", monospace;
          font-size: 25px;
          letter-spacing: -.04em;
        }
        .qf-lineage {
          padding: 18px;
          border: 1px solid var(--line);
          border-top: 5px solid var(--ink);
          background: rgba(255,255,255,.3);
          min-height: 148px;
        }
        .qf-lineage strong {
          font: 500 12px/1.3 "DM Mono", monospace;
          letter-spacing: .08em;
        }
        .qf-lineage code { color: #686b60; font-size: 11px; }
        .qf-module {
          display: flex;
          justify-content: space-between;
          padding: 14px 4px;
          border-bottom: 1px solid var(--line);
          font-family: "DM Mono", monospace;
        }
        .qf-ready { color: #466014; }
        .qf-coming { color: #9b3b27; }
        [data-testid="stDataFrame"] { border: 1px solid var(--line); }
        .stAlert { border-radius: 2px; }
        @media (max-width: 700px) {
          .qf-hero { padding: 28px 24px; min-height: 250px; }
          .qf-hero h1 { font-size: 42px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _summary(manifest: dict[str, Any]) -> dict[str, Any]:
    rows = manifest.get("duckdb_summary", [])
    summary = rows[0] if rows else {}
    return {
        "row_count": summary.get("row_count", manifest.get("curated", {}).get("row_count", 0)),
        "instrument_count": summary.get("instrument_count", 0),
        "first_trade_date": summary.get("first_trade_date", "—"),
        "last_trade_date": summary.get("last_trade_date", "—"),
    }


def _render_lineage(manifest: dict[str, Any], copy: dict[str, str]) -> None:
    columns = st.columns(3)
    stages = [
        (copy["raw"], manifest.get("raw", {})),
        (copy["staging"], manifest.get("staging", {})),
        (copy["curated"], manifest.get("curated", {})),
    ]
    for column, (title, stage) in zip(columns, stages, strict=True):
        checksum = str(stage.get("checksum", "unavailable"))
        detail = stage.get("snapshot_id") or Path(str(stage.get("data_path", "—"))).name
        column.markdown(
            f'<div class="qf-lineage"><strong>{title}</strong><br><br>'
            f"<code>{str(detail)[:32]}</code><br><code>sha · {checksum[:16]}</code></div>",
            unsafe_allow_html=True,
        )


def _render_references(manifest: dict[str, Any]) -> None:
    references = manifest.get("reference_data", {})
    if not references:
        st.caption("—")
        return
    columns = st.columns(len(references))
    for column, (name, payload) in zip(columns, references.items(), strict=True):
        quality = payload.get("quality", {})
        column.metric(
            name.replace("_", " ").upper(),
            f"{quality.get('row_count', 0):,}",
            "PASS" if quality.get("passed") else "FAIL",
        )


def render_dashboard(project_root: Path, records: list[RunRecord]) -> None:
    language = st.sidebar.selectbox(COPY["中文"]["language"], list(COPY))
    copy = COPY[language]
    st.sidebar.markdown("---")
    st.sidebar.caption(str(project_root))
    if not records:
        st.markdown(
            f'<section class="qf-hero"><div class="qf-eyebrow">{copy["eyebrow"]}</div>'
            f"<h1>{copy['title']}</h1><p>{copy['subtitle']}</p></section>",
            unsafe_allow_html=True,
        )
        st.warning(copy["no_runs"])
        return

    labels = {record.run_id: record.label for record in records}
    selected_id = st.sidebar.selectbox(
        copy["run"],
        [record.run_id for record in records],
        format_func=lambda run_id: labels[run_id],
    )
    record = next(item for item in records if item.run_id == selected_id)
    manifest = record.manifest
    summary = _summary(manifest)
    quality_passed = bool(manifest.get("quality", {}).get("passed"))

    st.markdown(
        f'<section class="qf-hero"><div class="qf-eyebrow">{copy["eyebrow"]}</div>'
        f"<h1>{copy['title']}</h1><p>{copy['subtitle']}</p></section>",
        unsafe_allow_html=True,
    )

    metrics = st.columns(5)
    metrics[0].metric(copy["status"], str(manifest.get("status", "—")).upper())
    metrics[1].metric(copy["quality"], copy["passed"] if quality_passed else copy["failed"])
    metrics[2].metric(copy["rows"], f"{summary['row_count']:,}")
    metrics[3].metric(copy["instruments"], f"{summary['instrument_count']:,}")
    metrics[4].metric(
        copy["coverage"],
        f"{str(summary['first_trade_date'])[5:]} → {str(summary['last_trade_date'])[5:]}",
    )
    st.caption(
        f"{copy['run_id']}: {record.run_id}  ·  "
        f"{copy['source']}: {manifest.get('config', {}).get('source', '—')}"
    )

    st.markdown(f'<div class="qf-section">01 / {copy["market"]}</div>', unsafe_allow_html=True)
    st.caption(copy["market_note"])
    try:
        prices = load_indexed_close_series(manifest)
        if not prices.empty:
            chart = prices.pivot(
                index="trade_date", columns="instrument_id", values="indexed_close"
            )
            palette = [
                "#171915",
                "#c4482d",
                "#718b27",
                "#176b87",
                "#8b6238",
                "#6b4d87",
                "#b17b12",
                "#405968",
            ]
            st.line_chart(chart, color=palette[: len(chart.columns)])
    except FileNotFoundError:
        st.warning(copy["missing_data"])

    st.markdown(
        f'<div class="qf-section">02 / {copy["quality_title"]}</div>',
        unsafe_allow_html=True,
    )
    issues = quality_issues_frame(manifest)
    if issues.empty:
        st.success(copy["quality_clear"])
    else:
        errors = int((issues["severity"] == "error").sum())
        warnings = int((issues["severity"] == "warning").sum())
        issue_metrics = st.columns(2)
        issue_metrics[0].metric(copy["error"], errors)
        issue_metrics[1].metric(copy["warning"], warnings)
        st.dataframe(issues, width="stretch", hide_index=True)

    st.markdown(f'<div class="qf-section">03 / {copy["lineage"]}</div>', unsafe_allow_html=True)
    _render_lineage(manifest, copy)

    st.markdown(
        f'<div class="qf-section">04 / {copy["references"]}</div>',
        unsafe_allow_html=True,
    )
    _render_references(manifest)

    st.markdown(f'<div class="qf-section">05 / {copy["preview"]}</div>', unsafe_allow_html=True)
    st.caption(copy["preview_note"])
    try:
        preview = load_daily_bar_preview(manifest)
        st.dataframe(
            preview,
            width="stretch",
            hide_index=True,
            column_config={
                "trade_date": st.column_config.DateColumn("trade_date", format="YYYY-MM-DD"),
                "amount": st.column_config.NumberColumn("amount", format="%.0f"),
            },
        )
    except FileNotFoundError:
        st.warning(copy["missing_data"])

    st.markdown(f'<div class="qf-section">06 / {copy["roadmap"]}</div>', unsafe_allow_html=True)
    modules = [
        (copy["bars"], copy["ready"], "qf-ready"),
        (copy["universe"], copy["coming"], "qf-coming"),
        (copy["factors"], copy["coming"], "qf-coming"),
        (copy["backtest"], copy["coming"], "qf-coming"),
    ]
    for name, status, class_name in modules:
        st.markdown(
            f'<div class="qf-module"><span>{name}</span>'
            f'<span class="{class_name}">{status}</span></div>',
            unsafe_allow_html=True,
        )


st.set_page_config(
    page_title="QuantForge · Research Ledger",
    page_icon="◩",
    layout="wide",
    initial_sidebar_state="expanded",
)
_inject_style()
ROOT = _project_root()
render_dashboard(ROOT, discover_runs(ROOT))
