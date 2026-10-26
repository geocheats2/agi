"""Settings: loaded from environment, with a minimal .env fallback parser.

No third-party dependencies. Real environment variables always win over .env.
Secrets are never written to state files by this module.
"""

from __future__ import annotations

import dataclasses
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


@dataclasses.dataclass(frozen=True)
class Settings:
    base_url: str
    model_id: str
    api_key: str
    backend: str  # resolved: "fake" | "live"
    reasoning_effort: str
    model_timeout_ms: int
    max_task_tokens: int
    max_task_run_cost_usd: float
    max_concurrent_tasks: int
    max_delegation_depth: int
    task_deadline_ms: int
    cost_per_mtok_in: float
    cost_per_mtok_out: float
    fake_delay_ms: int
    db_path: Path
    artifacts_root: Path


def _resolve(root: Path, value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else root / p


def load_settings(env: dict[str, str] | None = None,
                  env_file: Path | None = None) -> Settings:
    environ = dict(os.environ if env is None else env)
    file_values = _parse_env_file(env_file or PROJECT_ROOT / ".env")
    merged: dict[str, str] = {}
    merged.update({k: v for k, v in file_values.items() if v != ""})
    merged.update({k: v for k, v in environ.items() if v != ""})

    def get(key: str, default: str = "") -> str:
        return merged.get(key, default)

    def get_int(key: str, default: int) -> int:
        try:
            return int(get(key, str(default)))
        except ValueError:
            return default

    def get_float(key: str, default: float) -> float:
        try:
            return float(get(key, str(default)))
        except ValueError:
            return default

    api_key = get("QWEN_API_KEY")
    raw_backend = get("CSA_BACKEND", "auto").lower()
    if raw_backend == "auto":
        backend = "live" if api_key else "fake"
    else:
        backend = raw_backend  # "fake" | "live"

    return Settings(
        base_url=get("QWEN_BASE_URL", "http://100.105.83.8:8080/"),
        model_id=get("QWEN_MODEL_ID", "Qwen/Qwen3.8-27B-FP8"),
        api_key=api_key,
        backend=backend,
        reasoning_effort=get("CSA_REASONING_EFFORT", "medium").lower(),
        model_timeout_ms=get_int("CSA_MODEL_TIMEOUT_MS", 120000),
        max_task_tokens=get_int("CSA_MAX_TASK_TOKENS", 200000),
        max_task_run_cost_usd=get_float("CSA_MAX_TASK_RUN_COST_USD", 5.0),
        max_concurrent_tasks=get_int("CSA_MAX_CONCURRENT_TASKS", 1),
        max_delegation_depth=get_int('CSA_MAX_DELEGATION_DEPTH', 2),
        task_deadline_ms=get_int('CSA_TASK_DEADLINE_MS', 1800000),
        cost_per_mtok_in=get_float("QWEN_COST_PER_MTOK_IN", 0.0),
        cost_per_mtok_out=get_float("QWEN_COST_PER_MTOK_OUT", 0.0),
        fake_delay_ms=get_int("CSA_FAKE_DELAY_MS", 0),
        db_path=_resolve(PROJECT_ROOT, get("CSA_DB", "csa-data/csa.db")),
        artifacts_root=_resolve(PROJECT_ROOT, get("CSA_ARTIFACTS", "artifacts/runs")),
    )
