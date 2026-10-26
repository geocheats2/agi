from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from csa.config import load_settings  # noqa: E402
from csa.runtime import Runtime  # noqa: E402


@pytest.fixture()
def env(tmp_path):
    return {
        "CSA_BACKEND": "fake",
        "QWEN_API_KEY": "sk-TEST-SECRET-MUST-NEVER-LEAK",
        "CSA_DB": str(tmp_path / "test.db"),
        "CSA_ARTIFACTS": str(tmp_path / "artifacts"),
        "CSA_MAX_TASK_TOKENS": "200000",
        "CSA_MAX_TASK_RUN_COST_USD": "5",
    }


@pytest.fixture()
def rt(env, tmp_path):
    settings = load_settings(env=env, env_file=tmp_path / "nope.env")
    runtime = Runtime(settings)
    yield runtime
    runtime.close()
