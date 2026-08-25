from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from quantforge.pipeline import run_pipeline_from_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantforge",
        description="QuantForge audit-first quantitative research platform",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    pipeline = subparsers.add_parser("pipeline", help="Run the reproducible vertical slice")
    pipeline.add_argument("--config", default="configs/mvp.yaml", help="YAML configuration path")
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
