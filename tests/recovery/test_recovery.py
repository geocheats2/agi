"""Fault-injection recovery tests (charter NF-1, NF-2; Phase 1 exit criteria).

'Kills' are simulated by dropping the Runtime (closing the connection) while
a task is in 'active' status - exactly what a host crash/WAL-rolled journal
leaves behind, plus a clean-shutdown variant.
"""

import json
import sqlite3

from csa.config import load_settings


def _settings(env, tmp_path):
    return load_settings(env=env, env_file=tmp_path / "nope.env")


def _rt(env, tmp_path):
    from csa.runtime import Runtime
    return Runtime(_settings(env, tmp_path))


# ---------- the kill-mid-run test ----------

def test_task_survives_kill_and_resumes(env, tmp_path):
    env = dict(env, CSA_FAKE_DELAY_MS="25")
    rt = _rt(env, tmp_path)
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Survive the crash", aid)
    rt.activate(tid)  # status -> active

    plan_ref = f"{tid}/1-plan.txt"
    # Run until the first step has fully committed (plan artifact on disk).
    # This stands in for the process living only long enough for step 1.
    rt._run_step(rt.task(tid), "plan")
    rt._event(rt.conn, "artifact_written", "runtime", tid, aid, None, None,
              "info", "step artifact for 'plan'", {"ref": plan_ref})
    rt.conn.commit()

    # KILL: the process dies while the task is still 'active', mid-task.
    rt.close()

    # Sanity: on disk the task really is in-flight.
    conn = sqlite3.connect(env["CSA_DB"])
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT status, step FROM tasks WHERE task_id=?",
                       (tid,)).fetchone()
    assert row["status"] == "active"
    conn.close()

    # RESTART: new process opens the same DB.
    rt2 = _rt(env, tmp_path)
    try:
        assert rt2.task(tid).status == "active"
        recovered = rt2.recover()
        assert recovered == [tid]
        assert rt2.task(tid).status == "queued"

        # Resumed run: step 1 must NOT re-invocation cost; steps 2 & 3 complete.
        task = rt2.run_task(tid)
        assert task.status == "completed"
        assert task.result_ref == f"{tid}/3-verify.txt"

        plan_events = [
            e for e in rt2.event_log(tid, 200)
            if e["type"] == "model_call_completed"
            and json.loads(e["payload_json"] or "{}").get("artifact") == plan_ref
        ]
        assert len(plan_events) == 1, "plan step must run exactly once"
        resume_marks = [e for e in rt2.event_log(tid, 200)
                        if e["type"] == "step_started"]
        # 'work' step context must have carried the prior plan in (idempotent
        # resume), logged as a resume_note
        work_notes = [e["summary"] for e in resume_marks
                      if "work" in e["summary"] and "resuming" in e["summary"]]
        assert work_notes, "resume must reuse prior artifacts"
    finally:
        rt2.close()


# ---------- kill after clean shutdown (double-run guard) ----------

def test_completed_task_is_not_rerun(env, tmp_path):
    rt = _rt(env, tmp_path)
    aid = rt.create_agent("foreman")
    tid = rt.create_task("No double spend", aid)
    rt.run_task(tid)
    before = rt.task(tid).tokens_used
    rt.close()

    rt2 = _rt(env, tmp_path)
    try:
        assert rt2.recover() == []  # nothing in flight
        task = rt2.run_task(tid)
        assert task.status == "completed"
        assert rt2.task(tid).tokens_used == before, "terminal task must not accrue cost"
    finally:
        rt2.close()


# ---------- idempotent step re-entry ----------

def test_step_reruns_are_idempotent(env, tmp_path):
    """Calling _run_step twice for the same step reuses the artifact."""
    rt = _rt(env, tmp_path)
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Idempotent steps", aid)
    rt.activate(tid)
    tokens_0 = rt.task(tid).tokens_used
    ref1 = rt._run_step(rt.task(tid), "plan")
    planned_after_first = rt.task(tid).tokens_used
    assert planned_after_first > tokens_0
    # A repeat of the same step (duplicate call / crash re-entry) must not
    # re-invoke the model or re-charge tokens.
    ref2 = rt._run_step(rt.task(tid), "plan")
    assert ref2 == ref1
    assert rt.task(tid).tokens_used == planned_after_first
    rt.close()


# ---------- WAL: reader/writer survive ----------

def test_wal_mode_active(env, tmp_path):
    rt = _rt(env, tmp_path)
    mode = rt.conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"
    rt.close()


def test_artifacts_are_hash_consistent(env, tmp_path):
    rt = _rt(env, tmp_path)
    aid = rt.create_agent("foreman")
    tid = rt.create_task("Hash check", aid)
    rt.run_task(tid)
    for name in ("1-plan.txt", "2-work.txt", "3-verify.txt"):
        a = rt.artifacts.read(f"{tid}/{name}")
        b = rt.artifacts.read(f"{tid}/{name}")
        assert a.sha256 == b.sha256
        assert len(a.sha256) == 64
    rt.close()
