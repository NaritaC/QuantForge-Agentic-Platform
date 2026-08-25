from pathlib import Path

import pytest

from quantforge.settings import MissingSecretError, load_local_env, require_secret, secret_status


def test_local_env_does_not_override_operating_system_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("QUANTFORGE_TEST_SECRET=from-file\n", encoding="utf-8")
    monkeypatch.setenv("QUANTFORGE_TEST_SECRET", "from-system")

    load_local_env(tmp_path)

    assert require_secret("QUANTFORGE_TEST_SECRET") == "from-system"
    assert secret_status("QUANTFORGE_TEST_SECRET") == {"QUANTFORGE_TEST_SECRET": True}


def test_missing_secret_error_never_contains_a_secret_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUANTFORGE_ABSENT_SECRET", raising=False)

    with pytest.raises(MissingSecretError, match="local .env"):
        require_secret("QUANTFORGE_ABSENT_SECRET")
