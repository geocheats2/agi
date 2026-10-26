# ARCHITECTURE_OPTIONS

Goal (charter §12): compare plausible architectures against explicit criteria,
pick a recommendation with a *simple baseline*, and state where each can fail.
We choose the **simplest stack that can test the most consequential
hypotheses**, not a framework because it is "agentic."

This is a *recommendation to be approved*, not a committed decision. See
`DECISION_LOG.md` D-04.

## Decision we are making
*What stack carries an agent + durable state + delegation + evidence +
enforcement + human control, in Python, local-only, on a single model?*

## Option A — Existing workflow/agent framework (e.g., LangGraph / Temporal /
CrewAI / AutoGen)
Use an established runtime for execution graph + state + persistence; build
constitution, evidence, and control semantics on top.

- **Enables:** durable execution, retries/checkpointing, human-in-the-loop
  primitives, fast start.
- **Costs:** framework lock-in; fighting the abstraction for our custom claim /
  dispute / constitutional types; observability tied to the framework's model;
  persistence behavior must be verified against crashes (many frameworks
  hold state in memory or a KV store, not a queryable relational store).
- **Can fail:** the "constitutional society" data model (claims ↔ evidence,
  dispute classes, dissent, amendment versioning) does not map onto the
  framework's node/state primitives without heavy workarounds — the part that
  is actually *our* contribution becomes the least controllable.

## Option B — Lightweight custom orchestrator (recommended)
Durable jobs/tasks + a relational database as the single source of truth +
an append-only event log + a thin model-adapter layer + explicit hand-written
state machines. Agent cognition kept deliberately simple at first.

- **Enables:** total control over the domain objects we actually need to
  *test* (claims/evidence/dispute/decision). The DB is queryable → provenance
  audit, disagreement reporting, and restart recovery are SQL, not framework
  archaeology. Simplest path to honest observability.
- **Costs:** we build what mature frameworks give for free (retries, workers,
  scheduling). More initial code. We must get durability *right* ourselves.
- **Can fail:** scope creep into "rebuild Temporal." Must be strictly bounded:
  one process, SQLite/Postgres, no queue/broker, one scheduler loop.

## Option C — Hybrid (existing workflow engine for durability + custom domain)
Use a durable-execution engine (e.g., Temporal) for the execution/state layer,
keep custom Python models for constitution/evidence/deliberation/control.

- **Enables:** battle-tested durability + concurrency with less code for the
  plumbing; clean boundary (engine = *how work runs*, our code = *what it
  means*).
- **Costs:** operational complexity (a server to run/version/migrate), two
  concepts to reason about, harder for a single dev + a local prototype.
- **Can fail:** over-engineered for the prototype phase; the durable-execution
  guarantees we most need are also achievable with B + a transactional DB.

## Option D — Single-agent baseline with simulated specialists (MANDATORY
baseline, not a rival)
A well-instrumented single agent that can invoke specialist *prompts* /
independent evaluation passes, with tool use and structured memory, but **no
persistent independent agents and no dynamic delegation**.

- **Purpose (charter §12.2):** establish whether a *true* society creates
  measurable value. If D performs as well as the societal version at lower
  cost, prefer D. Do **not** dismiss D as philosophically inferior.
- **Costs:** none — it is the control arm of every key experiment.

## Scoring (1 = weak, 5 = strong; prototype = the Phase 1–4 prototype)

| Criterion | A | B | C | D |
|---|---|---|---|---|
| Durability & recovery | 3 | 4 | 5 | 4 |
| State-machine clarity (our domain types) | 2 | 5 | 4 | 3 |
| Inspect & intervene (CLI) ease | 2 | 5 | 4 | 4 |
| Task-graph / delegation flexibility | 3 | 4 | 4 | 1 |
| Security / sandboxing control | 3 | 5 | 4 | 4 |
| Model/provider portability | 3 | 5 | 4 | 4 |
| Observability | 2 | 5 | 4 | 4 |
| Evaluation / testability | 3 | 5 | 4 | 5 |
| Concurrency (future) | 4 | 3 | 5 | 2 |
| Failure recovery (future) | 4 | 4 | 5 | 3 |
| Implementation complexity (5 = simplest) | 3 | 4 | 2 | 5 |
| Deployment / maintenance burden (5 = lightest) | 3 | 4 | 2 | 5 |
| Data portability | 3 | 5 | 4 | 4 |
| Represent disagreement/evidence well | 2 | 5 | 4 | 3 |
| **Prototype total** | **43** | **62** | **58** | **51** |

*Weighting note:* for the prototype, "control", "observability",
"testability", and "represent disagreement well" matter more than "concurrency"
and "deployment burden." A and B score similarly on durability; B wins the
domain-model and control rows, which is exactly what we are trying to test.

## Recommendation
**Build Option B (lightweight custom orchestrator) as the primary system, and
always run Option D (single-agent baseline) in parallel as the control.** Hold
Option C as the *revisit* trigger if the prototype's durability or concurrency
needs outgrow what a transactional DB + single loop gives us. Defer Option A.

### Proposed minimal stack (each component justified)
- **Python 3.11+**, single process. Justification: owner choice; richest
  LLM/durability tooling.
- **SQLite** (file) as the authoritative structured store for agents, tasks,
  claims, evidence, decisions, events. Justification: queryable, zero-ops,
  transactional → recovery + provenance audit are SQL; no server to run.
  (Swap to Postgres later via a repository abstraction if needed — N/A now.)
- **Append-only event table** in the same DB for consequential transitions
  (event schema). Justification: audit + recoverability without a broker.
- **Model adapter** (thin wrapper over the OpenAI-compatible chat-completions
  endpoint, `QWEN_BASE_URL`/`QWEN_API_KEY` from env) recording model/config
  version, latency, token usage, failures. Justification: portability
  (NF-7) + cost accounting (F metric).
- **Explicit tool registry** with permission + side-effect class. Prototype
  ships with *read-only local* tools only (e.g., read a local corpus, run a
  deterministic checker); **no** network/external/write-durable tools.
- **Scheduler loop**: pulls one bounded task at a time (concurrency=1 in the
  prototype; cap from env), runs the agent cognition step, checkpoints,
  advances state. Justification: simplest bounded autonomy; concurrency added
  later.
- **CLI** (`csa` console): `status`, `agent <id>`, `claim <id>`, `events`,
  `pause <task>`, `cancel <task>`, `run --task <case>`. Justification: owner
  chose CLI over a web dashboard for the prototype.
- **Benchmark harness** (`experiments/`): runs a task case against the society
  *and* the single-agent baseline under matched budget, emits JSON metrics.

### What is intentionally NOT built in the prototype (charter §18 "omit")
- No message broker, no graph DB, no vector store, no distributed workers.
- No web UI. No external side-effect tools. No model fine-tuning. No
  multi-model routing (single model). No self-modification of enforcement.
