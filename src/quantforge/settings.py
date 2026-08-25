from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


class MissingSecretError(RuntimeError):
    """Raised when an enabled adapter lacks a required local credential."""


def load_local_env(project_root: str | Path) -> Path:
    """Load a Git-ignored .env without replacing operating-system values."""
    env_path = Path(project_root).resolve() / ".env"
    load_dotenv(dotenv_path=env_path, override=False)
    return env_path


def require_secret(name: str) -> str:
    """Return a secret without logging it, or explain where to configure it."""
    value = os.getenv(name, "").strip()
    if not value:
        raise MissingSecretError(
            f"Missing required secret {name}. Add it to the local .env file; "
            "do not pass it as a command-line argument."
        )
    return value


def secret_status(*names: str) -> dict[str, bool]:
    """Safe diagnostic: report presence only, never values or lengths."""
    return {name: bool(os.getenv(name, "").strip()) for name in names}
