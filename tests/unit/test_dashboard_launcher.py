from pathlib import Path

import pytest

from quantforge.ui import launcher


def test_launch_dashboard_builds_local_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict = {}
    monkeypatch.setattr(launcher.importlib.util, "find_spec", lambda name: object())

    def fake_run(command: list[str], *, check: bool, env: dict[str, str]) -> None:
        captured.update(command=command, check=check, env=env)

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)

    launcher.launch_dashboard(tmp_path, port=8765, open_browser=False)

    assert captured["check"] is True
    assert captured["env"]["QUANTFORGE_PROJECT_ROOT"] == str(tmp_path.resolve())
    assert "streamlit" in captured["command"]
    assert "8765" in captured["command"]
    assert captured["command"][captured["command"].index("--server.headless") + 1] == "true"


def test_launch_dashboard_explains_optional_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launcher.importlib.util, "find_spec", lambda name: None)

    with pytest.raises(RuntimeError, match=r"\[ui\]"):
        launcher.launch_dashboard(tmp_path)
