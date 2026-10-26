# REQUIREMENTS

Source: `Plan.md` (charter). This document **normalizes** the charter into
testable requirements and clearly separates *design commitments* (confirmed),
*hypotheses* (to be tested), and *non-goals* (intentionally excluded) so that
not every suggestion is silently promoted into a mandatory requirement
(charter §25, Action 2).

Priority: **P0** = must hold for the prototype to be valid.
**P1** = essential for the intended system, may land after the prototype.
**P2** = desirable / future.

Legend: [F] functional · [NF] non-functional · [S] safety · [E] evaluation.

## A. Confirmed design commitments (from the owner + charter)
- **C-1** Runtime is Python; local/dev-only deployment; single model
  `Qwen/Qwen3.8-27B-FP8` (custom endpoint) for now. (Owner, 2026-10-25)
- **C-2** API key supplied via environment/`.env`; never in code or state.
- **C-3** No external side effects in the prototype (see Non-goals N-7).

## B. Functional requirements

### Agents & persistence (G1)
- **F-1 [P0]** An agent has durable identity and state that survives a
  process restart: it can resume an assigned task with its beliefs,
  obligations, work history, and budget context intact.
- **F-2 [P0]** Durable task state machine (e.g. queued → active →
  blocked → completed / failed / cancelled) persisted to disk, not held only
  in memory.
- **F-3 [P1]** Structured, versioned agent state (see `PROTOTYPE_SPEC.md`
  data model). No claim of "persistent cognition" beyond demonstrated behavior.

### Delegation (G2)
- **F-4 [P0]** A parent agent can create a bounded subtask with an explicit
  contract: objective, inputs, acceptance criteria, budget, deadline,
  depth limit.
- **F-5 [P0]** Delegation is bounded: hard limits on depth, concurrency,
  deadline, and token/cost budget are enforced at the runtime (not by prompt).
- **F-6 [P0]** Dependencies between tasks are tracked; a parent validates a
  child's output against the contract's acceptance criteria before integrating.
- **F-7 [P1]** Cancellation propagates to descendants; deadlock/recursion is
  detected.

### Evidence & knowledge (G4, G5)
- **F-8 [P0]** A "claim" record links to evidence records (source, provenance,
  capture time, trust status). Material claims in a collective statement must
  resolve to at least one evidence item.
- **F-9 [P0]** Conflicting claims can **coexist** until resolved; a correction
  appends a revision, it does not silently overwrite history.
- **F-10 [P1]** A source repeated by agents that descend from the same origin
  is flagged as *not* independent corroboration.
- **F-11 [P1]** Three storage layers: private working state, shared cognitive
  workspace, durable knowledge record.

### Deliberation & collective judgment (G4, G5)
- **F-12 [P0]** Agents produce a **blind initial assessment** (before seeing
  peers' answers) on an independent-assessment question.
- **F-13 [P0]** A structured collective statement is emitted with: conclusion,
  status, established findings, assumptions, evidence for/against, alternative
  explanations, unresolved disagreements, correlated-evidence warnings, and
  recommended next action (schema in PROTOTYPE_SPEC §Collective statement).
- **F-14 [P0]** Material dissent is **preserved** in the statement — not erased
  for a polished answer.
- **F-15 [P1]** Disagreement is classified (fact / probability / value /
  strategy / risk tolerance) and targeted challenge is directed at specific
  claims.

### Constitution & enforcement (G7)
- **F-16 [P1]** A versioned `CONSTITUTION.md` governs the society; version is
  attached to tasks and decisions.
- **F-17 [P1]** The runtime, not the prompt, is the security boundary:
  permission evaluation + approval gates + budget enforcement are in code.
- **F-18 [P1]** An emergency stop / budget stop that does **not** depend on the
  cooperation of the agent being stopped.
- **F-19 [P1]** Amendment workflow: any agent may propose, but a worker cannot
  unilaterally change foundational rules or enforcement code.

### Human control (G3)
- **F-20 [P0]** Operator can, via CLI: list active tasks/agents, inspect an
  agent's task/beliefs/permissions/budget, pause a task, cancel a task, and
  read the append-only event history.
- **F-21 [P1]** Approval queue for any action classified as high-impact or
  external (none in prototype — see N-7).
- **F-22 [P1]** The operator can see whether an action is *proposed, queued,
  executing, completed, or verified* (explicit state, not inferred).

### Learning (G6)
- **F-23 [P1]** Structured experience records: objective, assumptions, evidence
  used, predictions (recorded *before* outcomes), actions, actual outcome,
  rubric, cost, failures, and lessons.
- **F-24 [P1]** At least one process change is shown to improve a held-out
  evaluation *or is rejected*; regressions are detectable and rollback works.
- **F-25 [P2]** Task-specific capability profiles with uncertainty.

## C. Non-functional requirements

### Reliability & recoverability (G9)
- **NF-1 [P0]** Crash / kill of a running process must not corrupt project
  state; restarting resumes cleanly. Durable event history is append-only.
- **NF-2 [P0]** Model-invocation has idempotency: a retried task does not
  double-apply side effects (prototype side effects are local/reversible only).
- **NF-3 [P1]** Checkpointing: long tasks can checkpoint and resume.
- **NF-4 [P1]** Liveness/health: stuck tasks are detectable and reported.

### Observability
- **NF-5 [P0]** Append-only audit/event log (event schema) for consequential
  transitions: who, what, when, prior→result state, artifacts, authorization.
- **NF-6 [P1]** Metrics captured per task: tokens, tool calls, latency
  (time-to-first-useful-result and end-to-end), cost, retries.

### Security (charter §13)
- **S-1 [P0]** Secrets (API key) only from environment; redacted from all
  traces and state.
- **S-2 [P0]** Untrusted content (tool outputs, retrieved text) is treated as
  *data*, not instructions; least-privilege tool surface.
- **S-3 [P1]** Tool registry is explicit: stable name, I/O schema, permission
  class, side-effect class, timeout/retry, budget, audit behavior.
- **S-4 [P0]** Sandbox/code execution (if any tool executes generated code):
  isolated filesystem + restricted network + CPU/memory/wall-clock limits.
  For the prototype, execute **no** untrusted generated code.

### Portability
- **NF-7 [P1]** Model/provider is behind an adapter layer; the constitution,
  evidence, and control semantics are not coupled to one provider.

## D. Evaluation requirements (G10)
- **E-1 [P0]** A strong single-agent baseline exists and is measured on the
  same tasks, same model, same budget cap, for a fair comparison.
- **E-2 [P0]** At least some tasks have **objective** (automated) tests, not
  only open-ended judgment (charter §18.3).
- **E-3 [P0]** Known-conflict / known-correlated-error test cases exist to
  verify disagreement detection and dissent preservation.
- **E-4 [P0]** Cost and coordination overhead are measured, and reported
  honestly alongside quality.
- **E-5 [P1]** Metrics can be gamed → use several complementary metrics and
  inspect examples, not just aggregate scores.
- **E-6 [P1]** Important experiments are pre-registered (hypothesis + metric +
  stop condition) before running.

## E. Non-goals for the first version (from charter §3.2)
- **N-1** No full autonomous self-redesign.
- **N-2** No unrestricted agent spawning; **N-3** no unbounded lifetimes/budgets.
- **N-4** No permanent fixed hierarchy.
- **N-5** No mandatory agreement before decisions.
- **N-6** No simulated legal system / elaborate governance ritual.
- **N-7** **No** financial, legal, medical, or safety-critical external
  actions. Prototype has **no external side effects at all**.
- **N-8** No model fine-tuning as a prerequisite for learning.
- **N-9** No exposing every private reasoning token.
- **N-10** No custom orchestration framework before evaluating existing tools.
- **N-11** No AGI claim; measurable capabilities only.

## F. Success is NOT measured by (charter §3.3) — guardrails
agent count · message count · debate length · document count · stated
confidence · degree of consensus · dashboard sophistication · self-description
of intelligence · un-independently-verified self-reported improvement.
