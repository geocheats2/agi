# PROJECT_STATE

**Project:** Constitutional Society of Agents
**Phase:** Phase 1 (Durable task & agent state) — **COMPLETE 2026-10-25; Phase 2 next**
**Last updated:** 2026-10-25
**Status:** PROTOTYPE — durable task runtime + agent state, 15/15 tests green, CLI smoke-tested. Run offline on `CSA_BACKEND=auto` (FakeModel) until `QWEN_API_KEY` is in `.env`.

## What exists
| Type | Item |
|---|---|
| Source document | `Plan.md` (the charter — authoritative) |
| Planning artifact | `PROJECT_STATE.md` (this file) |
| Planning artifact | `REQUIREMENTS.md` |
| Planning artifact | `ASSUMPTIONS_AND_QUESTIONS.md` |
| Planning artifact | `ARCHITECTURE_OPTIONS.md` |
| Planning artifact | `RESEARCH_PLAN.md` |
| Planning artifact | `DECISION_LOG.md` |
| Planning artifact | `RISK_REGISTER.md` |
| Planning artifact | `MILESTONES.md` |
| Planning artifact | `EVALUATION_PLAN.md` |
| Planning artifact | `PROTOTYPE_SPEC.md` |
| Navigation | `README.md` |

## What exists now (Phase 1, 2026-10-25)
| Type | Item |
|---|---|
| Runtime | `src/csa/` — config, SQLite DB (WAL), model adapters (Fake/Live), artifact store, state-machine runtime, CLI |
| Schemas | `schemas/` — `schema.sql`, `agent.schema.json`, `task.schema.json`, `event.schema.json` |
| Tests | `tests/unit/` (10) + `tests/recovery/` (5 fault-injection) — all passing |
| Constitution | `CONSTITUTION.md` v0.1.0 (thin, honest "not yet true" section) |
| Ops | `pyproject.toml`, `.env.example`, `.gitignore` |

Run: `python -m csa.cli backend|agents --create|new|run|task|result|events|pause|resume|cancel`

## What is NOT yet built
Delegation/child tasks (Phase 2); evidence & claims registry (Phase 3);
independent assessment workflow (Phase 4); runtime-enforced policy layer
(Phase 5); the live model has not been exercised yet (no `QWEN_API_KEY`).

## Confirmed decisions (owner, 2026-10-25)
- **Model:** `Qwen/Qwen3.8-27B-FP8` via a custom OpenAI-compatible
  chat-completions endpoint at `http://100.105.83.8:8080/`. Supports tool
  calling, vision, thinking, and reasoning-effort (`low`/`medium`/`xhigh`).
  200k input / 40k output tokens; 120 s timeout.
- **Model diversity:** single model for now. *Consequence:* correlated-error
  risk (R-02) is high because "different agents" share one underlying model.
  Mitigated via different prompts, different evidence, and different methods —
  not by changing the model.
- **Secrets:** API key is read from environment (owner will place it in a
  `.env` file). Never hard-coded, never written to state or logs.
- **Runtime language:** Python.
- **Deployment:** local/dev only. No external side effects, no external
  accounts, no destructive or financial actions.
- **Prototype control surface:** structured **CLI** first (no web dashboard yet).

## The one research question this project is answering right now
> Does a small group of persistent, independently-assessed agents with
> explicit evidence and disagreement handling produce better decisions than a
> strong single-agent baseline, at acceptable cost?  (charter §18)

## Next actions
1. **OWNER:** place `QWEN_API_KEY` in `.env` + first live smoke
   (`csa backend` should report `live`; then one live task). FakeModel covers
   everything until then.
2. **FOREMAN:** on owner go, start **Phase 2 (bounded delegation)**: task
   contracts, child tasks, depth/concurrency/deadline/budget limits,
   dependency tracking, recursion/duplicate detection, parent validation,
   and the mandatory Option-D single-agent baseline comparison.

## Blockers
- `QWEN_API_KEY` not yet in `.env` (needed only for live-model runs;
  the offline FakeModel backend unblocks all development).

## `.env` contract (owner to fill later)
```dotenv
# Model endpoint + credentials for the Constitutional Society runtime
QWEN_BASE_URL=http://100.105.83.8:8080/
QWEN_MODEL_ID=Qwen/Qwen3.8-27B-FP8
QWEN_API_KEY=
# Cost guardrails (defaults are conservative for a single 27B box)
CSA_MAX_TASK_TOKENS=200000
CSA_MAX_TASK_RUN_COST_USD=5.0
CSA_MAX_CONCURRENT_TASKS=2
```
`.env` is git-ignored. A checked-in `.env.example` documents the keys without
values (to be added alongside Phase 1 code).

## Resumability
If this session is interrupted, resume from: (a) this file, (b) `DECISION_LOG.md`
for committed choices, (c) `MILESTONES.md` for the next approved phase. Do not
rely on conversational memory.
