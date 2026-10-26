# ASSUMPTIONS_AND_QUESTIONS

Purpose: make unknowns, assumptions, and hypotheses explicit. A clear
unresolved question beats a fabricated certainty (charter §19.7, §21). We do
**not** turn every charter suggestion into a requirement. Grouped by:
**(A)** assumptions driving the recommendation now, **(B)** hypotheses the
prototype must test, **(C)** open decisions for the owner (with a recommended
default each), **(D)** what evidence could change our mind.

## A. Assumptions currently driving the plan (verify before they bite)
| ID | Assumption | Why it matters | Cheap test to confirm |
|---|---|---|---|
| A-1 | The custom endpoint at `100.105.83.8:8080` is reachable and behaves like standard OpenAI chat-completions with tool-calling. | All cognition depends on it. | One scripted call with +1 tool call; check schema of response. |
| A-2 | A single 27B model is fine for the prototype. | Constrains model-diversity-based mitigations. | Run one known-conflict case; observe if same-model disagreement is even possible with prompt-level diversity. |
| A-3 | SQLite is adequate for the prototype's state volume and recovery needs. | Core durability choice. | Fault-injection: kill mid-task, restart, verify state intact. |
| A-4 | Prompt-level "thinking"/reasoning-effort can be toggled per call (low/med/xhigh). | Cost/quality control. | Toggle effort on one call; confirm field accepted and cost difference. |
| A-5 | The local corpus / deterministic checkers we write can provide *objective* answers for at least some benchmark tasks. | Objective scoring (E-2) is mandatory. | Author 1 fully-graded task with a deterministic checker. |

## B. Hypotheses the prototype must TEST (not assume)
- **H-1 (persistence):** persistent multi-agent state yields value over a
  resumable single workflow. *Test:* kill-and-restart on a multi-step task;
  confirm resume correctness vs. a baseline that re-derives from scratch.
- **H-2 (independent assessment):** blind independent initial assessment
  improves accuracy enough to justify its token cost. *Test:* with-vs-without
  first-pass mode on a graded set.
- **H-3 (correlated error):** with a single shared model, "independent"
  agents still make the *same* mistake. *Test:* a case where the model has a
  known/widely-shared wrong answer → does any agent catch it? If not, the
  "society" is theater (R-02, R-12).
- **H-4 (delegation bounds):** dynamic delegation stays bounded and
  understandable under budget/depth limits. *Test:* recursion + budget-
  exhaustion + duplicate-task cases.
- **H-5 (dissent preservation):** a valid minority view survives to the final
  statement. *Test:* a "majority is wrong / minority identifies the flaw" case.
- **H-6 (enforcement outside prompt):** constraints hold when enforced in code
  rather than prompt. *Test:* request a prohibited action; confirm runtime
  blocks it and logs it.
- **H-7 (society ≷ single-agent):** does the society beat the single-agent
  baseline (Option D) on quality **per unit cost**? *Test:* the core benchmark
  (EVALUATION_PLAN).

## C. Open decisions for the owner
Format: decision → why it matters now → recommended default → alternatives.

1. **Anchor benchmark task** (also picked in EVALUATION_PLAN; confirm here).
   *Why now:* everything is graded against it. *Default:* a **bounded code /
   technical-investigation** task (e.g., "reproduce and diagnose a specific
   bug in a small repo with a deterministic test"), because it yields objective
   results and realistic decomposition. *Alternatives:* research/synthesis over
   a local corpus; a planning task.
2. **Reasoning effort default** for routine vs. consequential calls.
   *Default:* `medium` routine, `xhigh` for deliberation/synthesis steps;
   `low` for triage. Tune after measured cost/quality.
3. **Concurrency for the prototype.** *Default:* 1 (sequential) to keep
   recovery + accounting trivial; cap from `CSA_MAX_CONCURRENT_TASKS`.
4. **Retention.** *Default:* keep all local event/state/artifact data; no
   external retention policy applies (local-only). Revisit if data grows.
5. **What must *never* leave the local environment.** *Default:* nothing leaves
   — the only network egress in the prototype is the model endpoint
   (`QWEN_BASE_URL`). Confirm that's the sole permitted call.
6. **What (if anything) may be automated without approval** in the prototype.
   *Default:* only read-only local actions and building local artifacts that
   land in a designated writable dir. Everything else = proposal, not execution.

## D. Evidence that could change the recommendation (revisit triggers)
- If **H-3** shows same-model correlation makes "independent" agents a
  non-sequitur → reconsider single-model assumption (A-2); possibly require a
  second model for the challenger role.
- If **H-7** shows the single-agent baseline (Option D) matches the society
  within noise at much lower cost → **prefer the simpler Option D** for those
  task classes (charter §18.4, §12.2). This is a *good* result, not a failure.
- If durability/failure-injection exposes SQLite limitations at target scale →
  switch to Postgres (the repository abstraction keeps this cheap).
- If concurrency needs outgrow a single loop → revisit **Option C** (hybrid).
- If the custom endpoint proves unstable/slow → reconsider model/provider
  (adapter layer isolates this).
