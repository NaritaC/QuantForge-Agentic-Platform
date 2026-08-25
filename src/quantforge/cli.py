from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from quantforge.pipeline import run_pipeline_from_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantforge",
        description="QuantForge audit-first quantitative research platform",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    pipeline = subparsers.add_parser("pipeline", help="Run the reproducible vertical slice")
    pipeline.add_argument("--config", default="configs/mvp.yaml", help="YAML configuration path")
    dashboard = subparsers.add_parser("dashboard", help="Open the local research ledger")
    dashboard.add_argument(
        "--project-root", default=".", help="Project root containing artifacts and data"
    )
    dashboard.add_argument("--port", type=int, default=8501, help="Local dashboard port")
    dashboard.add_argument(
        "--no-browser", action="store_true", help="Start without opening a browser window"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "pipeline":
        result = run_pipeline_from_path(args.config)
        summary = {
            "run_id": result["run_id"],
            "status": result["status"],
            "quality_passed": result["quality"]["passed"],
            "curated_snapshot": result["curated"]["snapshot_id"],
            "duckdb_summary": result["duckdb_summary"],
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    elif args.command == "dashboard":
        from quantforge.ui.launcher import launch_dashboard

        launch_dashboard(Path(args.project_root), port=args.port, open_browser=not args.no_browser)
