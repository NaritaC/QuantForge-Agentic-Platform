from __future__ import annotations

import argparse
import html
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from quantforge.ui.data import (
    RunRecord,
    discover_runs,
    field_lineage_frame,
    flatten_mapping,
    load_daily_bar_preview,
    load_indexed_close_series,
    load_raw_preview,
    load_research_artifact,
    processing_steps_frame,
    quality_checks_frame,
    quality_issues_frame,
    research_artifacts_frame,
    row_reconciliation_frame,
    trace_inventory,
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
        "product": "QUANTFORGE / EVIDENCE CONSOLE",
        "title": "量化研究证据台",
        "subtitle": "从供应商请求到研究快照，每一步都有记录、规则与校验。",
        "language": "语言 / Language",
        "run": "运行记录",
        "overview": "闭环总览",
        "processing": "处理链路",
        "quality": "质量门禁",
        "data": "数据对照",
        "research": "研究闭环",
        "status": "运行状态",
        "gate": "质量结果",
        "rows": "Curated 行数",
        "instruments": "证券数量",
        "coverage": "行情区间",
        "passed": "通过",
        "failed": "失败",
        "trace": "证据完整度",
        "trace_note": "衡量复现所需证据是否齐全，不代表数据本身一定正确。",
        "legacy": "这条旧运行生成于详细血缘功能之前。请重新运行流水线以获得字段级追踪。",
        "flow": "本次数据流",
        "market": "行情覆盖",
        "market_note": "成交额靠前的证券，首个可用收盘价标准化为 100，仅用于覆盖检查。",
        "references": "参考数据",
        "source_request": "供应商请求",
        "run_config": "运行配置",
        "reproduce": "精确复现",
        "download_manifest": "下载完整运行证据",
        "row_reconciliation": "行数对账",
        "row_note": "任何非零变化都必须由显式过滤、隔离或聚合规则解释。",
        "steps": "处理步骤",
        "fields": "字段级血缘",
        "fields_note": "逐字段说明供应商字段如何变成平台标准字段，以及实现代码位于何处。",
        "all_checks": "全部质量检查",
        "checks_note": "通过项与异常项一并保留，避免“没有报错”等同于“没有检查”。",
        "issues": "异常证据与样本",
        "no_issues": "本次运行没有错误或警告。",
        "raw": "Raw 原始证据",
        "curated": "Curated 研究数据",
        "schema": "字段与类型对照",
        "preview_note": "仅加载最多 200 行供人工检查；完整快照不会被前端整体读入内存。",
        "closed_loop": "闭环状态",
        "closed_note": (
            "完整研究闭环必须依次产出股票池、因子、回测和报告；当前未完成的模块不会伪装成可用。"
        ),
        "available": "已产出",
        "implemented": "已实现，待接线",
        "missing": "未实现",
        "baseline_deferred": "基线比较按本轮范围暂缓：买入持有、网格交易、定投均未参与评价。",
        "research_outputs": "研究产物",
        "execution_evidence": "成交与组合证据",
        "no_runs": "没有可展示的运行。请先执行数据流水线。",
        "missing_local": "运行清单存在，但对应的本地数据文件已不存在。",
        "source": "数据源",
        "commit": "代码版本",
    },
    "English": {
        "product": "QUANTFORGE / EVIDENCE CONSOLE",
        "title": "Quant Research Evidence Console",
        "subtitle": "Every step from vendor request to research snapshot is recorded and tested.",
        "language": "Language / 语言",
        "run": "Run record",
        "overview": "Loop overview",
        "processing": "Processing trace",
        "quality": "Quality gates",
        "data": "Data comparison",
        "research": "Research loop",
        "status": "Run status",
        "gate": "Quality result",
        "rows": "Curated rows",
        "instruments": "Instruments",
        "coverage": "Coverage",
        "passed": "Passed",
        "failed": "Failed",
        "trace": "Evidence completeness",
        "trace_note": "Measures reproducibility evidence, not whether the underlying data is true.",
        "legacy": (
            "This run predates detailed lineage. Rerun the pipeline for field-level evidence."
        ),
        "flow": "Run data flow",
        "market": "Market coverage",
        "market_note": "Liquid instruments rebased to 100 at first close; a coverage check only.",
        "references": "Reference data",
        "source_request": "Vendor request",
        "run_config": "Run configuration",
        "reproduce": "Exact reproduction",
        "download_manifest": "Download full run evidence",
        "row_reconciliation": "Row reconciliation",
        "row_note": (
            "Every non-zero delta requires an explicit filter, quarantine, or aggregation rule."
        ),
        "steps": "Processing steps",
        "fields": "Field-level lineage",
        "fields_note": "How each vendor field becomes canonical data and where the code lives.",
        "all_checks": "All quality checks",
        "checks_note": "Passed and failed checks are retained; no error no longer means no check.",
        "issues": "Issue evidence and samples",
        "no_issues": "This run contains no errors or warnings.",
        "raw": "Raw source evidence",
        "curated": "Curated research data",
        "schema": "Schema and type comparison",
        "preview_note": (
            "At most 200 rows are loaded for review; full snapshots stay out of UI memory."
        ),
        "closed_loop": "Loop status",
        "closed_note": (
            "A complete loop must produce universe, factors, backtest, and report evidence."
        ),
        "available": "Produced",
        "implemented": "Built, not wired",
        "missing": "Not built",
        "baseline_deferred": (
            "Baseline comparison is deferred for this iteration: buy-and-hold, grid trading, "
            "and periodic investment are not evaluated."
        ),
        "research_outputs": "Research artifacts",
        "execution_evidence": "Execution and portfolio evidence",
        "no_runs": "No run is available. Execute the data pipeline first.",
        "missing_local": "The manifest exists, but its local data artifact is unavailable.",
        "source": "Source",
        "commit": "Code version",
    },
}


def _inject_style() -> None:
    st.markdown(
        """
        <style>
        :root { --paper:#f4f1e8; --paper-2:#e9e4d7; --ink:#171915; --muted:#66695f;
          --signal:#d8ff52; --amber:#e5a82b; --rust:#c4482d; --green:#315d3b;
          --line:rgba(23,25,21,.20); }
        .stApp { color:var(--ink); background:radial-gradient(circle at 80% 0%,
          rgba(216,255,82,.16),transparent 25rem),linear-gradient(rgba(23,25,21,.025) 1px,
          transparent 1px),var(--paper); background-size:auto,100% 26px,auto; }
        [data-testid="stHeader"] { background:rgba(244,241,232,.88); }
        [data-testid="stAppDeployButton"] { display:none; }
        [data-testid="stSidebar"] { background:#171915; border-right:1px solid #33372e; }
        [data-testid="stSidebar"] * { color:#f4f1e8; }
        [data-testid="stSidebar"] [data-baseweb="select"] > div {
          background:#272a24; border-color:#4b4f45; }
        .block-container { max-width:1380px; padding:2.4rem 2.2rem 5rem; }
        h1,h2,h3 { font-family:"Noto Serif SC","Songti SC",Georgia,serif !important; }
        p,label,button,[data-testid="stMetricLabel"] {
          font-family:"Cascadia Mono","SFMono-Regular",monospace !important; }
        .qf-masthead { position:relative; overflow:hidden; display:grid;
          grid-template-columns:1fr auto; gap:24px; align-items:end; padding:26px 30px 24px;
          background:var(--ink); color:var(--paper); border-left:8px solid var(--signal);
          box-shadow:8px 8px 0 rgba(23,25,21,.12); }
        .qf-masthead::after { content:"TRACE"; position:absolute; right:-18px; top:-27px;
          font:900 104px/1 "Bahnschrift Condensed",sans-serif; color:rgba(216,255,82,.055);
          letter-spacing:-.05em; }
        .qf-kicker { color:var(--signal); font:600 11px/1.5 "Cascadia Mono",monospace;
          letter-spacing:.16em; }
        .qf-masthead h1 { margin:9px 0 5px; color:var(--paper); font-size:36px;
          letter-spacing:-.035em; }
        .qf-masthead p { margin:0; color:#afb2a6; font-size:12px; }
        .qf-run-stamp { position:relative; z-index:1; min-width:210px; text-align:right; }
        .qf-run-stamp code { color:var(--signal); font-size:11px; }
        .qf-run-stamp div { color:#afb2a6; font:11px/1.7 "Cascadia Mono",monospace; }
        .qf-metrics { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:1px;
          margin:28px 0; background:var(--line); border:1px solid var(--line); }
        .qf-metric { min-height:96px; padding:15px 17px; background:rgba(250,248,241,.94); }
        .qf-metric label { display:block; color:var(--muted); font:10px/1.3
          "Cascadia Mono",monospace; text-transform:uppercase; letter-spacing:.08em; }
        .qf-metric strong { display:block; margin-top:17px; color:var(--ink);
          font:650 22px/1 "Bahnschrift",sans-serif; overflow-wrap:anywhere; }
        .qf-section-title { margin:30px 0 10px; padding-top:10px; border-top:2px solid var(--ink); }
        .qf-section-title span { font:650 11px/1.4 "Cascadia Mono",monospace;
          letter-spacing:.12em; text-transform:uppercase; }
        .qf-section-title p { margin:5px 0 0; color:var(--muted); font-size:11px; }
        .qf-flow { display:grid; grid-template-columns:repeat(6,1fr); gap:7px; margin:18px 0 24px; }
        .qf-node { position:relative; min-height:102px; padding:13px; background:#fffdf6;
          border:1px solid var(--line); }
        .qf-node::after { content:"→"; position:absolute; right:-8px; top:39px; z-index:2;
          color:var(--rust); font-weight:900; }
        .qf-node:last-child::after { content:""; }
        .qf-node small { color:var(--rust); font:650 9px/1 "Cascadia Mono",monospace; }
        .qf-node strong { display:block; margin:17px 0 7px;
          font:650 12px/1.2 "Cascadia Mono",monospace; }
        .qf-node code { color:var(--muted); font-size:9px; }
        .qf-trace-score { display:flex; gap:22px; align-items:center; padding:18px 20px;
          border:1px solid var(--line); background:#fffdf6; }
        .qf-score { flex:0 0 auto; font:800 36px/1 "Bahnschrift",sans-serif; }
        .qf-score em { color:var(--green); font-style:normal; }
        .qf-bar { height:8px; flex:1; background:var(--paper-2); overflow:hidden; }
        .qf-bar i { display:block; height:100%; background:var(--green); }
        .qf-timeline { border-left:2px solid var(--ink); margin:16px 0 12px 13px; }
        .qf-step { position:relative; display:grid; grid-template-columns:44px 170px 1fr 150px;
          gap:12px; padding:15px 14px 18px 25px; border-bottom:1px solid var(--line); }
        .qf-step::before { content:""; position:absolute; left:-7px; top:20px; width:11px;
          height:11px; background:var(--signal); border:2px solid var(--ink); }
        .qf-step b { font:700 11px/1.4 "Cascadia Mono",monospace; }
        .qf-step p { margin:0; color:var(--muted); font-size:10px; line-height:1.6; }
        .qf-step code { color:var(--rust); font-size:9px; overflow-wrap:anywhere; }
        .qf-stage { padding:18px; background:#fffdf6; border:1px solid var(--line);
          border-top:5px solid var(--ink); min-height:155px; }
        .qf-stage[data-state="done"] { border-top-color:var(--green); }
        .qf-stage[data-state="wired"] { border-top-color:var(--amber); }
        .qf-stage[data-state="missing"] { border-top-color:var(--rust); }
        .qf-stage small { font:650 9px/1 "Cascadia Mono",monospace; color:var(--muted); }
        .qf-stage strong { display:block; margin:18px 0 9px; font:700 15px/1.2
          "Noto Serif SC",serif; }
        .qf-stage p { margin:0; color:var(--muted); font-size:10px; line-height:1.55; }
        [data-baseweb="tab-list"] { gap:6px; margin-top:8px; }
        [data-baseweb="tab"] { height:44px; padding:0 16px; background:rgba(255,253,246,.72);
          border:1px solid var(--line); }
        [aria-selected="true"][data-baseweb="tab"] { background:var(--ink); color:var(--signal); }
        [data-testid="stDataFrame"] { border:1px solid var(--line); }
        .stAlert { border-radius:0; }
        @media (max-width:900px) {
          .block-container { padding:1.3rem 1rem 4rem; }
          .qf-masthead { grid-template-columns:1fr; }
          .qf-run-stamp { text-align:left; }
          .qf-metrics { grid-template-columns:repeat(2,1fr); }
          .qf-flow { grid-template-columns:repeat(2,1fr); }
          .qf-node:nth-child(even)::after { content:""; }
          .qf-step { grid-template-columns:34px 1fr; }
          .qf-step p,.qf-step code { grid-column:2; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _escape(value: Any) -> str:
    return html.escape(str(value if value is not None else "—"))


def _summary(manifest: dict[str, Any]) -> dict[str, Any]:
    rows = manifest.get("duckdb_summary", [])
    item = rows[0] if rows else {}
    return {
        "row_count": item.get("row_count", manifest.get("curated", {}).get("row_count", 0)),
        "instrument_count": item.get("instrument_count", 0),
        "first_trade_date": item.get("first_trade_date", "—"),
        "last_trade_date": item.get("last_trade_date", "—"),
    }


def _section(title: str, note: str = "") -> None:
    st.markdown(
        f'<div class="qf-section-title"><span>{_escape(title)}</span><p>{_escape(note)}</p></div>',
        unsafe_allow_html=True,
    )


def _masthead(record: RunRecord, copy: dict[str, str]) -> None:
    manifest = record.manifest
    commit = str(manifest.get("git_commit") or "unavailable")[:10]
    source = manifest.get("config", {}).get("source", "—")
    st.markdown(
        f"""
        <section class="qf-masthead">
          <div><div class="qf-kicker">{_escape(copy["product"])}</div>
            <h1>{_escape(copy["title"])}</h1><p>{_escape(copy["subtitle"])}</p></div>
          <div class="qf-run-stamp"><code>{_escape(record.run_id)}</code>
            <div>{_escape(copy["source"])} · {_escape(source)}</div>
            <div>{_escape(copy["commit"])} · {_escape(commit)}</div></div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _metrics(manifest: dict[str, Any], copy: dict[str, str]) -> None:
    summary = _summary(manifest)
    quality_passed = bool(manifest.get("quality", {}).get("passed"))
    coverage = f"{summary['first_trade_date']} → {summary['last_trade_date']}"
    items = [
        (copy["status"], str(manifest.get("status", "—")).upper()),
        (copy["gate"], copy["passed"] if quality_passed else copy["failed"]),
        (copy["rows"], f"{summary['row_count']:,}"),
        (copy["instruments"], f"{summary['instrument_count']:,}"),
        (copy["coverage"], coverage),
    ]
    cards = "".join(
        f'<div class="qf-metric"><label>{_escape(label)}</label>'
        f"<strong>{_escape(value)}</strong></div>"
        for label, value in items
    )
    st.markdown(f'<div class="qf-metrics">{cards}</div>', unsafe_allow_html=True)


def _flow(manifest: dict[str, Any], language: str, copy: dict[str, str]) -> None:
    steps = manifest.get("lineage", {}).get("processing_steps", [])
    if not steps:
        st.warning(copy["legacy"])
        return
    name_key = "name_zh" if language == "中文" else "name_en"
    nodes = "".join(
        f'<div class="qf-node"><small>0{step.get("order")}</small>'
        f"<strong>{_escape(step.get(name_key))}</strong>"
        f"<code>{_escape(step.get('output_rows'))} rows · "
        f"{_escape(step.get('status'))}</code></div>"
        for step in steps
    )
    st.markdown(f'<div class="qf-flow">{nodes}</div>', unsafe_allow_html=True)


def _trace_score(manifest: dict[str, Any], copy: dict[str, str]) -> None:
    inventory = trace_inventory(manifest)
    present = int((inventory["status"] == "present").sum())
    total = len(inventory)
    percent = int(present / total * 100) if total else 0
    st.markdown(
        f'<div class="qf-trace-score"><div><div class="qf-score"><em>{present}</em>/{total}</div>'
        f'<p>{_escape(copy["trace"])}</p></div><div class="qf-bar">'
        f'<i style="width:{percent}%"></i></div>'
        f"<p>{_escape(copy['trace_note'])}</p></div>",
        unsafe_allow_html=True,
    )


def _render_market(manifest: dict[str, Any], copy: dict[str, str]) -> None:
    _section(copy["market"], copy["market_note"])
    try:
        prices = load_indexed_close_series(manifest)
    except FileNotFoundError:
        st.warning(copy["missing_local"])
        return
    if prices.empty:
        st.info("No price series available.")
        return
    chart = prices.pivot(index="trade_date", columns="instrument_id", values="indexed_close")
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
    st.line_chart(chart, color=palette[: len(chart.columns)], height=330)


def _render_references(manifest: dict[str, Any], copy: dict[str, str]) -> None:
    _section(copy["references"])
    references = manifest.get("reference_data", {})
    if not references:
        st.info("No reference dataset was produced by this adapter.")
        return
    columns = st.columns(len(references))
    for column, (name, payload) in zip(columns, references.items(), strict=True):
        quality = payload.get("quality", {})
        column.metric(
            name.replace("_", " ").upper(),
            f"{quality.get('row_count', 0):,}",
            "PASS" if quality.get("passed") else "FAIL",
        )


def _render_overview(manifest: dict[str, Any], language: str, copy: dict[str, str]) -> None:
    _section(copy["trace"])
    _trace_score(manifest, copy)
    _section(copy["flow"])
    _flow(manifest, language, copy)
    _render_market(manifest, copy)
    _render_references(manifest, copy)


def _render_processing(manifest: dict[str, Any], language: str, copy: dict[str, str]) -> None:
    lineage = manifest.get("lineage", {})
    if not lineage:
        st.warning(copy["legacy"])
        st.dataframe(trace_inventory(manifest), width="stretch", hide_index=True)
        return
    _section(copy["row_reconciliation"], copy["row_note"])
    st.dataframe(row_reconciliation_frame(manifest), width="stretch", hide_index=True)

    _section(copy["steps"])
    steps = processing_steps_frame(manifest, language=language)
    timeline = "".join(
        f'<div class="qf-step"><b>0{_escape(row.order)}</b><b>{_escape(row.name)}</b>'
        f"<p>{_escape(row.rule)}<br>IN {_escape(row.input_rows)} → "
        f"OUT {_escape(row.output_rows)}</p>"
        f"<code>{_escape(row.implementation)}</code></div>"
        for row in steps.itertuples(index=False)
    )
    st.markdown(f'<div class="qf-timeline">{timeline}</div>', unsafe_allow_html=True)

    left, right = st.columns(2)
    with left:
        _section(copy["source_request"])
        st.dataframe(
            flatten_mapping(lineage.get("source_request", {})), width="stretch", hide_index=True
        )
    with right:
        _section(copy["run_config"])
        st.dataframe(flatten_mapping(manifest.get("config", {})), width="stretch", hide_index=True)

    _section(copy["fields"], copy["fields_note"])
    st.dataframe(
        field_lineage_frame(manifest, language=language),
        width="stretch",
        hide_index=True,
        height=520,
    )
    _section(copy["reproduce"])
    reproduction = manifest.get("reproduction", {})
    if reproduction.get("command"):
        st.code(reproduction["command"], language="powershell")
    evidence = {
        copy["commit"]: manifest.get("git_commit"),
        "config_sha256": reproduction.get("config_checksum"),
        "raw_sha256": manifest.get("raw", {}).get("checksum"),
        "staging_sha256": manifest.get("staging", {}).get("checksum"),
        "curated_sha256": manifest.get("curated", {}).get("checksum"),
        "raw_path": manifest.get("raw", {}).get("data_path"),
        "curated_path": manifest.get("curated", {}).get("path"),
    }
    st.dataframe(flatten_mapping(evidence), width="stretch", hide_index=True)
    st.download_button(
        copy["download_manifest"],
        data=json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
        file_name=f"{manifest.get('run_id', 'run')}.json",
        mime="application/json",
    )


def _render_quality(manifest: dict[str, Any], copy: dict[str, str]) -> None:
    checks = quality_checks_frame(manifest)
    _section(copy["all_checks"], copy["checks_note"])
    if checks.empty:
        st.warning(copy["legacy"])
    else:
        counts = checks["status"].value_counts()
        columns = st.columns(4)
        for column, state in zip(columns, ("passed", "warning", "failed", "not_run"), strict=True):
            column.metric(state.upper(), int(counts.get(state, 0)))
        st.dataframe(checks, width="stretch", hide_index=True, height=480)
        st.download_button(
            "Download quality checks / 下载质量检查",
            data=checks.to_csv(index=False),
            file_name=f"{manifest.get('run_id', 'run')}-quality.csv",
            mime="text/csv",
        )

    _section(copy["issues"])
    issues = quality_issues_frame(manifest)
    if issues.empty:
        st.success(copy["no_issues"])
        return
    st.dataframe(issues, width="stretch", hide_index=True)
    reports = [("daily_bars", manifest.get("quality", {}))]
    reports.extend(
        (str(name), payload.get("quality", {}))
        for name, payload in manifest.get("reference_data", {}).items()
    )
    for dataset, report in reports:
        for issue in report.get("issues", []):
            with st.expander(f"{dataset} / {issue.get('check')} / {issue.get('count')} rows"):
                st.write(issue.get("message", ""))
                if issue.get("sample"):
                    st.dataframe(issue["sample"], width="stretch", hide_index=True)


def _schema(frame: Any) -> Any:
    return frame.dtypes.astype(str).rename_axis("field").reset_index(name="dtype")


def _render_data(manifest: dict[str, Any], copy: dict[str, str]) -> None:
    st.caption(copy["preview_note"])
    try:
        raw = load_raw_preview(manifest)
        curated = load_daily_bar_preview(manifest)
    except FileNotFoundError:
        st.warning(copy["missing_local"])
        return
    except ValueError as error:
        st.warning(str(error))
        return
    raw_tab, curated_tab, schema_tab = st.tabs([copy["raw"], copy["curated"], copy["schema"]])
    with raw_tab:
        st.caption(str(manifest.get("raw", {}).get("data_path", "")))
        st.dataframe(raw, width="stretch", hide_index=True, height=500)
        st.download_button(
            "Download Raw preview / 下载 Raw 样本",
            data=raw.to_csv(index=False),
            file_name="raw-preview.csv",
            mime="text/csv",
        )
    with curated_tab:
        st.caption(str(manifest.get("curated", {}).get("path", "")))
        st.dataframe(curated, width="stretch", hide_index=True, height=500)
        st.download_button(
            "Download Curated preview / 下载 Curated 样本",
            data=curated.to_csv(index=False),
            file_name="curated-preview.csv",
            mime="text/csv",
        )
    with schema_tab:
        left, right = st.columns(2)
        left.markdown(f"**{copy['raw']}**")
        left.dataframe(_schema(raw), width="stretch", hide_index=True)
        right.markdown(f"**{copy['curated']}**")
        right.dataframe(_schema(curated), width="stretch", hide_index=True)


def _render_research_loop(manifest: dict[str, Any], copy: dict[str, str]) -> None:
    _section(copy["closed_loop"], copy["closed_note"])
    research = manifest.get("research", {})
    completed = research.get("status") == "succeeded"
    if completed:
        stages = [
            (
                "01",
                "数据采集与清洗 / Data pipeline",
                copy["available"],
                "quality checks · immutable Parquet",
                "done",
            ),
            (
                "02",
                "动态股票池 / PIT universe",
                copy["available"],
                "listing age · lifecycle · ST · liquidity",
                "done",
            ),
            (
                "03",
                "因子与信号 / Factors & signals",
                copy["available"],
                "12-1 momentum · low volatility · target weights",
                "done",
            ),
            (
                "04",
                "成交与组合 / Execution & portfolio",
                copy["available"],
                "orders · fills · costs · holdings · NAV",
                "done",
            ),
            (
                "05",
                "实验记录 / Experiment record",
                copy["available"],
                "metrics · lineage · checksums · limitations",
                "done",
            ),
        ]
    else:
        stages = [
            (
                "01",
                "数据采集与清洗 / Data pipeline",
                copy["available"],
                "run manifest · quality checks · immutable Parquet",
                "done",
            ),
            (
                "02",
                "动态股票池 / PIT universe",
                copy["implemented"],
                "Selection engine exists; no experiment artifact in this run.",
                "wired",
            ),
            (
                "03",
                "因子与信号 / Factors & signals",
                copy["missing"],
                "No factor or target-weight artifact in this run.",
                "missing",
            ),
            (
                "04",
                "成交与组合 / Execution & portfolio",
                copy["missing"],
                "No orders, fills, holdings, or NAV in this run.",
                "missing",
            ),
            (
                "05",
                "实验记录 / Experiment record",
                copy["missing"],
                "Run the experiment command to produce the closed loop.",
                "missing",
            ),
        ]
    columns = st.columns(len(stages))
    for column, (number, name, status, evidence, state) in zip(columns, stages, strict=True):
        column.markdown(
            f'<div class="qf-stage" data-state="{state}"><small>'
            f"{number} · {_escape(status)}</small>"
            f"<strong>{_escape(name)}</strong><p>{_escape(evidence)}</p></div>",
            unsafe_allow_html=True,
        )
    if not completed:
        st.code(
            "python -m quantforge experiment --config configs/research-demo.yaml",
            language="powershell",
        )
        return

    st.info(copy["baseline_deferred"])
    metrics = research.get("metrics", {})
    _section(copy["execution_evidence"])
    metric_items = [
        ("FINAL EQUITY", f"{float(metrics.get('final_equity', 0)):,.2f}"),
        ("TOTAL RETURN", f"{float(metrics.get('total_return', 0)):.2%}"),
        ("MAX DRAWDOWN", f"{float(metrics.get('max_drawdown', 0)):.2%}"),
        ("TURNOVER", f"{float(metrics.get('turnover', 0)):.2f}×"),
        ("FILLS", f"{int(metrics.get('trade_count', 0)):,}"),
    ]
    cards = "".join(
        f'<div class="qf-metric"><label>{_escape(label)}</label>'
        f"<strong>{_escape(value)}</strong></div>"
        for label, value in metric_items
    )
    st.markdown(f'<div class="qf-metrics">{cards}</div>', unsafe_allow_html=True)
    try:
        nav = load_research_artifact(manifest, "nav", limit=10_000)
        if not nav.empty:
            nav["trade_date"] = pd.to_datetime(nav["trade_date"])
            st.line_chart(nav.set_index("trade_date")[["nav"]], height=320, color="#315d3b")
    except (FileNotFoundError, ValueError) as error:
        st.warning(str(error))

    lineage = pd.DataFrame(research.get("lineage", []))
    if not lineage.empty:
        st.dataframe(lineage, width="stretch", hide_index=True)

    _section(copy["research_outputs"])
    artifacts = research_artifacts_frame(manifest)
    st.dataframe(artifacts, width="stretch", hide_index=True)
    names = [
        name
        for name in ("universe", "factors", "signals", "orders", "fills", "holdings", "nav")
        if name in set(artifacts.get("artifact", []))
    ]
    artifact_tabs = st.tabs([name.upper() for name in names])
    for tab, name in zip(artifact_tabs, names, strict=True):
        with tab:
            try:
                st.dataframe(
                    load_research_artifact(manifest, name),
                    width="stretch",
                    hide_index=True,
                    height=420,
                )
            except (FileNotFoundError, ValueError) as error:
                st.warning(str(error))

    with st.expander("Leakage controls / 防泄漏约束"):
        for item in research.get("leakage_controls", []):
            st.markdown(f"- {item}")
    for limitation in research.get("limitations", []):
        st.warning(limitation)


def render_dashboard(project_root: Path, records: list[RunRecord]) -> None:
    language = st.sidebar.selectbox(COPY["中文"]["language"], list(COPY))
    copy = COPY[language]
    st.sidebar.caption(str(project_root))
    if not records:
        st.error(copy["no_runs"])
        return
    labels = {record.run_id: record.label for record in records}
    selected_id = st.sidebar.selectbox(
        copy["run"],
        [record.run_id for record in records],
        format_func=lambda run_id: labels[run_id],
    )
    record = next(item for item in records if item.run_id == selected_id)
    manifest = record.manifest
    _masthead(record, copy)
    _metrics(manifest, copy)
    overview, processing, quality, data, research = st.tabs(
        [copy["overview"], copy["processing"], copy["quality"], copy["data"], copy["research"]]
    )
    with overview:
        _render_overview(manifest, language, copy)
    with processing:
        _render_processing(manifest, language, copy)
    with quality:
        _render_quality(manifest, copy)
    with data:
        _render_data(manifest, copy)
    with research:
        _render_research_loop(manifest, copy)


st.set_page_config(
    page_title="QuantForge · Evidence Console",
    page_icon="◩",
    layout="wide",
    initial_sidebar_state="expanded",
)
_inject_style()
ROOT = _project_root()
render_dashboard(ROOT, discover_runs(ROOT))
