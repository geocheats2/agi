"""Phase 1 unit tests: happy path, budget, controls, redaction, persistence."""

import json

from csa.config import load_settings


def _runtime(env, tmp_path):
    from csa.runtime import Runtime
    settings = load_settings(env=env, env_file=tmp_path / "nope.env")
    return Runtime(settings)


def test_happy_path_completes_with_three_steps(rt, env):
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Investigate bug in calc.py", aid,
                         acceptance=["explain the root cause"])
    task = rt.run_task(tid)
    assert task.status == "completed"
    assert task.tokens_used > 0
    assert task.result_ref == f"{tid}/3-verify.txt"

    # all three artifacts exist
    for name in ("1-plan.txt", "2-work.txt", "3-verify.txt"):
        art = rt.artifacts.read(f"{tid}/{name}")
        assert art.content
        assert len(art.sha256) == 64

    # event log reconstructs the run
    types = [e["type"] for e in reversed(rt.event_log(tid, 100))]
    for expected in ("task_created", "task_activated", "task_completed"):
        assert expected in types
    assert types.count("step_started") == 3
    assert types.count("model_call_completed") == 3


def test_state_survives_reopen(rt, env, tmp_path):
    """Agent + task + events persist after a full Runtime reopen."""
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Persist across reopen", aid)
    rt.activate(tid)
    rt.close()

    rt2 = _runtime(env, tmp_path)
    try:
        t = rt2.task(tid)
        assert t.status == "active"
        assert t.objective == "Persist across reopen"
        a = rt2.agent(aid)
        assert a["role"] == "foreman"
        types = [e["type"] for e in rt2.event_log(tid)]
        assert "task_activated" in types
    finally:
        rt2.close()


def test_budget_enforcement_fails_cleanly(env, tmp_path):
    env["CSA_MAX_TASK_TOKENS"] = "10"  # tiny budget: fake tokens exceed it
    rt = _runtime(env, tmp_path)
    try:
        aid = rt.create_agent("foreman")
        tid = rt.create_task("Burn the budget", aid)
        task = rt.run_task(tid)
        assert task.status == "failed"
        assert "budget exhausted" in task.error
        # no artifact was produced for the failed step
        assert not rt.artifacts.exists(f"{tid}/1-plan.txt")
        types = [e["type"] for e in rt.event_log(tid)]
        assert "task_failed" in types
    finally:
        rt.close()


def test_pause_resume_cycle(rt):
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Pausable task", aid)
    rt.activate(tid)
    rt.pause(tid)
    assert rt.task(tid).status == "blocked"
    rt.resume(tid)
    assert rt.task(tid).status == "active"
    task = rt.run_task(tid)
    assert task.status == "completed"
    types = [e["type"] for e in rt.event_log(tid)]
    assert "task_paused" in types and "task_resumed" in types


def test_pause_mid_run_stops_cleanly(rt):
    """A pausing operator stops a run without corrupting state."""
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Mid-run pause", aid)
    # hook: pause after the first model call completes
    orig = rt._run_step
    calls = {"n": 0}

    def wrapping(task, step):
        ref = orig(task, step)
        calls["n"] += 1
        if calls["n"] == 1:
            rt.pause(tid)
        return ref
    rt._run_step = wrapping
    try:
        task = rt.run_task(tid)
        # run stopped; state is blocked (paused), not corrupted
        assert task.status == "blocked"
        rt.resume(tid)
        final = rt.run_task(tid)
        assert final.status == "completed"
    finally:
        rt._run_step = orig


def test_cancel(rt):
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Doomed task", aid)
    rt.cancel(tid)
    assert rt.task(tid).status == "cancelled"
    # terminal tasks reject further work
    try:
        rt.run_task(tid)
    except Exception:
        pass
    assert rt.task(tid).status == "cancelled"


def test_api_key_never_leaks_into_state(rt, env, capsys):
    """S-1: the secret must not appear in events, tasks, or artifacts."""
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Leak check", aid)
    rt.run_task(tid)
    for e in rt.event_log(tid, 100):
        blob = json.dumps(dict(e), default=str)
        assert "sk-TEST-SECRET-MUST-NEVER-LEAK" not in blob
    row = rt.conn.execute("SELECT * FROM tasks WHERE task_id=?", (tid,)).fetchone()
    assert "sk-TEST-SECRET-MUST-NEVER-LEAK" not in json.dumps(dict(row))
    for name in ("1-plan.txt", "2-work.txt", "3-verify.txt"):
        art = rt.artifacts.read(f"{tid}/{name}")
        assert "sk-TEST-SECRET-MUST-NEVER-LEAK" not in art.content


def test_event_log_is_append_only(rt):
    """No API exists to delete events; count only grows."""
    aid = rt.create_agent("foreman")
    before = rt.conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
    rt.create_task("Append-only probe", aid)
    after = rt.conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
    assert after > before
    assert not hasattr(rt, "delete_event")


def test_model_error_fails_task_cleanly(rt, env):
    class ExplodingModel:
        def call(self, m):
            from csa.model import ModelError
            raise ModelError("engine down", retryable=False)
    rt.model = ExplodingModel()
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Will fail", aid)
    task = rt.run_task(tid)
    assert task.status == "failed"
    assert "model error" in task.error
    types = [e["type"] for e in rt.event_log(tid)]
    assert "task_failed" in types


def test_backend_auto_resolution(tmp_path):
    """auto + no key = fake; auto + key = live (D-09)."""
    env_off = tmp_path / "nope.env"
    s1 = load_settings(env={"CSA_BACKEND": "auto"}, env_file=env_off)
    assert s1.backend == "fake"
    s2 = load_settings(env={"CSA_BACKEND": "auto", "QWEN_API_KEY": "x"},
                       env_file=env_off)
    assert s2.backend == "live"
    s3 = load_settings(env={"CSA_BACKEND": "auto"},
                       env_file=None)  # real os.environ, no forced fake
    assert s3.backend in {"fake", "live"}
