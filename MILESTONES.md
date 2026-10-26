# MILESTONES

Staged delivery plan (charter §17). **Phase 0 (planning — this artifact set)
is complete.** Each phase has *testable* exit criteria: a phase is done when
its tests/artifacts pass, not when an agent says it's done (charter §0.2,
§19.4). Nothing is implemented "all at once."

> **Gate:** the first *code* milestone (Phase 1) starts only after the owner
> approves `ARCHITECTURE_OPTIONS.md` (D-04), the stack (D-05/D-07/D-08), and
> the anchor benchmark below. Schemas/state can begin earlier if desired.

## Phase 0 — Clarify & establish baseline  ✅ (this deliverable)
Status: **Complete — owner approved direction ("Yes, move forward", 2026-10-25 20:57).**
Exit criteria (met):
- [x] Requirements normalized (REQUIREMENTS.md), separated commitments /
  hypotheses / non-goals.
- [x] Three+ architecture options compared + recommendation (ARCHITECTURE_OPTIONS).
- [x] Decision log, risk register, assumptions & questions, research plan.
- [x] Staged plan with testable exit criteria (this file).
- [x] Smallest prototype recommended (PROTOTYPE_SPEC.md) — deliberately < vision.
- [x] **Owner approves initial direction.** (2026-10-25)

## Phase 1 — Durable task & agent state   ✅ **Complete (2026-10-25)**
Prove tasks + agent identities persist across failures (G1, G9).
Work: agent/task/event/artifact/decision schemas → SQLite; durable task
state machine; bounded model call (adapter + idempotency); persist plan/
checkpoint/output/error; restart recovery; basic status inspection (CLI).
Exit criteria (must pass) — **all met, 2026-10-25, 15/15 tests green**:
- [x] A task survives a mid-task process kill and resumes to a correct,
  auditable end state. (`tests/recovery/test_recovery.py::test_task_survives_kill_and_resumes`)
- [x] Duplicate execution is controlled (idempotency) — verified by a
  fault-injection test. (`test_step_reruns_are_idempotent`,
  `test_completed_task_is_not_rerun`; call idempotency key `task:step`)
- [x] Event history is append-only and queryable (reconstructs the task).
  (`test_event_log_is_append_only`; happy path test reconstructs task from events)
- [x] `.env`-based secret works; key never appears in state/logs (test asserts).
  (`test_api_key_never_leaks_into_state` — S-1 scan over events, tasks, artifacts)
- [x] No claim of "persistent cognition" beyond demonstrated recovery.
  (CONSTITUTION.md v0.1.0 "What is NOT yet true" section)
Deliverables: `schemas/` JSON + SQL, `src/` runtime core, `tests/recovery/`,
`.env.example`, updated `CONSTITUTION.md` v0 (thin).

## Phase 2 — Bounded delegation (G2)
Work: task contracts; child-task creation; enforce depth/concurrency/deadline/
budget; dependency tracking + ownership; parent validates child output;
cancellation propagation + deadlock/recursion detection.
Exit criteria:
- [ ] A multi-level task completes **under limits** (depth & budget).
- [ ] Recursion / budget-evasion / duplicate-task tests pass.
- [ ] Parent checks child output against acceptance criteria (not trust).
- [ ] Single-agent baseline (Option D) comparison exists for the same task.

## Phase 3 — Evidence & shared knowledge (G4/G5)
Work: evidence + artifact registry; structured claim records; source
provenance; conflict + revision tracking; searchable shared workspace;
retrieval evaluation.
Exit criteria:
- [ ] Material claims link to ≥1 evidence item; provenance is inspectable.
- [ ] Conflicting claims coexist; a correction appends, never overwrites.
- [ ] Source-correlation (shared-origin) is flagged.
- [ ] Retrieval has measurable tests.

## Phase 4 — Independent assessment & deliberation (G4/G5)
Work: blind first-pass mode; structured evidence exchange; disagreement
classification; targeted challenge; dissent-preserving synthesis; decision
record + later outcome tracking.
Exit criteria:
- [ ] Known-conflict / minority-correct test cases pass at an agreed level.
- [ ] Collective statement distinguishes facts / assumptions / recommendations /
    dissent (schema fields populated, verified).
- [ ] Performance compared vs. simpler baselines (Option D; no-first-pass ablation).
- [ ] Cost + latency overhead measured and reported.

## Phase 5 — Constitution & policy enforcement (G7)
Work: versioned constitution; policy evaluation layer; scoped tool permissions;
approval gates; resource enforcement; amendment workflow; independent emergency
stop; adversarial prompt-injection + privilege tests.
Exit criteria:
- [ ] A prohibited action is blocked **by the runtime** (not prompt) + logged.
- [ ] Constitution version attached to tasks + decisions; retrieval is exact.
- [ ] Amendment workflow is tested; a worker cannot change foundational rules.
- [ ] Emergency/budget stop works without the stopped agent's cooperation.

## Phase 6 — Human control interface (G3)
Work: society overview; agent detail; task graph; disagreement/evidence browser;
approval queue; pause/cancel/reassign/budget controls; event + performance views.
*(CLI → may graduate to a web UI here if usability tests demand it.)*
Exit criteria:
- [ ] Operator locates active work + blockers in a bounded number of steps.
- [ ] Operator actions have clean, logged state transitions.
- [ ] Controls tested *during live work* (pause a running task; verify response).
- [ ] High-impact ops show authorization status; usability feedback incorporated.

## Phase 7 — Outcome-based learning (G6)
Work: structured experience records; predictions + outcomes; task-specific
capability profiles; routing experiments; process-change proposals; regression
+ rollback.
Exit criteria:
- [ ] ≥1 change shown to improve a held-out eval **or is rejected**; regressions
    detectable; capability estimates carry uncertainty.
- [ ] No agent can unilaterally weaken core enforcement (tested).

## Phase 8 — Hardening & scale (G9, G10)
Work: fault injection; load/concurrency; security review; backup/restore; cost
optimization; provider/model change handling; retention/privacy review;
deploy + upgrade procedure; runbooks.
Exit criteria:
- [ ] Recovery + safety tests pass; operational cost understood.
- [ ] Deploy + rollback repeatable; residual limitations documented.
- [ ] **Owner** approves any expansion of autonomy before enabling it.

## Sequencing + go/no-go
Phases are mostly serial because each is a prerequisite of the next and the
*value* of the richer layers can only be measured once the layers below are
proven. **Go/no-go after each phase** (EVALUATION_PLAN §Gates): if the
evidence shows a deeper layer adds no measurable value over the simpler design,
we stop and prefer the simpler one (charter §18.4, §12.4).
