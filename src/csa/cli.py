"""csa - operator control surface for the Constitutional Society runtime.

Phase 1 commands: backend, agents, agent, tasks, task, new, run, result,
events, pause, resume, cancel. (No web UI; owner chose CLI - D-06.)
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import load_settings
from .runtime import Runtime


def _print_json(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_backend(rt: Runtime, _args) -> int:
    _print_json({
        "backend": rt.settings.backend,
        "model": rt.model_name,
        "reasoning_effort": rt.settings.reasoning_effort,
        "db": str(rt.settings.db_path),
        "artifacts": str(rt.settings.artifacts_root),
        "note": ("offline deterministic model" if rt.settings.backend == "fake"
                 else "live endpoint"),
    })
    return 0


def cmd_agents(rt: Runtime, args) -> int:
    rows = rt.conn.execute("SELECT * FROM agents ORDER BY created_at").fetchall()
    _print_json([{"agent_id": r["agent_id"], "role": r["role"],
                  "model": r["model_name"],
                  "constitution_version": r["constitution_version"]} for r in rows])
    return 0


def cmd_agent(rt: Runtime, args) -> int:
    row = rt.agent(args.agent_id)
    _print_json({"agent_id": row["agent_id"], "role": row["role"],
                 "model": row["model_name"], "state": json.loads(row["state_json"]),
                 "constitution_version": row["constitution_version"],
                 "created_at": row["created_at"]})
    for t in rt.conn.execute(
            "SELECT task_id, objective, status, step, tokens_used, cost_usd"
            " FROM tasks WHERE owner_agent_id=? ORDER BY created_at",
            (args.agent_id,)).fetchall():
        print(f"  task {t['task_id']}: [{t['status']}] {t['objective'][:60]}")
    return 0


def cmd_tasks(rt: Runtime, _args) -> int:
    rows = rt.conn.execute(
        "SELECT task_id, objective, status, step, tokens_used, cost_usd, error"
        " FROM tasks ORDER BY created_at").fetchall()
    _print_json([{"task_id": r["task_id"], "objective": r["objective"],
                  "status": r["status"], "step": r["step"],
                  "tokens_used": r["tokens_used"], "cost_usd": r["cost_usd"],
                  "error": r["error"]} for r in rows])
    return 0


def cmd_task(rt: Runtime, args) -> int:
    _print_json(rt.task(args.task_id).to_payload())
    return 0


def cmd_new(rt: Runtime, args) -> int:
    aid = args.agent or _first_agent(rt)
    if not aid:
        print("no agents yet; run: csa agents --create", file=sys.stderr)
        return 1
    acceptance = args.acceptance or None
    tid = rt.create_task(args.objective, aid,
                         acceptance=acceptance,
                         parent_task_id=args.parent)
    print(tid)
    return 0


def _first_agent(rt: Runtime) -> str | None:
    row = rt.conn.execute("SELECT agent_id FROM agents ORDER BY created_at").fetchone()
    return row["agent_id"] if row else None


def cmd_run(rt: Runtime, args) -> int:
    recovered = rt.recover()
    if recovered:
        _print_json({"recovered_tasks": recovered})
    for tid in args.task_ids:
        task = rt.run_task(tid)
        _print_json(task.to_payload())
    return 0 if all(rt.task(t).status in {"completed", "cancelled", "failed"}
                    for t in args.task_ids) else 1


def cmd_result(rt: Runtime, args) -> int:
    t = rt.task(args.task_id)
    if not t.result_ref:
        print(f"task {args.task_id} has no result (status={t.status})",
              file=sys.stderr)
        return 1
    print(rt.artifacts.read(t.result_ref).content)
    return 0


def cmd_events(rt: Runtime, args) -> int:
    rows = rt.event_log(args.task, args.limit)
    for r in reversed(rows):
        print(f"[{r['event_id']:>5}] {r['ts']}  {r['severity']:<7} "
              f"{r['type']:<22} {r['summary'][:90]}")
    return 0


def _control(rt: Runtime, args, op: str) -> int:
    try:
        getattr(rt, op)(args.task_id)
    except (KeyError, RuntimeError) as e:
        print(str(e), file=sys.stderr)
        return 1
    _print_json(rt.task(args.task_id).to_payload())
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="csa",
                                description="Constitutional Society of Agents")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("backend", help="show active model backend")
    s = sub.add_parser("agents", help="list agents")
    s.add_argument("--create", action="store_true",
                   help="create the default prototype roles")
    sub.add_parser("agent", help="agent detail").add_argument("agent_id")
    sub.add_parser("tasks", help="list tasks")
    sub.add_parser("task", help="task detail").add_argument("task_id")
    s = sub.add_parser("new", help="create a task")
    s.add_argument("objective")
    s.add_argument("--agent")
    s.add_argument("--acceptance", action="append",
                   help="acceptance criterion (repeatable)")
    s.add_argument("--parent")
    s = sub.add_parser("run", help="run tasks to completion (recovers first)")
    s.add_argument("task_ids", nargs="+")
    sub.add_parser("result", help="print a task's result artifact").add_argument("task_id")
    s = sub.add_parser("events", help="event history")
    s.add_argument("--task")
    s.add_argument("-n", "--limit", type=int, default=20)
    for op in ("pause", "resume", "cancel"):
        s = sub.add_parser(op, help=f"{op} a task")
        s.add_argument("task_id")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    rt = Runtime(settings)
    try:
        if args.cmd == "backend":
            return cmd_backend(rt, args)
        if args.cmd == "agents":
            if args.create:
                for role in ("foreman", "investigator", "analyst", "challenger"):
                    if not rt.conn.execute(
                            "SELECT 1 FROM agents WHERE role=?", (role,)).fetchone():
                        print(f"{rt.create_agent(role)}  ({role})")
            return cmd_agents(rt, args)
        if args.cmd == "agent":
            return cmd_agent(rt, args)
        if args.cmd == "tasks":
            return cmd_tasks(rt, args)
        if args.cmd == "task":
            return cmd_task(rt, args)
        if args.cmd == "new":
            return cmd_new(rt, args)
        if args.cmd == "run":
            return cmd_run(rt, args)
        if args.cmd == "result":
            return cmd_result(rt, args)
        if args.cmd == "events":
            return cmd_events(rt, args)
        if args.cmd in ("pause", "resume", "cancel"):
            return _control(rt, args, args.cmd)
        return 2
    finally:
        rt.close()


if __name__ == "__main__":
    raise SystemExit(main())
