"""Durable task & agent state (Phase 1 core) + bounded delegation (Phase 2).

Guarantees carried forward from Phase 1:
- Every transition is (event + state row) committed in ONE transaction ->
  recoverable, auditable, no half-states after a crash.
- Step execution is idempotent: the result artifact and the token accounting
  are committed together; a crash+resume reuses completed results and never
  double-counts cost (NF-2).
- The event log is append-only.

Phase 2 additions (bounded delegation, G2):
- Delegation tasks use steps [plan, consolidate, verify]; between plan and
  consolidate the parent WAITS (blocked, reason=waiting_children) and runs
  its own children first. The parent does the children's work itself — no
  unattended recursion (D-08: concurrency 1).
- Bounded by: max delegation depth (CSA_MAX_DELEGATION_DEPTH), child budget
  never exceeding the parent's remaining budget, duplicate-objective
  rejection under the same parent, and a wall-clock deadline per task.
- Cancel propagation: cancelling a task cancels all non-terminal descendants.
- Parents judge children's RESULTS (consolidate step sees every child result
  artifact + status), not the children's claims (no trust).
"""

from __future__ import annotations

import calendar
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass

from .artifacts import ArtifactStore
from .config import Settings
from .db import connect, init_db
from .model import LiveOpenAIModel, ModelCall, ModelError, make_model

TERMINAL = {"completed", "failed", "cancelled", "timed_out"}
STEP_ORDER = ["plan", "work", "verify"]
DELEGATION_STEPS = ["plan", "consolidate", "verify"]

SYSTEM_PROMPTS = {
    "plan": ("You are a research foreman. Produce a minimal step-by-step plan "
             "for the objective. No external actions; local analysis only."),
    "work": ("You are a specialist worker. Execute the plan for the objective. "
             "State your main findings and evidence. No external actions."),
    "verify": ("You are an independent reviewer. Check a draft result against "
               "the acceptance criteria. State verdict: pass/fail with reasons."),
    "consolidate": ("You are a research foreman consolidating the results of "
                    "subtasks you delegated. Use ONLY the child results and "
                    "their stated evidence; do not invent findings. State a "
                    "verdict on each acceptance criterion (met / not met / "
                    "needs-attention) and name the evidence ref for each."),
}


class _BudgetExceeded(Exception):
    pass


class _TimedOut(Exception):
    pass


@dataclass
class Task:
    task_id: str
    parent_task_id: str | None
    owner_agent_id: str
    task_type: str
    objective: str
    acceptance: list[str]
    status: str
    step: str | None
    result_ref: str | None
    max_tokens: int
    max_cost_usd: float
    tokens_used: int
    cost_usd: float
    error: str | None = None
    finished_at: str | None = None
    created_at: str | None = None
    parent_index: int = 0
    blocked_reason: str | None = None

    @property
    def is_delegator(self) -> bool:
        return self.task_type == "delegation"

    def to_payload(self) -> dict:
        return {
            "task_id": self.task_id, "parent_task_id": self.parent_task_id,
            "owner_agent_id": self.owner_agent_id, "type": self.task_type,
            "objective": self.objective, "status": self.status,
            "step": self.step, "result_ref": self.result_ref,
            "max_tokens": self.max_tokens, "max_cost_usd": self.max_cost_usd,
            "tokens_used": self.tokens_used, "cost_usd": round(self.cost_usd, 6),
            "error": self.error, "finished_at": self.finished_at,
            "parent_index": self.parent_index,
            "blocked_reason": self.blocked_reason,
        }

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Task":
        return cls(
            task_id=row["task_id"], parent_task_id=row["parent_task_id"],
            owner_agent_id=row["owner_agent_id"], task_type=row["type"],
            objective=row["objective"],
            acceptance=json.loads(row["acceptance_json"] or "[]"),
            status=row["status"], step=row["step"],
            result_ref=row["result_ref"], max_tokens=row["max_tokens"],
            max_cost_usd=row["max_cost_usd"], tokens_used=row["tokens_used"],
            cost_usd=row["cost_usd"], error=row["error"],
            finished_at=row["finished_at"], created_at=row["created_at"],
            parent_index=row["parent_index"],
            blocked_reason=row["blocked_reason"],
        )


class Runtime:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.conn = connect(settings.db_path)
        init_db(self.conn)
        self.artifacts = ArtifactStore(settings.artifacts_root)
        self.model, self.model_name = make_model(settings)

    @staticmethod
    def _now() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # ---------------- event log (append-only) ----------------

    _POLICY_EVENTS = {"artifact_written", "model_call", "model_call_completed",
                      "model_call_failed"}

    def _event(self, conn: sqlite3.Connection, etype: str, actor: str,
               task_id: str | None, agent_id: str | None,
               prior: int | None, resulting: int | None,
               severity: str, summary: str, payload: dict | None = None) -> None:
        conn.execute(
            "INSERT INTO events (ts, type, actor, task_id, agent_id,"
            " prior_state_version, resulting_state_version, severity,"
            " authorization, summary, payload_json)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (self._now(), etype, actor, task_id, agent_id,
             prior, resulting, severity,
             "runtime-policy:read-local" if etype in self._POLICY_EVENTS else None,
             summary, json.dumps(payload) if payload is not None else None))

    # ---------------- agents ----------------

    def create_agent(self, role: str, agent_id: str | None = None) -> str:
        aid = agent_id or f"agent-{role[:3]}-{uuid.uuid4().hex[:8]}"
        ts = self._now()
        with self.conn:
            self._event(self.conn, "agent_created", "runtime", None, aid,
                        None, 1, "info", f"agent created: role={role}")
            self.conn.execute(
                "INSERT INTO agents (agent_id, role, model_name, config_version,"
                " constitution_version, state_json, state_version, created_at,"
                " updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (aid, role, self.model_name, "v0", "v0.1.0", "{}", 1, ts, ts))
        return aid

    def agent(self, agent_id: str) -> sqlite3.Row:
        return self._must(self.conn.execute(
            "SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone(),
            f"unknown agent: {agent_id}")

    # ---------------- helpers: tree position ----------------

    def depth_of(self, task_id: str | None) -> int:
        """0 for a root task, +1 per ancestor level."""
        depth = 0
        cur = task_id
        seen = set()
        while cur and cur not in seen:  # cycle guard (should be impossible)
            seen.add(cur)
            row = self.conn.execute(
                "SELECT parent_task_id FROM tasks WHERE task_id=?",
                (cur,)).fetchone()
            if not row or row["parent_task_id"] is None:
                break
            cur = row["parent_task_id"]
            depth += 1
        return depth

    def _child_index(self, parent_task_id: str | None) -> int:
        if not parent_task_id:
            return 0
        row = self.conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE parent_task_id=?",
            (parent_task_id,)).fetchone()
        return int(row["n"])

    def _children(self, parent_task_id: str) -> list[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE parent_task_id=? ORDER BY parent_index",
            (parent_task_id,)).fetchall()
        return [Task.from_row(r) for r in rows]

    def _non_terminal_children(self, parent_task_id: str) -> list[Task]:
        return [c for c in self._children(parent_task_id)
                if c.status not in TERMINAL]

    def _step_order_for(self, task: Task) -> list[str]:
        return DELEGATION_STEPS if task.is_delegator else STEP_ORDER

    def _step_artifact_ref(self, task: Task, step: str) -> str:
        idx = self._step_order_for(task).index(step) + 1
        return f"{task.task_id}/{idx}-{step}.txt"

    # ---------------- tasks ----------------

    def create_task(self, objective: str, owner_agent_id: str, task_type: str = "generic",
                    acceptance: list[str] | None = None,
                    parent_task_id: str | None = None, task_id: str | None = None) -> str:
        self.agent(owner_agent_id)
        if parent_task_id:
            self.task(parent_task_id)
        first_step = "plan"
        tid = task_id or f"task-{uuid.uuid4().hex}"
        ts = self._now()
        with self.conn:
            self.conn.execute(
                "INSERT INTO tasks (task_id, parent_task_id, owner_agent_id, type,"
                " objective, acceptance_json, status, step, max_tokens,"
                " max_cost_usd, created_at, parent_index, blocked_reason)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tid, parent_task_id, owner_agent_id, task_type, objective,
                 json.dumps(acceptance or []), "queued", first_step,
                 self.settings.max_task_tokens, self.settings.max_task_run_cost_usd,
                 ts, self._child_index(parent_task_id), None))
            self._event(self.conn, "task_created", "operator", tid,
                        owner_agent_id, None, None, "info",
                        f"task created: {objective[:80]}")
        return tid

    def _spawn_child(self, parent: Task, objective: str,
                      acceptance: list[str] | None = None,
                      task_type: str = "generic") -> str:
        """Bounded child-task creation (G2): depth, dup, recursion, budget.

        A delegator's children are always generic leaves (no delegator may
        be the child of a delegator); generic parents may spawn delegator
        children, bounded by the depth limit."""
        if parent.is_delegator and task_type == "delegation":
            raise RuntimeError(
                "recursion guard: a delegation task cannot be a child of "
                "another delegation task (delegator children are leaves)")
        parent_depth = self.depth_of(parent.task_id)
        if parent_depth + 1 > self.settings.max_delegation_depth:
            raise RuntimeError(
                f"delegation depth limit {self.settings.max_delegation_depth} "
                f"reached (parent is at depth {parent_depth})")
        norm = " ".join(objective.split()).lower()
        for sib in self._non_terminal_children(parent.task_id):
            if " ".join(sib.objective.split()).lower() == norm:
                raise RuntimeError(
                    f"duplicate task rejected: child with the same objective "
                    f"already exists under {parent.task_id} ({sib.task_id})")
        # Anti-evasion: the cap is half of the parent's REMAINING budget,
        # i.e. what the parent has not spent itself AND has not already
        # spent through previously spawned children.
        sib_tokens = sum(c.tokens_used for c in self._children(parent.task_id))
        sib_cost = sum(c.cost_usd for c in self._children(parent.task_id))
        remaining_tokens = max(0, parent.max_tokens
                               - parent.tokens_used - sib_tokens)
        child_max_tokens = max(1, remaining_tokens // 2)
        remaining_cost = max(0.0, parent.max_cost_usd
                             - parent.cost_usd - sib_cost)
        child_max_cost = remaining_cost / 2.0
        tid = self.create_task(objective, parent.owner_agent_id,
                               task_type=task_type,
                               acceptance=acceptance or parent.acceptance,
                               parent_task_id=parent.task_id)
        with self.conn:
            self.conn.execute(
                "UPDATE tasks SET max_tokens=?, max_cost_usd=? WHERE task_id=?",
                (child_max_tokens, child_max_cost, tid))
            self._event(self.conn, "child_task_spawned", "runtime", tid,
                        parent.owner_agent_id, None, None, "info",
                        f"child spawned by delegation from {parent.task_id} "
                        f"(depth={self.depth_of(tid)}, budget={child_max_tokens} "
                        f"tok / ${child_max_cost:.4f})",
                        {"parent_task_id": parent.task_id,
                         "max_tokens": child_max_tokens,
                         "max_cost_usd": child_max_cost})
        return tid

    def _wait_blocked(self, task: Task) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE tasks SET status='blocked', blocked_reason="
                "'waiting_children', error=NULL WHERE task_id=?",
                (task.task_id,))
            self._event(self.conn, "task_blocked_waiting_children", "runtime",
                        task.task_id, task.owner_agent_id, None, None, "info",
                        "delegator waiting for child tasks to finish",
                        {"pending": [c.task_id for c in
                                     self._non_terminal_children(task.task_id)]})

    def _wake_if_waiting(self, task_id: str) -> None:
        row = self.conn.execute(
            "SELECT status, blocked_reason FROM tasks WHERE task_id=?",
            (task_id,)).fetchone()
        if row and row["status"] == "blocked" and \
                row["blocked_reason"] == "waiting_children":
            with self.conn:
                self.conn.execute(
                    "UPDATE tasks SET status='queued', blocked_reason=NULL "
                    "WHERE task_id=?", (task_id,))
                self._event(self.conn, "task_woken", "runtime", task_id, None,
                            None, None, "info",
                            "waiting parent re-queued after a child finished")

    def _run_children(self, parent: Task) -> int:
        """Run this delegator's children (in order) until it can continue.

        Returns the number of children that hit a terminal state this pass.
        A paused/cancelled parent stops the pass mid-flight (D-08: the parent
        does children's work itself; concurrency is capped)."""
        finished = 0
        while True:
            row = self.conn.execute(
                "SELECT status FROM tasks WHERE task_id=?",
                (parent.task_id,)).fetchone()
            if row["status"] != "active":
                break
            pending = self._non_terminal_children(parent.task_id)
            if not pending:
                break
            child = pending[0]
            c = self.run_task(child.task_id)
            if c.status in TERMINAL:
                finished += 1
                self._wake_if_waiting(parent.task_id)
        return finished

    def task(self, task_id: str) -> Task:
        return Task.from_row(self._must(self.conn.execute(
            "SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone(),
            f"unknown task: {task_id}"))

    def tasks_by_status(self, *statuses: str) -> list[Task]:
        if not statuses:
            return []
        marks = ",".join("?" * len(statuses))
        rows = self.conn.execute(
            f"SELECT * FROM tasks WHERE status IN ({marks}) ORDER BY created_at",
            statuses).fetchall()
        return [Task.from_row(r) for r in rows]

    def event_log(self, task_id: str | None = None, limit: int = 200) -> list[sqlite3.Row]:
        if task_id:
            return self.conn.execute(
                "SELECT * FROM events WHERE task_id=? ORDER BY event_id DESC LIMIT ?",
                (task_id, limit)).fetchall()
        return self.conn.execute(
            "SELECT * FROM events ORDER BY event_id DESC LIMIT ?", (limit,)).fetchall()

    @staticmethod
    def _must(row, message: str):
        if not row:
            raise KeyError(message)
        return row

    # ---------------- step execution (idempotent) ----------------

    def _deadline_exceeded(self, task_id: str) -> bool:
        dl = self.settings.task_deadline_ms
        if dl <= 0:
            return False
        row = self.conn.execute(
            "SELECT activated_at FROM tasks WHERE task_id=?",
            (task_id,)).fetchone()
        if not row["activated_at"]:
            return False
        started = calendar.timegm(time.strptime(row["activated_at"],
                                                "%Y-%m-%dT%H:%M:%SZ"))
        return (time.time() - started) * 1000.0 > dl

    def _context_for(self, task: Task, step: str) -> tuple[list[dict], str]:
        steps = self._step_order_for(task)
        prior_idx = steps.index(step)
        refs = [f"{task.task_id}/{i}-{s}.txt"
                for i, s in enumerate(steps[:prior_idx], start=1)]
        parts = []
        for ref in refs:
            if self.artifacts.exists(ref):
                parts.append(f"--- prior {ref.split('/')[-1]} ---\n"
                             f"{self.artifacts.read(ref).content}")
        child_note = ""
        if task.is_delegator and step in ("consolidate", "verify"):
            child_sections = []
            for c in self._children(task.task_id):
                if c.status == "completed" and c.result_ref:
                    child_sections.append(
                        f"--- child {c.task_id} [{c.status}] "
                        f"objective: {c.objective} ---\n"
                        f"{self.artifacts.read(c.result_ref).content}")
                elif c.status in TERMINAL:
                    child_sections.append(
                        f"--- child {c.task_id} [{c.status}] "
                        f"objective: {c.objective} ---\n"
                        f"(no result: {c.error or c.status})")
            if child_sections:
                parts.append("===== child results =====\n" + "\n\n".join(child_sections))
                child_note = f" with {len(child_sections)} child result(s)"
        resume_note = (f"resuming from step {step!r} with "
                       f"{max(0, len(parts) - (1 if child_note else 0))} prior "
                       f"artifact(s) reused" + child_note) \
            if (parts and (parts[0].startswith("--- prior") or child_note)) else ""
        body = ("role: agent\nstep: " + step + "\nobjective: " + task.objective
                + ("  | acceptance criteria: " + "; ".join(task.acceptance)
                   if task.acceptance else "")
                + ("\n\n" + "\n\n".join(parts) if parts else ""))
        cfg_tag = f"{step}-{self.settings.reasoning_effort}"
        messages = [
            {"role": "system", "content": SYSTEM_PROMPTS[step]},
            {"role": "user", "content": body + f"\n[config:{cfg_tag}]"},
        ]
        return messages, resume_note

    def _run_step(self, task: Task, step: str) -> str:
        """Execute one cognition step. Returns the result artifact ref.

        The token accounting and the artifact reference are committed in ONE
        transaction (per spend). A crash after commit -> the resume reuses the
        result. A crash mid-step -> the (uncommitted) accounting is gone, so
        cost is never double-counted on re-run.
        """
        ref = self._step_artifact_ref(task, step)
        if self.artifacts.exists(ref):
            # Idempotent reuse. If the task row still points at this step,
            # the prior run crashed BETWEEN the artifact write and the commit:
            # advance the step + log the reuse, but do NOT re-charge tokens.
            with self.conn:
                row = self.conn.execute(
                    "SELECT status, step FROM tasks WHERE task_id=?",
                    (task.task_id,)).fetchone()
                if row["status"] in TERMINAL:
                    raise RuntimeError(f"task {task.task_id} is terminal; step rejected")
                if row["step"] == step:
                    self._event(self.conn, "step_reused", "runtime",
                                task.task_id, task.owner_agent_id, None, None,
                                "info",
                                f"step {step!r} completed before a crash; reusing "
                                "artifact without double-charging",
                                {"ref": ref})
                    self.conn.execute(
                        "UPDATE tasks SET step=? WHERE task_id=?",
                        (self._next_step_after(task, step), task.task_id))
            return ref

        if self._deadline_exceeded(task.task_id):
            raise _TimedOut("task deadline exceeded")

        messages, resume_note = self._context_for(task, step)
        call = ModelCall(call_id=f"{task.task_id}:{step}",
                         task_id=task.task_id, purpose=step,
                         messages=messages,
                         effort=self.settings.reasoning_effort)
        self._event(self.conn, "step_started", "runtime", task.task_id,
                    task.owner_agent_id, None, None, "info",
                    f"step {step} started" + (f" ({resume_note})" if resume_note else ""),
                    {"model": self.model_name})
        try:
            result = self.model.call(call)
        except ModelError as e:
            self.conn.commit()  # persist the failure event
            raise

        usage = result.usage
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        total = prompt_tokens + completion_tokens
        if isinstance(self.model, LiveOpenAIModel):
            cost_delta = (prompt_tokens * self.model.in_cost
                          + completion_tokens * self.model.out_cost) / 1_000_000
        else:
            cost_delta = 0.0
        artifact_name = ref.split("/", 1)[1]

        over = False
        used = 0.0
        with self.conn:  # single transaction: budget check + step commit
            row = self.conn.execute(
                "SELECT tokens_used, cost_usd, status FROM tasks WHERE task_id=?",
                (task.task_id,)).fetchone()
            if row["status"] in TERMINAL:
                raise RuntimeError(f"task {task.task_id} is terminal; step rejected")
            used = row["tokens_used"]
            if used + total > task.max_tokens:
                over = True  # handle after the transaction commits the spend
        # The model WAS invoked, so its call + spend are recorded on disk
        # regardless of whether the step's artifact is kept (honest cost for
        # the budget-killer step, but no artifact from an over-budget run).
        with self.conn:
            self._event(self.conn, "model_call_completed", "runtime",
                        task.task_id, task.owner_agent_id, None, None, "info",
                        ("step " + step + " done: " + str(total)
                         + " tokens, " + str(result.latency_ms)
                         + "ms" + (" (over budget)" if over else "")),
                        {"artifact": None if over else ref,
                         "prompt_tokens": prompt_tokens,
                         "completion_tokens": completion_tokens,
                         "latency_ms": result.latency_ms,
                         "config_version": result.config_version})
            self.conn.execute(
                "UPDATE tasks SET tokens_used=?, cost_usd=ROUND(cost_usd+?, 9)"
                " WHERE task_id=?",
                (used + total, cost_delta, task.task_id))
        if over:
            raise _BudgetExceeded(
                f"token budget {task.max_tokens} exceeded "
                f"({used} used + {total} this step)")
        with self.conn:
            self.artifacts.write(task.task_id, artifact_name, result.text)
            self.conn.execute(
                "UPDATE tasks SET step=? WHERE task_id=?",
                (self._next_step_after(task, step), task.task_id))
        return ref

    @staticmethod
    def _next_step_after(task: Task, step: str) -> str | None:
        steps = DELEGATION_STEPS if task.is_delegator else STEP_ORDER
        i = steps.index(step)
        return steps[i + 1] if i + 1 < len(steps) else None

    # ---------------- task state machine ----------------

    def activate(self, task_id: str) -> None:
        with self.conn:
            row = self.conn.execute(
                "SELECT status, blocked_reason FROM tasks WHERE task_id=?",
                (task_id,)).fetchone()
            if row["status"] != "queued" or row["blocked_reason"]:
                raise RuntimeError(
                    f"cannot activate task in status {row['status']} "
                    f"(reason={row['blocked_reason']})")
            self.conn.execute(
                "UPDATE tasks SET status='active', activated_at=? WHERE task_id=?",
                (self._now(), task_id))
            self._event(self.conn, "task_activated", "runtime", task_id, None,
                        None, None, "info", "task activated")

    def _pause_blocked(self, conn: sqlite3.Connection, task_id: str) -> None:
        conn.execute(
            "UPDATE tasks SET status='blocked', error='paused by operator', "
            "blocked_reason=NULL WHERE task_id=? AND status IN ('queued','active')",
            (task_id,))

    def pause(self, task_id: str) -> None:
        with self.conn:
            row = self.conn.execute(
                "SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row["status"] not in {"queued", "active"}:
                raise RuntimeError(f"cannot pause task in status {row['status']}")
            self._pause_blocked(self.conn, task_id)
            self._event(self.conn, "task_paused", "operator", task_id, None,
                        None, None, "warning", "task paused by operator")

    def resume(self, task_id: str) -> None:
        with self.conn:
            row = self.conn.execute(
                "SELECT status, error FROM tasks WHERE task_id=?",
                (task_id,)).fetchone()
            if row["status"] != "blocked" or "paused" not in (row["error"] or ""):
                raise RuntimeError(f"task not paused (status={row['status']})")
            self.conn.execute(
                "UPDATE tasks SET status='active', error=NULL, "
                "blocked_reason=NULL WHERE task_id=?", (task_id,))
            self._event(self.conn, "task_resumed", "operator", task_id, None,
                        None, None, "info", "task resumed by operator")

    def _cancel_tree(self, conn: sqlite3.Connection, task_id: str) -> list[str]:
        """Cancel this task and all non-terminal descendants. Returns ids."""
        done: list[str] = []

        def visit(tid: str) -> None:
            row = conn.execute(
                "SELECT status FROM tasks WHERE task_id=?", (tid,)).fetchone()
            if row["status"] in TERMINAL:
                return
            conn.execute(
                "UPDATE tasks SET status='cancelled', finished_at=?, "
                "error='cancelled by operator' WHERE task_id=?",
                (self._now(), tid))
            done.append(tid)
            for r in conn.execute(
                    "SELECT task_id FROM tasks WHERE parent_task_id=?",
                    (tid,)).fetchall():
                visit(r["task_id"])

        visit(task_id)
        return done

    def cancel(self, task_id: str) -> None:
        with self.conn:
            row = self.conn.execute(
                "SELECT status FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if row["status"] in TERMINAL:
                raise RuntimeError(f"task already terminal: {row['status']}")
            cancelled = self._cancel_tree(self.conn, task_id)
            for tid in cancelled:
                self._event(self.conn, "task_cancelled", "operator", tid, None,
                            None, None, "warning",
                            "task cancelled by operator"
                            + ("" if tid == task_id else " (propagated)"))

    def _roll_up_spend(self, task_id: str) -> None:
        """Add a child's recorded spend to its parent's counters.

        Called once, inside the child's terminal transaction (complete,
        fail, or time-out), so the parent's budget envelope covers the
        WHOLE tree: the parent's guard accounts for what its children
        have already spent, and rows stay reconcilable with the event
        journal (parent.tokens_used == own + sum(children))."""
        row = self.conn.execute(
            "SELECT parent_task_id, tokens_used, cost_usd FROM tasks "
            "WHERE task_id=?", (task_id,)).fetchone()
        if row and row["parent_task_id"]:
            self.conn.execute(
                "UPDATE tasks SET tokens_used = tokens_used + ?, "
                "cost_usd = ROUND(cost_usd + ?, 9) WHERE task_id=?",
                (row["tokens_used"], row["cost_usd"],
                 row["parent_task_id"]))

    def _fail(self, task_id: str, message: str, severity: str = "error",
              status: str = "failed") -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE tasks SET status=?, finished_at=?, error=?, "
                "blocked_reason=NULL WHERE task_id=?",
                (status, self._now(), message, task_id))
            self._event(self.conn,
                        "task_timed_out" if status == "timed_out" else "task_failed",
                        "runtime", task_id, None, None, None, severity, message)
            self._roll_up_spend(task_id)

    def _complete(self, task_id: str, result_ref: str) -> None:
        with self.conn:
            self.conn.execute(
                "UPDATE tasks SET status='completed', finished_at=?, step=NULL, "
                "result_ref=?, blocked_reason=NULL WHERE task_id=?",
                (self._now(), result_ref, task_id))
            self._event(self.conn, "task_completed", "runtime", task_id, None,
                        None, None, "info", "task completed", {"result": result_ref})
            self._roll_up_spend(task_id)
        parent_id = self.conn.execute(
            "SELECT parent_task_id FROM tasks WHERE task_id=?",
            (task_id,)).fetchone()["parent_task_id"]
        if parent_id:
            self._wake_if_waiting(parent_id)

    def run_task(self, task_id: str) -> Task:
        """Advance a task to a terminal (or paused/blocked-waiting) state.

        A delegator, once past plan and before consolidate finishes, runs its
        own children; if any remain after this pass it parks itself as
        blocked(waiting_children) so the operator can see the dependency."""
        task = self.task(task_id)
        if task.status == "queued" and not task.blocked_reason:
            self.activate(task_id)
            task = self.task(task_id)
        if task.status == "blocked" and task.blocked_reason == "waiting_children":
            with self.conn:
                self.conn.execute(
                    "UPDATE tasks SET status='active', blocked_reason=NULL, "
                    "activated_at=? WHERE task_id=?", (self._now(), task_id))
                self._event(self.conn, "task_woken", "runtime", task_id, None,
                            None, None, "info",
                            "waiting delegator activated to run remaining "
                            "children")
            task = self.task(task_id)
        if task.status != "active":
            return task
        steps = self._step_order_for(task)
        step = task.step or steps[0]
        try:
            while step is not None:
                if self.task(task_id).status != "active":  # paused mid-run
                    return self.task(task_id)
                if self._deadline_exceeded(task_id):
                    self._fail(task_id, "task deadline exceeded", "warning",
                               status="timed_out")
                    return self.task(task_id)
                if (task.is_delegator and step == "consolidate"
                        and self._non_terminal_children(task_id)):
                    self._run_children(task)
                    if self._non_terminal_children(task_id):
                        # A child could not finish this pass (e.g. operator
                        # paused it mid-flight) -> park visibly.
                        self._wait_blocked(task)
                        return self.task(task_id)
                    # All children now terminal: fall through and consolidate
                    # using their on-disk results.
                self._run_step(task, step)
                self._event(self.conn, "artifact_written", "runtime", task_id,
                            task.owner_agent_id, None, None, "info",
                            f"step artifact for {step!r}",
                            {"ref": self._step_artifact_ref(task, step)})
                self.conn.commit()
                task = self.task(task_id)
                step = task.step
            self._complete(task_id,
                           self._step_artifact_ref(task, steps[-1]))
        except _BudgetExceeded as e:
            self._fail(task_id, f"budget exhausted: {e}")
        except _TimedOut as e:
            self._fail(task_id, f"deadline exceeded: {e}", "warning",
                       status="timed_out")
        except ModelError as e:
            self._fail(task_id, f"model error (not retryable inline): {e}")
        return self.task(task_id)

    def spawn_children(self, task_id: str, specs: list[dict]) -> list[str]:
        """API to define child tasks (operator or Phase 4).

        specs: [{"objective": ..., "acceptance": [...]?,
                 "task_type": "generic" | "delegation"?}, ...]
        Enforces the delegation bounds (depth, duplicate, budget, recursion):
        a delegator's children are generic leaves; a generic parent may
        delegate (bounded by the depth limit)."""
        parent = self.task(task_id)
        ids = [self._spawn_child(parent, s["objective"], s.get("acceptance"),
                                 s.get("task_type", "generic"))
               for s in specs]
        return ids

    def recover(self) -> list[str]:
        """After a restart: re-queue tasks still marked 'active'.

        Blocked (paused / waiting_children) tasks stay parked: paused needs an
        operator resume; waiting_children re-activates itself on the next
        run_task (after running its children)."""
        rows = self.conn.execute(
            "SELECT task_id, step FROM tasks WHERE status='active'").fetchall()
        ids = []
        for r in rows:
            with self.conn:
                self.conn.execute(
                    "UPDATE tasks SET status='queued' WHERE task_id=?",
                    (r["task_id"],))
                self._event(self.conn, "recovery_reactivated", "runtime",
                            r["task_id"], None, None, None, "warning",
                            f"in-flight task found after restart "
                            f"(step={r['step']}); re-queued for resume")
            ids.append(r["task_id"])
        return ids

    def close(self) -> None:
        self.conn.close()
