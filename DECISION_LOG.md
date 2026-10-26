# DECISION_LOG

Format per charter §19.5: ID, date, question, options, evidence, trade-offs,
selected option, rejected + why, owner/approval, confidence + reversibility,
revisit trigger.

Status values: **Proposed** (foreman recommends, awaiting owner) vs
**Confirmed** (owner approved).

---

## D-01 — Model + endpoint
- **Date:** 2026-10-25
- **Question:** What model runs the agents?
- **Options:** multiple providers (cost/latency/diversity) vs a single
  custom endpoint.
- **Evidence owner provided:** endpoint config for
  `Qwen/Qwen3.8-27B-FP8` at `http://100.105.83.8:8080/`, tool-calling/vision/
  thinking/reasoning-effort, 200k/40k, 120 s.
- **Selected:** single custom endpoint (Qwen 27B FP8).
- **Rejected:** multi-model now — adds cost/ops, and owner fixed the model.
- **Owner / approval:** Owner. **Status:** Confirmed.
- **Confidence:** high. **Reversibility:** high (adapter isolates it).
- **Revisit trigger:** endpoint unstable/slow, or H-3 shows same-model
  correlation defeats independent assessment.
- **Consequence accepted:** higher correlated-error risk (R-02).

## D-02 — Runtime language
- **Date:** 2026-10-25
- **Question:** What language for the runtime?
- **Selected:** Python (owner: "Python is fine").
- **Rationale:** richest LLM + persistence ecosystem.
- **Status:** Confirmed. **Reversibility:** n/a (foundational).

## D-03 — Secrets handling
- **Date:** 2026-10-25
- **Question:** How is the model API key supplied?
- **Selected:** environment variable read at runtime; owner will create a
  `.env` (git-ignored) with `QWEN_API_KEY`. Never in code, state, or logs.
  `.env.example` documents keys, values omitted.
- **Rejected:** hard-coding; committing the key; storing in agent state.
- **Status:** Confirmed. **Reversibility:** high.

## D-04 — Architecture stack (recommends Option B)
- **Date:** 2026-10-25
- **Question:** What stack carries agent + state + delegation + evidence +
  enforcement + control?
- **Options:** A (framework), B (lightweight custom), C (hybrid), D (baseline).
- **Evidence:** scoring in `ARCHITECTURE_OPTIONS.md`; B dominates on
  domain-model clarity, control, observability, testability.
- **Selected (proposed):** Option B primary; **Option D always runs in
  parallel as the baseline.** C = revisit trigger.
- **Rejected (now):** A (lock-in vs. our domain model); C (over-engineered for
  prototype).
- **Owner / approval:** Owner ("Yes, move forward", 2026-10-25).
  **Status:** Confirmed.
- **Confidence:** medium-high. **Reversibility:** medium (pre-code, cheap to
  change).
- **Revisit trigger:** durability/concurrency limits of a single DB + loop.

## D-05 — Persistence store
- **Date:** 2026-10-25
- **Question:** Where does authoritative state live?
- **Selected (proposed):** SQLite (file) + append-only event table; repository
  abstraction so Postgres is a drop-in later.
- **Evidence:** owner = local/dev only; queryable provenance + transactional
  recovery needed for H-1.
- **Rejected (now):** Postgres (needs a server), graph DB, vector store
  (premature).
- **Status:** Confirmed. **Revisit trigger:** scale / concurrency.

## D-06 — Human control surface: CLI first
- **Date:** 2026-10-25
- **Question:** Web dashboard now or temporary CLI?
- **Selected (proposed):** structured CLI for the prototype (`status`, `agent`,
  `claim`, `events`, `pause`, `cancel`, `run`); web UI deferred to Phase 6.
- **Evidence:** owner chose local/dev + CLI is "sufficient for the first
  prototype" (charter §21.10 permits CLI).
- **Status:** Confirmed. **Revisit trigger:** usability tests show CLI is a
  bottleneck for intervention (Phase 6 exit).

## D-07 — No external side effects in the prototype
- **Date:** 2026-10-25
- **Question:** What actions may agents take unattended?
- **Selected (proposed):** only read-only local tool calls + writing local
  artifacts to a designated writable dir. Every other action is a *proposal*,
  not an execution. Network egress limited to the model endpoint.
- **Rejected:** any durable-write/network/financial/external action.
- **Status:** Confirmed (aligns with owner "local/dev, no external side effects").
- **Revisit trigger:** a future milestone genuinely needs an external action →
  then add approval gates + confirmation + audit **before** enabling it.

## D-08 — Concurrency = 1 in the prototype
- **Date:** 2026-10-25
- **Question:** How many concurrent tasks?
- **Selected (proposed):** 1 (sequential), cap from `CSA_MAX_CONCURRENT_TASKS`.
- **Rationale:** trivial recovery + cost accounting; concurrency is a later
  concern.
- **Status:** Confirmed. **Revisit trigger:** throughput needs; Option C revisit.

## D-09 — Model backend: deterministic fake until the API key exists
- **Date:** 2026-10-25
- **Question:** How does the system develop and test before
  `QWEN_API_KEY` is in `.env`?
- **Selected:** A deterministic `FakeModel` backend, auto-selected when no API
  key is present (override via `CSA_BACKEND=fake|live`). Zero cost,
  deterministic, lets every durability/idempotency/recovery test run offline.
  The live OpenAI-compatible backend activates automatically once the key
  exists.
- **Rejected:** requiring the key before any development (blocks Phase 1).
- **Status:** Confirmed (consequence of D-01/D-03 owner decisions).
- **Reversibility:** trivial (config flag).

## D-10 — Phase 1 execution record (no new architectural choices)
- **Date:** 2026-10-25
- **Question:** Any deviations from D-01…D-09 during Phase 1 implementation?
- **Answer:** None. Implementation followed D-04 (custom orchestrator),
  D-05 (SQLite WAL + append-only events), D-06 (CLI), D-08 (concurrency 1).
  One operational detail fixed in-repo: `python -m csa` added as a fallback
  entry point because the `csa.exe` console-script install is blocked by a
  locked file in this environment — same code, different launcher.
- **Result:** Phase 1 exit criteria met; 15/15 tests green
  (`tests/unit` + `tests/recovery`), CLI smoke-tested end-to-end offline.
- **Status:** DecisionRecord. **Reversibility:** n/a (record).

## D-11 — Auxiliary model pool: available now, NOT built in yet
- **Date:** 2026-10-25
- **Question:** Owner offered an auxiliary endpoint pool alongside
  `Qwen/Qwen3.8-27B-FP8` (all at `100.105.83.8`): bge-m3 embeddings `:8102`,
  bge-reranker-v2-m3 `:8103`, SapBERT-from-PubMedBERT `:8105`, LightOnOCR
  `:8101`. Should a "fast memory" (retrieval layer) be implemented at the
  start of Phase 2?
- **Verified reachability (2026-10-25):** Qwen `:8080/v1/chat/completions`
  live (Bearer ok, vLLM, ~0.2 s); reranker `:8103/rerank` live (same key);
  bge-m3 `:8102` healthy but **401 with the chat key — separate token
  required (open owner action)**; `:8101`/`:8105` healthy.
- **Selected:** Defer implementation to **Phase 3** (evidence & shared
  knowledge), where the charter places it and defines testable exit
  criteria. **Design input now:** Phase 3 retrieval should be
  *embedding (bge-m3) + re-rank (bge-reranker)* — both already served —
  not keyword search.
- **Rejected:** building a provisional memory in Phase 2 — no Phase 2
  requirement uses retrieval, and an ad-hoc design would be reworked and
  would violate plan-before-code (charter §0, §17).
- **Status:** Confirmed (owner: "move forward with phase 2" when not
  crucial now). **Revisit trigger:** Phase 2 work unexpectedly requires
  shared-text retrieval → then design a minimal store in Phase 2.5.
- **Open owner action:** provide the `:8102` bge-m3 API token.
