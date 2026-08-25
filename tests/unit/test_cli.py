from pathlib import Path

import pytest

from quantforge.cli import build_parser, main
from quantforge.ui import launcher


def test_dashboard_parser_defaults() -> None:
    args = build_parser().parse_args(["dashboard"])

    assert args.command == "dashboard"
    assert args.project_root == "."
    assert args.port == 8501
    assert args.no_browser is False


def test_dashboard_command_launches_requested_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}

    def fake_launch(project_root: Path, *, port: int, open_browser: bool) -> None:
        captured.update(project_root=project_root, port=port, open_browser=open_browser)

    monkeypatch.setattr(launcher, "launch_dashboard", fake_launch)

    main(
        [
            "dashboard",
            "--project-root",
            str(tmp_path),
            "--port",
            "8765",
            "--no-browser",
        ]
    )

    assert captured == {
        "project_root": Path(tmp_path),
        "port": 8765,
        "open_browser": False,
    }
