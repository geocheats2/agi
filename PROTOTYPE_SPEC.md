# PROTOTYPE_SPEC

Concrete spec for the **smallest meaningful society** (charter §18).
Deliberately smaller than the vision. It answers one research question and is
the thing the Phase 1–4 milestones actually build.

## 1. Roles (functional, may overlap — not a permanent hierarchy)
| Role | Count | Remit |
|---|---|---|
| Foreman / coordinator | 1 | Frames the question, sets acceptance criteria, delegates bounded tasks, synthesizes the collective statement, owns the decision record. |
| Specialist agents | 2 | e.g. **Investigator** (localize evidence/reproduce) and **Analyst** (interpret, weigh alternatives). Independent remits; may be the same model with different prompts, evidence, and method (R-02/R-12). |
| Adversarial reviewer / challenger | 1 | Invoked *selectively* on material claims; checks for correlated evidence and logical gaps. |

Do **not** pre-assume the best role arrangement — the benchmark measures it.

## 2. Workflow (one bounded run)
1. **Frame** — Foreman: objective + acceptance criteria + budget.
2. **Independent first pass** — each Specialist answers important parts in
   *blind* mode (no peer answers). (F-12)
3. **Debate** — Foreman identifies information gaps; delegates bounded
   subtasks (depth/budget-limited, F-4/F-5).
4. **Integrate** — results carry source provenance + limitations (F-8).
5. **Challenge** — Reviewer attacks material claims; flags correlated
   evidence (H-3/H-5).
6. **Revise** — Specialists may update claims; revision appended (F-9).
7. **Synthesize** — Foreman emits the Collective Statement, preserving
   unresolved disagreements (F-13/F-14).
8. **Audit** — full event log + cost/latency/quality recorded.

## 3. Data model (SQLite; JSON-schema mirrored in `schemas/`)

**Agent** `{ agent_id, role, model, config_version, constitution_version,
  created_at, state_json }`.
`state_json` includes: current beliefs, open subtasks, budget_used, last_heartbeat.

**Task** `{ task_id, parent_task_id (nullable), type, objective, inputs,
  acceptance_criteria, budget_tokens, deadline, max_depth, depth, owner_agent_id,
  status, started_at, finished_at, outcome }`.
`status ∈ {queued, active, blocked, completed, failed, cancelled, timed_out}`.

**Event** (append-only) `{ event_id, ts, type, actor, task_id, agent_id,
  prior_state_version, resulting_state_version, artifact_refs, severity,
  authorization, error_or_outcome }`.

**Claim** `{ claim_id, proposition, scope, epistemic_type, evidence_ids[],
  supporting[], opposing[], assumptions[], dependencies[], confidence_semantics,
  confidence_estimate (nullable), status, revision_history[], author, reviewer,
  decision_relevance }`.

**Evidence** `{ evidence_id, content_type, location, originating_tool_or_agent,
  source, captured_at, integrity_md5, task_refs, claim_refs, trust_status,
  access_policy, version, superseded_by }`.

**Decision** `{ decision_id, question, alternatives[], decision_class,
  authority, constitution_version, criteria[], constraint_refs[],
  evidence_refs[], uncertainty, dissent[], chosen, rationale, approver,
  ts, reversibility, revisit_trigger, followups[] }`.

**Collective statement** — the §23.5 schema, verbatim:
```yaml
statement:
  id: "statement-id"
  question: "Question being answered"
  scope: "What the conclusion does and does not cover"
  conclusion: "Current best-supported conclusion"
  status: "provisional | reviewed | approved | superseded"
  confidence: { meaning: "defined scale", estimate: null, limitations: [] }
  established_findings: []
  assumptions: []
  evidence_for: []
  evidence_against: []
  alternative_explanations: []
  unresolved_disagreements: []
  correlated_evidence_warnings: []
  decision_implications: []
  recommended_next_action: ""
  authorization_required: true
  falsification_or_revision_conditions: []
  supporting_artifacts: []
  constitution_version: "version"
  created_at: "timestamp"
```

## 4. Bounded-autonomy rules (enforced by the runtime, not prompt)
- Max delegation depth: **2** (foreman → specialist → reviewer). Depth-3 is
  a *proposal*, blocked by default (R-05).
- Max concurrent tasks: **1** (D-08).
- Per-task token budget: from `CSA_MAX_TASK_TOKENS`.
- Per-run $ budget: from `CSA_MAX_TASK_RUN_COST_USD`.
- **Any** action beyond read-only-local → *proposed*, not executed (D-07).
- Emergency cancel via CLI works on a running task (F-20).

## 5. What is intentionally omitted (charter §18.4, ARCHITECTURE)
- No web UI; no broker/graph DB/vector store; no model fine-tuning;
  no multi-model routing; no self-modification of enforcement; no external
  side effects. These are added in Ph5–8 *only if* earlier phases prove value.

## 6. Exit criteria for the prototype (mirrors charter §18.4)
- [ ] Durable recovery (kill-and-restart clean).
- [ ] Bounded delegation under limits (no recursion escape).
- [ ] Source-linked claims (provenance inspectable).
- [ ] Explicit uncertainty in the statement.
- [ ] Material dissent preserved (minority-correct case).
- [ ] Human pause/cancel/redirect works during live work.
- [ ] Reliable audit history (event log reconstructs the run).
- [ ] **Baseline comparison** (B1/B2 vs B4) on the anchor benchmark.
- [ ] Measured coordination overhead (B4 vs B2 cost/latency).
- [ ] Honest report of failures + limitations (implemented vs unverified).

## 7. Acceptance
The prototype is **accepted** when the benchmark harness produces a
reproducible, JSON-serialized metrics run for all arms (B1, B2, B4) on the
anchor task, and the collective statement passes a schema + content audit
(dissent preserved, evidence linked, confidence is a *defined* scale not a
made-up number). The owner reviews the report and decides: proceed to Ph5,
simplify, or stop.
