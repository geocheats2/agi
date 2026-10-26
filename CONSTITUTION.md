# CSA Constitution (thin)

**Version**: v0.1.0
**Status**: v0 — normative statement of intent, NOT yet runtime-enforced.
Enforcement (policy evaluation layer, scoped permissions, approval gates)
arrives in **Phase 5** (MILESTONES.md). Until then these rules are
*demonstrated where possible* and *documented where not*; tasks and agents
carry `constitution_version` so every record is attributable to this text.

## Article 1 — Truthfulness (no over-claiming)

1.1 Every reported capability must be backed by a passing test or a logged
     run. "Persistent cognition", "independent agent", and similar claims are
     permitted only for behavior actually demonstrated (§0.2, §26).
1.2 Model outputs are evidence, not truth. The runtime must be able to
     distinguish model-generated text from system state, and must not record
     unverified model claims as fact (Phase 3 claims registry).

## Article 2 — Accountability (auditability)

2.1 All durable state changes are recorded as append-only events
    (schema: `schemas/event.schema.json`). Events are never edited or
    deleted; corrections are new events.
2.2 Any task's full history must be reconstructable from the event stream
    alone (verified by tests, Phase 1 exit criteria).
2.3 Every record that depends on policy carries the constitution and
    config version in force at the time (task.agent references;
    `config_version` per model call).

## Article 3 — Human Control (bounded autonomy)

3.1 A human operator can pause, cancel, or inspect any task at any time,
    without the cooperation of the agent performing it (CLI: `pause`,
    `cancel`, `task`). This is tested, Phase 1.
3.2 Autonomy is granted in phases. No capability is enabled before its
    phase exit criteria pass, and the owner approves expansion (Phase 8).
3.3 Budgets (tokens, cost) are hard limits enforced by the runtime, not
    by the model (tested, Phase 1: over-budget work fails cleanly).

## Article 4 — Independence (guarded, not assumed)

4.1 Multiple agents over the same model are *correlated*, not independent
    (RISK R-02/R-12). Findings of "the society" must not be presented as
    independent evidence unless independence was actually established.
4.2 Baseline comparison against a single-agent system (Option D) is
    mandatory before claiming that the multi-agent structure adds value
    (EVALUATION_PLAN.md gates).

## Article 5 — Safety (fail closed)

5.1 On crash, resume, or ambiguity the runtime fails toward NO action, no
    double spend, and no lost history. Recovery re-runs are idempotent
    (call idempotency keys; artifact reuse without double-charging).
5.2 If a model call fails non-retryably, the task fails cleanly and
    auditable; it does not silently retry unbounded.
5.3 Secrets (API keys, credentials) come from the environment/.env only
    and MUST NEVER appear in state, logs, artifacts, or events
    (tested, Phase 1).

## Amendment process (v0)

- Amendments are versioned edits to this file (vX.Y.Z) + an entry in
  `DECISION_LOG.md` with rationale and owner approval.
- A worker agent cannot amend this document; only the owner or a
  delegated human operator may. (Enforced by file access now; by runtime
  policy in Phase 5.)

## What is NOT yet true (honesty section)

- No policy layer is enforced by the runtime yet (Phase 5).
- No delegation exists yet (Phase 2) — tasks are single-agent today.
- No shared knowledge / claims registry yet (Phase 3).
- "Society" currently means: a durable task runtime + durable agent
  identities, proven to survive crashes. That is all.
