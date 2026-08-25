from pathlib import Path

import pytest
import yaml

from quantforge.config import load_config


def test_yaml_rejects_inline_token(tmp_path: Path) -> None:
    payload = {
        "project_root": str(tmp_path),
        "pipeline": {
            "adapter": "tushare",
            "dataset": "daily_bars",
            "source": "tushare",
            "api_token": "must-not-live-here",
        },
    }
    path = tmp_path / "unsafe.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="local .env"):
        load_config(path)


def test_yaml_allows_environment_variable_name(tmp_path: Path) -> None:
    payload = {
        "project_root": str(tmp_path),
        "pipeline": {
            "adapter": "tushare",
            "dataset": "daily_bars",
            "source": "tushare",
            "api_token_env": "QUANTFORGE_TUSHARE_TOKEN",
        },
    }
    path = tmp_path / "safe.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    config = load_config(path)

    assert config.adapter_options["api_token_env"] == "QUANTFORGE_TUSHARE_TOKEN"
