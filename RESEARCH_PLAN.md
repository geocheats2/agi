# RESEARCH_PLAN

Investigation plan for Phase 0 → early Phase 1. Prioritizes primary sources,
reproducible evidence, and the *risky assumptions* that could invalidate the
architecture (charter §16, §25, §19.7).

## 1. Research questions (from charter §16)

**RQ-1 (persistence/value).** Does persistent multi-agent state provide value
over a resumable *single* workflow? *(H-1)*
- Sources: Temporal/durable-execution docs; LangGraph persistence semantics;
  fault-injection literature.
- Experiment: kill mid-task on a multi-step task; measure resume correctness
  + re-derivation cost vs. re-deriving from scratch.
- Stop condition: resume is unreliable OR re-derivation is so cheap that
  persistence isn't worth it → simplify.

**RQ-2 (independent assessment).** Does blind first-pass improve accuracy
enough for its token cost? *(H-2)*
- Sources: "society of minds" / multi-agent synthesis papers; single-model
  self-consistency work.
- Experiment: with/without first-pass on the graded anchor task.
- Stop condition: no accuracy gain within noise → drop first-pass.

**RQ-3 (correlated error under one model).** Can "independent" agents on the
*same* model still fail in a correlated way? *(H-3 — the load-bearing risk R-02/R-12)*
- Sources: multi-agent groupthink / correlation papers.
- Experiment: a case with a known/widely-shared wrong answer; does prompt +
  evidence diversity let *any* agent catch it?
- Stop condition: agents converge on the wrong answer reliably → report
  honestly; reconsider a second model for the challenger role.

**RQ-4 (bounded delegation).** Can dynamic delegation stay bounded +
understandable under real limits? *(H-4)*
- Experiment: recursion, budget exhaustion, duplicate-task, deadlock cases.
- Stop condition: any limit can be evaded → tighten enforcement before Ph2.

**RQ-5 (dissent preservation).** Does a valid minority view survive to the
final statement? *(H-5)*
- Experiment: majority-wrong / minority-correct case; check the statement's
  `unresolved_disagreements`.
- Stop condition: dissent is silently dropped → fix synthesis before Ph4 claim.

**RQ-6 (enforcement outside prompt).** Do constraints hold when enforced in
code rather than prompt? *(H-6)*
- Experiment: request a prohibited action; confirm runtime blocks + logs it.
- Stop condition: a prompt-only safeguard is the only thing holding → that is
  not a security boundary (charter §4.3); must re-arch.

## 2. Source quality (charter §19.6)
Priority: (1) official docs/specs, (2) peer-reviewed/preprints, (3) reproducible
experiments + public benchmarks, (4) issue trackers + source, (5) independent
analyses, (6) vendor claims (caution), (7) anecdotes (leads only). Record
publication date, version, and context. **Framework capabilities change
fast — re-verify current support before committing.**

## 3. Investigation tasks (Phase 0 wrap-up, cheap, no code)
- **T-1 (A-1):** one scripted chat-completions call against
  `100.105.83.8:8080` with a tool call; confirm response schema + tool-calling
  works + timing. *(Needs `QWEN_API_KEY`.)*
- **T-2:** confirm `reasoningEffort` toggling (`low/medium/xhigh`) is accepted
  and observe cost/latency delta.
- **T-3:** author the anchor benchmark's first fully-graded case + a deterministic
  checker (ASSUMPTIONS A-5).
- **T-4:** verify SQLite durability/recovery assumptions with a throwaway
  kill-and-restart script (A-3).
- **T-5:** pin candidate library versions (e.g., Python HTTP client, `jsonschema`,
  CLI lib) — record version + source for `DECISION_LOG`.

## 4. Stop conditions (project-level)
Stop or pivot the whole approach if:
- **RQ-3** shows single-model "independence" is theater *and* a second model is
  not acceptable → the societal premise is weak on this stack.
- **B2 (Option D) ≈ B4** on quality-per-cost across the anchor + conflict cases
  → prefer the simpler single-agent baseline (a *good* result).
- Recovery tests (NF-1) cannot be made reliable on the chosen store → revisit
  durability architecture (Option C).

## 5. Status
Open. T-3 and T-4 can start **now** without the API key. T-1/T-2 need the key.
