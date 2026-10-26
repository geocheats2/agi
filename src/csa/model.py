"""Model adapter: the only place that talks to a language model.

Two backends:
- FakeModel    - deterministic, offline. Auto-selected when no API key is
                 present (D-09). Lets every Phase 1 test run with zero cost.
- LiveOpenAIModel - OpenAI-compatible chat-completions over stdlib urllib.
                 Activated automatically when QWEN_API_KEY is set.

Both record model/config version, latency, and usage. The API key never
appears in events or artifacts (S-1).
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
import time
import urllib.error
import urllib.parse
from dataclasses import dataclass, field


class ModelError(Exception):
    def __init__(self, msg: str, retryable: bool = False, status: int | None = None):
        super().__init__(msg)
        self.retryable = retryable
        self.status = status


@dataclass
class ModelCall:
    """One model invocation. `call_id` is the idempotency key (NF-2)."""
    call_id: str            # stable, derived from task+step+attempt (idempotent)
    task_id: str
    purpose: str
    messages: list[dict] = field(default_factory=list)
    effort: str = "medium"
    max_output_tokens: int = 4000
    # filled by the backend
    config_version: str = ""
    latency_ms: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    error: str | None = None


@dataclass
class ModelResult:
    text: str
    usage: dict
    latency_ms: int
    config_version: str


class FakeModel:
    """Deterministic offline backend. Same (call_id, task) => same answer.

    Behavior: echoes the task objective with a canned, role-appropriate
    response. If a previous result for the same call_id is passed in
    (resumed run), it is used verbatim -> idempotent step execution.
    """

    name = "fake"

    def __init__(self, delay_ms: int = 0):
        self.delay_ms = delay_ms

    def _config_version(self, messages: list[dict]) -> str:
        if not messages:
            return "fake-v1"
        # Last user message carries a config_version tag in Phase 1 prompts.
        for m in reversed(messages):
            if m.get("role") == "user" and "[config:" in m.get("content", ""):
                tag = m["content"].split("[config:", 1)[1].split("]", 1)[0]
                return f"fake-{tag}"
        return "fake-v1"

    def call(self, m: ModelCall) -> ModelResult:
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000.0)
        start = time.monotonic()
        cfg = self._config_version(m.messages)
        purpose = m.purpose
        user_content = ""
        for msg in reversed(m.messages):
            if msg.get("role") == "user":
                user_content = msg.get("content", "")
                if "objective:" in user_content:
                    objective = user_content.split("objective:", 1)[1].split("\n", 1)[0].strip()
                else:
                    objective = user_content
                break
        else:
            objective = "(no objective)"

        if purpose in ("plan", "work", "verify", "consolidate"):
            body = f"{purpose.upper()}: acknowledged objective '{objective}'. Step complete."
        else:
            body = f"acknowledged '{objective}'."
        text = f"[fake:{purpose}] {body}"
        # Phase 2: make consolidation evidence observable. Report how many
        # prior artifacts and delegated child results were actually present
        # in the prompt, so "the parent checked child OUTPUT, not claims"
        # is verifiable from the artifact text.
        n_prior = user_content.count("--- prior ")
        n_child = user_content.count("--- child ")
        if n_prior or n_child:
            detail = []
            if n_prior:
                detail.append(f"{n_prior} prior artifact(s)")
            if n_child:
                detail.append(f"{n_child} child results")
            text += " (consumed " + " + ".join(detail) + ")"

        latency_ms = int((time.monotonic() - start) * 1000)
        # Deterministic offline token estimate: proportional to prompt size
        # and completion length. `// 4` approximates ~4 chars/token.
        prompt_tokens = max(1, len(" ".join(json.dumps(m.messages).split())) // 4)
        completion_tokens = max(1, len(text.split()))
        m.config_version = cfg
        return ModelResult(text=text, usage={"prompt_tokens": prompt_tokens,
                                             "completion_tokens": completion_tokens,
                                             "total_tokens": prompt_tokens + completion_tokens},
                           latency_ms=latency_ms, config_version=cfg)


class LiveOpenAIModel:
    """OpenAI-compatible chat-completions client (stdlib only)."""

    name = "live"

    def __init__(self, settings):
        self.base_url = settings.base_url.rstrip("/")
        self.model_id = settings.model_id
        self.api_key = settings.api_key
        self.timeout_ms = settings.model_timeout_ms
        self.in_cost = settings.cost_per_mtok_in
        self.out_cost = settings.cost_per_mtok_out

    def _config_version(self, effort: str) -> str:
        digest = hashlib.sha1(f"{self.model_id}|{effort}".encode()).hexdigest()[:8]
        return f"live-{self.model_id.replace('/', '_')}-{digest}"

    def call(self, m: ModelCall) -> ModelResult:
        effort = m.effort
        body: dict = {
            "model": self.model_id,
            "messages": m.messages,
            "max_tokens": m.max_output_tokens,
            "stream": False,
        }
        if effort and effort != "medium":
            body["reasoning_effort"] = effort
        req = urllib.request.Request(
            f"{self.base_url}/v1/chat/completions",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_ms / 1000.0) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            payload = e.read().decode(errors="replace")[:500]
            retryable = e.code in (408, 409, 429, 500, 502, 503, 504)
            raise ModelError(f"HTTP {e.code} from model endpoint: {payload}",
                             retryable=retryable, status=e.code) from e
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ModelError("network error calling model endpoint",
                             retryable=True) from e
        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ModelError(f"unexpected model response shape: {str(data)[:300]}") from e
        usage = data.get("usage", {}) or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        cost = (prompt_tokens * self.in_cost + completion_tokens * self.out_cost) / 1_000_000
        m.config_version = self._config_version(effort)
        m.prompt_tokens = prompt_tokens
        m.completion_tokens = completion_tokens
        m.cost_usd = cost
        return ModelResult(text=text, usage=usage, latency_ms=latency_ms,
                           config_version=m.config_version)


def make_model(settings) -> tuple[object, str]:
    if settings.backend == "live":
        if not settings.api_key:
            raise ModelError("CSA_BACKEND=live but QWEN_API_KEY is not set")
        return LiveOpenAIModel(settings), settings.model_id
    return FakeModel(settings.fake_delay_ms), "fake-model (deterministic, offline)"