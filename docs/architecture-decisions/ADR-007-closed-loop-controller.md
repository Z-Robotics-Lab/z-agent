# ADR-007: From Open-Loop Compiler to Grounded Closed-Loop Controller

- Status: Accepted — staged delivery in progress on `feat/verified-agent-kernel`
- Date: 2026-06-06
- Related: [docs/agent-kernel-STATUS.md](../agent-kernel-STATUS.md), ADR-006 (Agent Kernel / World-Plugin Architecture)

## Context

A deep code probe of the VGG stack revealed that despite its sophisticated vocabulary
(GoalTree, GoalVerifier, StrategySelector, experience compilation), the system was
behaving as an **open-loop compiler**:

- Goals are decomposed into a frozen DAG up front; the DAG is never revised mid-run
  from what actually happened.
- Step outputs (return values, side-effects, sensor readings) are not stored anywhere
  accessible to downstream steps or the replanner; observations are discarded at every
  junction.
- Almost every routing decision (strategy selection, retry, replan trigger) is driven by
  keyword matching on strings, not on structured understanding of the world state. The
  single real-understanding site is the decomposer LLM call.
- The decompose vocabulary is split-brained: the Go2 robot world supplies a separate
  vocabulary from the skill registry, producing a divergent action space that can
  hallucinate skills the kernel does not actually know how to execute.
- Plan execution is blind: the verify step returns a boolean pass/fail but the failure
  value and the step's output are not threaded back into replanning context.

This architecture cannot support the north-star goal of powerful NL decomposition
followed by long-chain planning that adapts to what the robot (or dev-world) actually
observes. The open-loop property is the root cause, not a surface symptom.

## Decision

Re-architect the VGG stack from a blind one-shot compiler into a **grounded closed-loop
controller**, via five complementary bets applied in stages:

**Bet 1 — Close the observation loop.**
Make observations first-class: a per-run `Blackboard` stores every step's structured
output; GoalVerifier returns `(bool, raw_value)` instead of a bare boolean; each
`StepRecord` carries `result_data`; the VGGHarness rebuilds `world_context` from the
Blackboard before every (re)decompose call. Parameter binding in plan nodes uses safe
`${step.output.path}` references resolved by pure dict/list traversal, not f-strings
over arbitrary data.

**Bet 2 — Plan as a living, incremental program.**
Introduce a control-flow IR (`foreach`, `until`, `if`) so the planner can express
iteration and branching without hardcoding loop counts. Wire observation-driven
mid-tree replan: when a step fails or a verify check returns a structured signal, the
harness re-decomposes the affected subtree using current `world_context`, not the stale
context from T=0.

**Bet 3 — Single-source the action space from the registry.**
Generate the decompose vocabulary directly from the skill registry
(`vocab_from_registry.build_decompose_vocab`), gating base primitives on `has_base`.
Eliminate the Go2 split-brain vocabulary and all keyword sieves for strategy and
primitive lookup. Add fail-loud validation: `GoalTree.validation_notes` is injected
into replan context so the LLM sees its own prior failures.

**Bet 4 — Ground the planner.**
Introduce structured perception that populates `world_context` with typed facts (object
positions, affordances, arm state). Add referring-expression resolution so the planner
can refer to "the red cup on the left" and get a stable identifier, not a free-text
string that breaks mid-chain. Wire real `detect`/`describe` outputs and arm predicates;
maintain an `ObjectMemory` that stays coherent across steps.

**Bet 5 — Unify the two planning paths.**
Today VectorEngine and the VGGHarness are separate planning paths that can diverge.
Merge them into a single closed-loop controller that owns the full
decompose → plan → execute → verify → replan cycle with a unified observation store.

### Forks locked

- **Foundation-first:** the SO-101 arm is the primary touchstone for correctness; all
  mechanisms are designed world-agnostic (Dev world exercises the same code paths on a
  laptop).
- **Keep GoalTree + verify:** the deterministic per-sub-goal verification and inspectable
  goal graph are the differentiated moat. This ADR makes them closed-loop and
  incremental, not removes them.

## Consequences

**Staged delivery.** Each stage is a shippable increment that leaves all tests green:

```
Stage 0  Visible sim — mjpython re-exec, --headless opt-out (window by default) [SHIPPED]
Stage 1  Close the loop — Blackboard, result_data, verify returns value,
         world_context refresh                                         [SHIPPED]
Stage 2  Single-source vocab + fail-loud — vocab_from_registry, kill split-brain,
         GoalTree.validation_notes in replan                          [SHIPPED]
Stage 3  Grounding — structured perception, referring-expression resolution,
         wire real detect/describe, arm predicates, ObjectMemory re-sync
Stage 4  Control-flow IR — foreach/until/if + observation-driven mid-tree replan;
         unlocks "grasp all objects" end-to-end
Stage 5  Unify planning paths — single closed-loop controller
Stage 6+ Learning-loop v2, C.3 model zoo (after the loop is closed)
```

**Preserved invariants.** The world-plugin seam from ADR-006 is unchanged: the kernel
still never imports a world; worlds still register exactly tools, verify namespace,
decompose vocabulary, and persona. The closed-loop machinery is kernel-internal.

**New surface.** `Blackboard` (per-run observation store), `StepRecord.result_data`,
the `vocab_from_registry` builder, and the control-flow IR nodes are new public
surfaces that must be kept stable across stages.

**C.3 model zoo is gated.** The per-skill fine-tuned model routing (Phase C.3) depends
on a closed loop that can generate reliable training signal. It is deferred until
Stage 5 is complete.

## Alternatives considered

- **Patch keyword matching incrementally.** Rejected: the root cause is the open-loop
  property; patching routing heuristics does not close the loop and accumulates
  technical debt at every junction.
- **Abandon GoalTree and replace with a pure ReAct / scratchpad agent.** Rejected: the
  deterministic verify moat and the inspectable goal graph are core to the product
  thesis; a flat ReAct loop discards both.
- **Rebuild from scratch with a new engine.** Rejected: the kernel/world seam (ADR-006),
  the verify sandbox, and the experience compilation are already sound; a clean rebuild
  risks losing them and delays delivery.
