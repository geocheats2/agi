"""Phase 2 - bounded delegation (G2).

Covers, all offline via the deterministic FakeModel:
- happy-path delegation: delegator plans, runs its generic leaf children,
  consolidates their ACTUAL artifact output (no trust), verifies;
- recursion guard: a delegator can never be a child of a delegator;
- depth limit enforcement;
- duplicate-objective rejection under the same parent (not across parents);
- budget anti-evasion: child caps are half the parent's REMAINING budget,
  shrinking as the parent spends;
- child budget overrun -> clean child failure that becomes the parent's
  consolidation evidence (honest spend, no artifact for the failed step);
- wall-clock deadline -> timed_out status;
- waiting_children park + wake (visible blocked_reason, no double charge);
- cancel propagation to all non-terminal descendants;
- Option-D baseline: one generic agent vs a delegation tree, with honest
  per-task token accounting reconciled from the event journal.
"""

import dataclasses
import json

import pytest


def _usage(rt, task_id):
    """(tokens, calls) recorded for one task from model_call_completed."""
    rows = rt.conn.execute(
        "SELECT payload_json FROM events WHERE task_id=? AND type="
        "'model_call_completed'", (task_id,)).fetchall()
    toks = sum(int(json.loads(r["payload_json"] or "{}")["prompt_tokens"])
               + int(json.loads(r["payload_json"] or "{}")["completion_tokens"])
               for r in rows)
    return toks, len(rows)


def _tree_ids(rt, root_id):
    return [root_id] + [c.task_id for c in rt._children(root_id)]


def _event_types(rt, task_id):
    return [e["type"] for e in rt.event_log(task_id, 500)]


def test_delegation_happy_path_checks_child_output(rt, env):
    aid = rt.create_agent("delegator")
    root_id = rt.create_task("Survey and consolidate field notes", aid,
                             task_type="delegation",
                             acceptance=["criterion A", "criterion B"])
    child_ids = rt.spawn_children(root_id, [
        {"objective": "Collect field notes A", "acceptance": ["covers A"]},
        {"objective": "Collect field notes B", "acceptance": ["covers B"]},
    ])

    root = rt.run_task(root_id)
    assert root.status == "completed"
    assert root.blocked_reason is None
    assert root.is_delegator and root.result_ref == \
        rt._step_artifact_ref(root, "verify")

    children = [rt.task(c) for c in child_ids]
    assert [c.objective for c in children] == ["Collect field notes A",
                                               "Collect field notes B"]
    assert [c.parent_index for c in children] == [0, 1]
    assert all(c.status == "completed" for c in children)
    assert all(not c.is_delegator for c in children)

    # The parent's consolidate/verify steps consumed the children's actual
    # result artifacts ("no trust": verdicts reference artifacts, not claims).
    cons = rt.artifacts.read(
        rt._step_artifact_ref(root, "consolidate")).content
    assert "child results" in cons.lower()
    verify = rt.artifacts.read(
        rt._step_artifact_ref(root, "verify")).content
    assert "child results" in verify.lower()

    # Honest accounting: each leaf's tokens_used equals the tokens recorded
    # by its model calls; the root's row includes its own calls plus the
    # children's spend (tree roll-up keeps the root envelope meaningful).
    for c in children:
        toks, calls = _usage(rt, c.task_id)
        assert toks == c.tokens_used and calls == 3
    own_toks, own_calls = _usage(rt, root_id)
    assert own_calls == 3
    assert root.tokens_used == own_toks + \
        sum(c.tokens_used for c in children)
    assert root.tokens_used <= root.max_tokens
    for c in children:
        assert c.tokens_used <= c.max_tokens


def test_recursion_guard_and_depth_limit(rt, env):
    aid = rt.create_agent("delegator")
    root_id = rt.create_task("Root delegation", aid,
                             task_type="delegation", acceptance=["done"])
    (child_id,) = rt.spawn_children(root_id,
                                    [{"objective": "Leaf A",
                                      "acceptance": ["a done"]}])
    child = rt.task(child_id)
    assert child.task_type == "generic" and not child.is_delegator

    # A leaf fits under the depth limit, yet a delegator can never be the
    # child of a delegator (G2 recursion guard).
    assert rt.depth_of(root_id) == 0
    with pytest.raises(RuntimeError, match="recursion guard"):
        rt._spawn_child(rt.task(root_id), objective="Not allowed",
                        task_type="delegation")

    # Depth limit: with max_delegation_depth=0 no children may spawn at all.
    deep_id = rt.create_task("Deep root", aid, task_type="delegation",
                             acceptance=["done"])
    rt.settings = dataclasses.replace(rt.settings, max_delegation_depth=0)
    with pytest.raises(RuntimeError, match="depth limit"):
        rt.spawn_children(deep_id, [{"objective": "Too deep",
                                     "acceptance": ["d"]}])
    # Depth limit 1: a GENERIC root at depth 0 may delegate to a depth-1
    # delegator; that delegator may then spawn no children (depth 2 > 1).
    rt.settings = dataclasses.replace(rt.settings, max_delegation_depth=1)
    generic_root = rt.create_task("Generic umbrella", aid,
                                  task_type="generic", acceptance=["g"])
    (mid_id,) = rt.spawn_children(
        generic_root, [{"objective": "Middle delegator", "acceptance": ["m"],
                        "task_type": "delegation"}])
    assert rt.task(mid_id).is_delegator and rt.depth_of(mid_id) == 1
    with pytest.raises(RuntimeError, match="depth limit"):
        rt.spawn_children(mid_id, [{"objective": "Too deep",
                                    "acceptance": ["d"]}])


def test_duplicate_objective_rejected_under_same_parent(rt, env):
    aid = rt.create_agent("delegator")
    root_id = rt.create_task("Root", aid, task_type="delegation",
                             acceptance=["done"])
    rt.spawn_children(root_id, [{"objective": "Same goal",
                                 "acceptance": ["g"]}])
    with pytest.raises(RuntimeError, match="duplicate task rejected"):
        rt.spawn_children(root_id, [{"objective": "  same  GOAL ",
                                     "acceptance": ["g2"]}])
    # The very same objective is fine under a DIFFERENT parent.
    other_id = rt.create_task("Other root", aid, task_type="delegation",
                              acceptance=["done"])
    (c,) = rt.spawn_children(other_id, [{"objective": "Same goal",
                                         "acceptance": ["g"]}])
    assert rt.task(c).status == "queued"


def test_child_budget_shrinks_with_parent_spend(rt, env):
    aid = rt.create_agent("delegator")
    root_id = rt.create_task("Budgeted root", aid, task_type="delegation",
                             acceptance=["done"])
    (c1,) = rt.spawn_children(root_id, [{"objective": "First child",
                                         "acceptance": ["x"]}])
    first = rt.task(c1)
    # Fresh parent: cap = half of the full budget.
    assert first.max_tokens == rt.task(root_id).max_tokens // 2

    # Once the parent has spent budget (its own steps and/or children),
    # the next spawn's cap reflects the REMAINING budget (anti-evasion).
    with rt.conn:
        rt.conn.execute(
            "UPDATE tasks SET tokens_used=1000, cost_usd=1.0 "
            "WHERE task_id=?", (root_id,))
    (c2,) = rt.spawn_children(root_id, [{"objective": "Second child",
                                         "acceptance": ["x"]}])
    second = rt.task(c2)
    assert second.max_tokens == (rt.task(root_id).max_tokens - 1000) // 2
    assert second.max_tokens < first.max_tokens
    assert second.max_cost_usd == pytest.approx(
        (rt.task(root_id).max_cost_usd - 1.0) / 2.0)
    assert second.max_cost_usd < first.max_cost_usd


def test_child_overrun_fails_cleanly_and_becomes_evidence(rt, env):
    aid = rt.create_agent("delegator")
    root_id = rt.create_task("Tiny budget root", aid,
                             task_type="delegation", acceptance=["done"])
    rt.spawn_children(root_id, [{"objective": "One child",
                                 "acceptance": ["x"]}])
    child_id = rt._children(root_id)[0].task_id
    # Cap the child so its plan fits but a second step busts it.
    with rt.conn:
        rt.conn.execute("UPDATE tasks SET max_tokens=30 WHERE task_id=?",
                        (child_id,))
    root = rt.run_task(root_id)
    child = rt.task(child_id)
    assert child.status == "failed"
    assert "budget exhausted" in (child.error or "")
    # Honest cost: the failing call was charged...
    ctoks, _ = _usage(rt, child_id)
    assert ctoks == child.tokens_used > 0
    # ...but the failed step produced no artifact.
    assert child.step in ("plan", "work", "verify")
    assert not rt.artifacts.exists(rt._step_artifact_ref(child, child.step))
    # The parent did not die on the child's failure: it consolidated the
    # labeled failure evidence and completed with its own verdict.
    assert root.status == "completed"
    cons = rt.artifacts.read(
        rt._step_artifact_ref(root, "consolidate")).content
    assert "child results" in cons.lower()


def test_deadline_times_out_active_task(env, tmp_path):
    from csa.config import load_settings
    from csa.runtime import Runtime
    env = {**env, "CSA_TASK_DEADLINE_MS": "1"}  # effectively expired
    rt2 = Runtime(load_settings(env=env, env_file=tmp_path / "nope.env"))
    try:
        aid = rt2.create_agent("foreman")
        tid = rt2.create_task("Slow task", aid, acceptance=["x"])
        with rt2.conn:
            rt2.conn.execute(
                "UPDATE tasks SET status='active', "
                "activated_at='2000-01-01T00:00:00Z' WHERE task_id=?",
                (tid,))
        t = rt2.run_task(tid)
        assert t.status == "timed_out"
        assert "deadline" in (t.error or "")
        assert "task_timed_out" in _event_types(rt2, tid)
    finally:
        rt2.close()


def test_park_wake_cycle_and_visible_waiting_state(rt, env):
    aid = rt.create_agent("delegator")
    root_id = rt.create_task("Park root", aid, task_type="delegation",
                             acceptance=["done"])
    (child_id,) = rt.spawn_children(root_id, [{"objective": "Slow child",
                                               "acceptance": ["x"]}])
    # Parent active at consolidate; child active mid-flight -> the runtime
    # parks the parent visibly (blocked, reason=waiting_children).
    rt.activate(root_id)
    rt._run_step(rt.task(root_id), "plan")
    rt.activate(child_id)
    rt._run_step(rt.task(child_id), "plan")
    assert rt.task(child_id).status == "active"
    rt._wait_blocked(rt.task(root_id))

    state = rt.task(root_id)
    assert state.status == "blocked"
    assert state.blocked_reason == "waiting_children"
    assert "task_blocked_waiting_children" in _event_types(rt, root_id)
    # Child's plan step was charged exactly once - parking is free.
    ctoks, ccalls = _usage(rt, child_id)
    assert ccalls == 1 and ctoks > 0

    # Operator finishes the child (its remaining generic steps are
    # work/verify); the next run_task WAKES the parent, consolidates the
    # child output, and completes.
    rt._run_step(rt.task(child_id), "work")
    rt._run_step(rt.task(child_id), "verify")
    assert rt.task(child_id).status == "completed"
    root = rt.run_task(root_id)
    assert root.status == "completed"
    assert "task_woken" in _event_types(rt, root_id)
    cons = rt.artifacts.read(
        rt._step_artifact_ref(root, "consolidate")).content
    assert "child results" in cons.lower()
    # Wake must not re-charge completed work: the child ran exactly
    # plan+write+verify (3 calls) and is never re-executed by the wake.
    assert _usage(rt, child_id)[1] == 3


def test_operator_pause_then_completion(rt, env):
    aid = rt.create_agent("delegator")
    root_id = rt.create_task("Pausable root", aid, task_type="delegation",
                             acceptance=["done"])
    (child_id,) = rt.spawn_children(root_id, [{"objective": "Child",
                                               "acceptance": ["x"]}])
    rt.pause(root_id)
    assert rt.task(root_id).status == "blocked"
    assert rt.task(root_id).blocked_reason is None  # operator pause, not a
    # dependency wait
    rt.resume(root_id)
    root = rt.run_task(root_id)
    assert root.status == "completed"
    assert rt.task(child_id).status == "completed"


def test_cancel_propagates_to_descendants(rt, env):
    aid = rt.create_agent("delegator")
    root_id = rt.create_task("Cancel root", aid, task_type="delegation",
                             acceptance=["done"])
    child_ids = rt.spawn_children(root_id, [
        {"objective": f"Cancellable {i}", "acceptance": [f"c{i}"]}
        for i in range(3)])
    rt.cancel(root_id)
    assert rt.task(root_id).status == "cancelled"
    for cid in child_ids:
        assert rt.task(cid).status == "cancelled"
    rows = rt.conn.execute(
        "SELECT task_id, summary FROM events WHERE type='task_cancelled'"
    ).fetchall()
    by_task = {r["task_id"]: r["summary"] for r in rows}
    assert len(by_task) == 4
    assert "propagated" in by_task[child_ids[0]]
    assert "propagated" not in by_task[root_id]


def test_single_agent_baseline_vs_delegation_option_d(rt, env):
    """Milestone exit criterion: an A/B comparison exists between (a) one
    generic agent handling the objective end-to-end and (b) a delegation
    tree. Token/cost figures are reconciled from the append-only event
    journal so the comparison is reproducible from on-disk state."""
    objective = "Produce a two-section report"
    acceptance = ["has section A", "has section B", "is consolidated"]

    solo_id = rt.create_task(objective, rt.create_agent("foreman"),
                             acceptance=acceptance)
    solo = rt.run_task(solo_id)
    assert solo.status == "completed"
    solo_toks, solo_calls = _usage(rt, solo_id)

    root_id = rt.create_task(objective, rt.create_agent("delegator"),
                             task_type="delegation", acceptance=acceptance)
    rt.spawn_children(root_id, [
        {"objective": "Write section A", "acceptance": ["has section A"]},
        {"objective": "Write section B", "acceptance": ["has section B"]},
    ])
    root = rt.run_task(root_id)
    assert root.status == "completed"

    tree_toks = sum(_usage(rt, t)[0] for t in _tree_ids(rt, root_id))
    tree_calls = sum(_usage(rt, t)[1] for t in _tree_ids(rt, root_id))

    # Delegation does extra work: coordination steps + consolidation +
    # per-child pipelines -> strictly more model calls than the solo run.
    assert tree_calls > solo_calls
    assert tree_toks >= solo_toks
    cons = rt.artifacts.read(
        rt._step_artifact_ref(root, "consolidate")).content
    assert "child results" in cons.lower()
    # Envelopes held everywhere; root row aggregates the whole tree.
    assert solo_toks == solo.tokens_used <= solo.max_tokens
    assert root.tokens_used == tree_toks <= root.max_tokens
    for c in rt._children(root_id):
        assert _usage(rt, c.task_id)[0] == c.tokens_used <= c.max_tokens