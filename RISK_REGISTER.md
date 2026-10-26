# RISK_REGISTER

Live register (charter §20). Fields: ID, risk, severity (S), likelihood (L),
current mitigations, residual risk, owner, review trigger.
S/L scale: Low / Medium / High. **Score = S × L** (High×High = critical).

## Prototype-phase risks (active now)

- **R-01 Groupthink / premature convergence.** S:Med L:Med.
  Mitigate: blind first-pass (F-12), provenance, targeted dissent, retained
  revision history (F-9). Residual: Med. Owner: Foreman. Trigger: if initial
  assessments correlate > expected with no information exchange.

- **R-02 Correlated model errors (AMPLIFIED — single model).** S:High L:High.
  *All agents share `Qwen-27B`; different prompts ≠ independence.*
  Mitigate: vary evidence & method per role; explicitly model "correlated
  source" not as corroboration (F-10); a known-correlated-error test case;
  **plan an honest report** that true epistemic independence is limited to a
  single model. Residual: High. Owner: Foreman + Owner.
  Trigger: **H-3** outcome — if no agent catches a known-wrong answer, this
  must be reported plainly, and we reconsider a second model for the
  challenger role (see D-01 revisit).

- **R-03 Consensus mistaken for truth.** S:Med L:Med.
  Mitigate: evidence-linked claims, explicit decision rules, preserved
  minority reports (F-13/F-14). Residual: Med → Low after E-3 tests.

- **R-04 Objective misspecification / gaming metrics.** S:Med L:Med.
  Mitigate: objective + human-evaluated + adversarial tests; multi-metric
  (E-1–E-5); inspect examples. Residual: Med.

- **R-05 Delegation explosion.** S:Med L:Low (bounded by D-08 = 1, hard limits
  in F-5). Mitigate: runtime-enforced depth/concurrency/deadline/budget;
  duplicate detection. Residual: Low. Trigger: recursion/budget-evasion tests.

- **R-06 Stale/contaminated memory.** S:Med L:Med (prototype memory is small,
  but the schema sets the pattern). Mitigate: provenance, temporal validity,
  scope labels, retrieval tests. Residual: Med.

- **R-07 Prompt injection / instruction laundering from untrusted content.**
  S:High L:Low (prototype corpus is local/owned, but the pattern must be
  correct from day one). Mitigate: treat tool/retrieved content as data (S-2);
  least-privilege tool surface; an adversarial test that embeds a malicious
  instruction in a corpus doc; enforce constraints in the runtime (F-17), not
  prompt. Residual: Med. Owner: Foreman.

- **R-08 Self-confirmation / self-evaluation as ground truth.** S:Med L:Med.
  Mitigate: independent + objective tests; an evaluator distinct from the
  proposing agent; outcome-based metrics (F-24, E-4). Residual: Med.

- **R-09 Human overload (too many events/approvals).** S:Low L:Low
  (prototype is small + CLI). Mitigate: prioritized output; batch low-risk.
  Residual: Low.

- **R-10 Hidden external side effects from retries/ambiguous status.**
  S:High L:Low (no external actions — D-07). Mitigate: idempotency keys for
  local writes; action IDs; explicit proposed/queued/executing/verified
  states (F-22). Residual: Low.

- **R-11 Overly elaborate constitutional bureaucracy.** S:Med L:Med.
  *Risk: governance ritual slows trivial tasks without safety gain.*
  Mitigate: risk-tiered procedures; measure approval overhead; keep rules
  testable; simplify where evidence says so. This is a **core** guardrail for
  the society to stay practical. Residual: Med. Owner: Owner (values call).

- **R-12 False independence (role names ≠ real expertise).** S:Med L:High
  (single model — different "specialists" share assumptions).
  Mitigate: measure correlation; vary evidence/method; compare vs. Option D
  baseline. Residual: High. **Report honestly** if "specialists" are not
  functionally different from one agent (see D-04/H-7 revisit: prefer simpler).

- **R-19 Benchmark overfitting.** S:Med L:Med. Mitigate: held-out task cases;
  distribution shifts; pre-register (E-6); avoid repeated optimization on the
  same examples. Residual: Med.

- **R-20 Durability/recovery bugs in the custom orchestrator (Option B cost).**
  S:Med L:Med. Mitigate: fault-injection test suite (kill mid-task, duplicate
  event, timeout, budget exhaustion) as **Phase exit criteria** (NF-1, NF-2);
  transactional SQLite. Residual: Med. This is the price of not using a
  mature engine — keep the test suite honest.

## Deferred / phase-bound risks (watch list, not active yet)
- **R-13 Self-modification regressions** (Phase 5+): versioned changes,
  held-out eval, rollback. **R-14 Supervisor overreach** (Phase 6+):
  separate governance authority from epistemic quality. **R-15 Human control
  adequacy** (Phase 6+): usability tests. **R-16 Dependency/supply-chain
  safety**, **R-17 Model/provider change**, **R-18 Scale/concurrency** — all
  gated behind their phases in `MILESTONES.md`.

## Escalation rule
Any risk whose *mitigation is unproven* before the phase that relies on it
must be flagged **before** implementation of that phase (go/no-go gate,
`EVALUATION_PLAN` §Gates). R-02, R-07, R-12 are the ones most likely to change
the architecture, not just the tuning.
