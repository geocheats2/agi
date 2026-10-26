# EVALUATION_PLAN

Evaluation is a central workstream, not final QA (charter §15). It exists to
answer, with evidence, the single research question:

> *Does a small persistent, independently-assessed society produce better
> decisions than a strong single-agent baseline, at acceptable cost?*

## 1. Arms compared (charter §15.1)
1. **B0 — single capable agent** (no tools).
2. **B1 — single agent + tools + structured memory.**
3. **B2 — multiple specialist invocations, centralized orchestration**
   (= our **Option D** baseline — mandatory control).
4. **B3 — the small persistent society with delegation** (prototype).
5. **B4 — society + deliberation + evidence tracking** (full prototype).

Not every experiment needs all five; major "the society is better" claims **must**
be measured against at least B1 and B2.

## 2. Anchor benchmark (proposed — confirm in ASSUMPTIONS C-1)
Primary family: a **bounded code/technical-investigation task with objective
output** (charter §15.2 "Code and technical investigation").
- Example shape: given a small local code artifact with a seeded defect and a
  failing test, the system must (a) localize the fault, (b) produce a minimal
  reproduction, (c) propose + implement a bounded fix, (d) make the test pass,
  (e) report evidence + uncertainty + dissent honestly.
- **Objective checks:** the provided test suite (pass/fail), reproduction
  correctness (determinism), and a rubric for report quality (citations,
  uncertainty, dissent preserved).
- Auxiliary families added as cases grow: research/synthesis over a local owned
  corpus; a known-conflict case; a "majority is wrong, minority catches the
  flaw" case; a misleading-source case.

Task-selection rules (charter §18.3): verifiable output, multiple sources,
realistic decomposition, *some* conflicting interpretations, bounded side
effects, manageable cost. **Not** only open-ended philosophical questions.

## 3. Metrics (charter §15.3; use several — any single one can be gamed)
| Area | Metric | How measured |
|---|---|---|
| Task quality | rubric score / objective test pass | blind eval + deterministic checks |
| Evidence | citation-support rate, unsupported-claim rate | provenance audit |
| Disagreement | known-conflict detection; minority-correct retention | conflict test suite |
| Delegation | subtask completion; dependency correctness | task-graph logs |
| Reliability | recovery rate after injected failure | fault-injection tests |
| Calibration | Brier / log-loss where probabilities are meaningful | recorded vs. observed |
| Cost | tokens, tool calls, $ per successful task | metered adapter usage |
| Latency | time-to-first-useful-result; end-to-end | timestamped events |
| Coordination overhead | cost/latency of B4 vs B2 (same model, same budget) | matched runs |
| Safety | unauthorized-action rate (target 0) | adversarial tests |
| Human control | time to locate state + intervene | usability/CLI timing |

## 4. Pre-registration (charter §15.5)
For every *important* experiment record **before running**: hypothesis,
arms, task set, metric, sample size, pass/fail threshold, and stop condition.
Pre-registration lives in `experiments/README.md` + per-experiment files. This
protects against benchmark overfitting (R-19).

## 5. Regression policy
- A versioned `experiments/regression/` suite must stay green across code
  changes; a regression is a phase blocker.
- Keep a **held-out** case set separate from cases used for tuning
  (R-19). Rotated/hidden cases for the "did it actually generalize" check.
- Distinguish clearly in reports: *implemented* vs *planned* vs *simulated* vs
  *unverified* claims (charter §0.1.9).

## 6. Go/no-go gates (per phase)
| Gate | Pass condition | No-go fallback |
|---|---|---|
| After Ph1 | Recovery + idempotency tests green | Fix durability before delegating |
| After Ph2 | Bounded delegation under limits; B2 comparison exists | Delegation not adding value → simplify |
| After Ph3 | Claims traceable; conflicts coexist; retrieval tested | Simplify knowledge layer |
| After Ph4 | Known-conflict cases pass; B4 vs B1/B2 quality-per-cost measured | If B2 ≈ B4 within noise → **prefer B2** (Option D) |
| After Ph5 | Prohibited action blocked by runtime; stop independent of agent | Re-arch enforcement before trusting it |
| After Ph6 | Operator intervenes during live work with logged transitions | Iterate control surface |

**The decisive gate is after Phase 4:** if the single-agent/specialist baseline
matches the society on quality-per-cost, the honest outcome is to *prefer the
simpler architecture* (charter §18.4, §12.4) for those tasks. That is a success
of the experiment, not a failure of the project.

## 7. Cost/latency budget (default; owner-tunable)
- Per prototype run: cap tokens (`CSA_MAX_TASK_TOKENS`) and $
  (`CSA_MAX_TASK_RUN_COST_USD`) from `.env`.
- Reasoning effort: `medium` routine / `xhigh` deliberation / `low` triage
  (ASSUMPTIONS C-2). Overhead is reported, not assumed zero.
- If a run hits its budget it stops *cleanly* (record partial result), never
  silently overruns.
