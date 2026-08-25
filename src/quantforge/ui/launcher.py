from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path


def launch_dashboard(
    project_root: str | Path,
    *,
    port: int = 8501,
    open_browser: bool = True,
) -> None:
    """Launch the optional Streamlit UI in a separate Python process."""

    if importlib.util.find_spec("streamlit") is None:
        raise RuntimeError(
            'Dashboard dependencies are missing. Install them with: pip install -e ".[ui]"'
        )
    root = Path(project_root).resolve()
    app_path = Path(__file__).with_name("app.py")
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.headless",
        str(not open_browser).lower(),
        "--browser.gatherUsageStats",
        "false",
    ]
    environment = os.environ.copy()
    environment["QUANTFORGE_PROJECT_ROOT"] = str(root)
    subprocess.run(command, check=True, env=environment)
