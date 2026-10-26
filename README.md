# Constitutional Society of Agents

A research-and-engineering project to build a **persistent society of
independently-reasoning agents** governed by an explicit, versioned
constitution — capable of deliberation, delegation, evidence-grounded
collective judgment, preserved disagreement, and learning from evaluated
experience — with a human who can inspect and steer it at all times.

**Current phase:** Phase 1 (durable task & agent state) — **complete 2026-10-25**
(owner-approved). Phase 2 (bounded delegation) is next.

## Read first
1. `Plan.md` — the authoritative charter (source of truth).
2. `PROJECT_STATE.md` — status, confirmed decisions, next actions.
3. `ARCHITECTURE_OPTIONS.md` — the recommendation you're being asked to approve.
4. `MILESTONES.md` — what gets built, in what order, with testable exits.
5. `EVALUATION_PLAN.md` + `PROTOTYPE_SPEC.md` — how we'll know it works.

## The one question we're answering
> Does a small group of persistent, independently-assessed agents with explicit
> evidence and disagreement handling beat a strong single-agent baseline, at
> acceptable cost? (charter §18)

## Key facts (owner-confirmed, 2026-10-25)
- **Model:** `Qwen/Qwen3.8-27B-FP8` via a custom OpenAI-compatible
  chat-completions endpoint (`http://100.105.83.8:8080/`). Tool-calling,
  vision, thinking, reasoning-effort. 200k/40k.
- **Language:** Python. **Deployment:** local/dev only, no external side
  effects. **Control:** CLI first.
- **Secrets:** model API key from `.env` (`QWEN_API_KEY`), git-ignored.

## Planning artifacts (Phase 0)
| File | Purpose |
|---|---|
| `PROJECT_STATE.md` | Status, what exists, next actions, `.env` contract |
| `REQUIREMENTS.md` | Normalized requirements; commitments vs. hypotheses vs. non-goals |
| `ASSUMPTIONS_AND_QUESTIONS.md` | Driving assumptions, hypotheses to test, open owner decisions |
| `ARCHITECTURE_OPTIONS.md` | Options A–D compared; recommendation (Option B + Option D baseline) |
| `RESEARCH_PLAN.md` | Research questions, sources, experiments, stop conditions |
| `DECISION_LOG.md` | D-01…D-08, with alternatives, rationale, revisit triggers |
| `RISK_REGISTER.md` | Risks S×L, mitigations, owners; R-02/R-07/R-12 are load-bearing |
| `MILESTONES.md` | Phase 0–8 with testable exit criteria + go/no-go gates |
| `EVALUATION_PLAN.md` | Baselines (B0–B4), metrics, pre-registration, regression, gates |
| `PROTOTYPE_SPEC.md` | The smallest meaningful society (roles, workflow, data model, exits) |

## Recommended path (pending approval)
**Option B** — lightweight custom orchestrator (single Python process, SQLite
as the authoritative store, thin model-adapter, explicit tool registry, CLI),
with **Option D** — a well-instrumented single-agent baseline — always run in
parallel as the control. Hold **Option C** (hybrid) as the revisit trigger if
durability/concurrency outgrow a single DB + loop. See `ARCHITECTURE_OPTIONS.md`.

## Quickstart (Phase 1 runtime)
```
pip install -e .            # then: csa ...   (or: python -m csa ...)
copy .env.example .env      # add QWEN_API_KEY for live runs (optional)
csa backend                 # fake until QWEN_API_KEY is set (CSA_BACKEND=auto)
csa agents --create         # foreman / investigator / analyst / challenger
csa new "your objective" --agent <agent-id> --acceptance "..."
csa run <task-id>
csa task <task-id>
csa events --task <task-id>
csa pause <task-id>; csa resume <task-id>; csa cancel <task-id>
csa result <task-id>
python -m pytest tests -q   # 15 tests: unit + fault-injection recovery
```
Everything runs offline on the deterministic FakeModel; the live Qwen
endpoint activates automatically once `QWEN_API_KEY` exists in `.env`.

## Status & next step
Phase 0 approved, **Phase 1 complete** (2026-10-25, 15/15 tests green — see
`MILESTONES.md` for the evidence). Next: owner supplies `QWEN_API_KEY` for
first live smoke, then **Phase 2 (bounded delegation)** including the
mandatory single-agent baseline comparison (Option D).

## Repo structure (planned destination — created as it gets content)
```
README.md  PROJECT_STATE.md  REQUIREMENTS.md  ASSUMPTIONS_AND_QUESTIONS.md
ARCHITECTURE_OPTIONS.md  ARCHITECTURE.md  RESEARCH_PLAN.md  DECISION_LOG.md
RISK_REGISTER.md  MILESTONES.md  EVALUATION_PLAN.md  CONSTITUTION.md
SECURITY_MODEL.md  OPERATIONS.md
docs/{concepts,architecture,decisions}/
schemas/{agent,task,evidence,decision,event,claim}.schema.json
experiments/{baseline,deliberation,delegation,memory,reliability}/
evaluations/{datasets,rubrics,regression,reports}/
tests/{unit,integration,recovery,security,governance}/
src/  scripts/  artifacts/
.env.example  .env (git-ignored)
```
