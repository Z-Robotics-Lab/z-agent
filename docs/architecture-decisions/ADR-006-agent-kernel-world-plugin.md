# ADR-006: Agent Kernel / World-Plugin Architecture

- Status: Proposed
- Date: 2026-06-04
- Related: [docs/agent-kernel.md](../agent-kernel.md), ADR-003 (Hardware Abstraction Layer)

## Context

The agentic system (VectorEngine + the VGG cognitive layer + the CLI) is the current
development focus. Two needs converge:

1. The CLI must be usable cross-platform (macOS first). Today the robot/ROS2 stack is
   only ever lazily imported, but the CLI is still coupled to the robot through: an
   undeclared CLI dependency set (`rich`, `prompt_toolkit`), a robot-hardcoded system
   prompt, a VGG decompose gate that returns `None` unless a robot base is connected, and
   a robot-specific decomposer vocabulary.
2. The VGG architecture is differentiated (deterministic per-sub-goal verification,
   inspectable goal graph, measured-strategy selection, experience compilation without
   fine-tuning), but that value is currently expressed only through the robot domain.

A read of `vcli/cognitive/` and `vcli/engine.py` confirms the VGG kernel (decompose ->
verify sandbox -> execute -> retry/re-plan) is already domain-general; the robot coupling
is concentrated in `engine._build_verifier_namespace`, the `GoalDecomposer` vocabulary,
and the CLI startup/prompt.

## Decision

Treat VGG + the engine + general tools + backends + session + permissions as a
**domain-general agent kernel**, and model each domain (robot, code/dev, browser, ...) as
a **world plugin** that registers four things into the kernel:

1. tools (into the existing `CategorizedToolRegistry`, under its own category),
2. a verify/primitive namespace (consumed by `GoalVerifier`),
3. a decompose vocabulary (strategy menu + verify-function names/signatures/
   descriptions/examples used by `GoalDecomposer`),
4. a persona / system-prompt block.

A default `dev`/`code` world ships in the kernel. The robot becomes an optional world
plugin. The kernel never imports a world.

## Consequences

- The CLI can run on macOS as a general verified agent with zero robot dependencies.
- VGG becomes usable over non-robot domains by injecting a non-robot verify namespace and
  decompose vocabulary; the kernel machinery is unchanged.
- The robot stack (`core/agent.py`, `skills/`, `hardware/`, `perception/`, `ros2/`) is
  relocated behind the `robot` world over time; this is migration, not rewrite, because
  the robot deps are already lazy and the engine already tolerates `agent=None`.
- New surface to maintain: the `World` protocol and the default dev world.
- Packaging must be re-tiered (core / sim / perception / ros2 / real) so a base install
  pulls only kernel dependencies.

## Alternatives considered

- **Keep the robot as a load-bearing assumption and add macOS support feature-by-feature.**
  Rejected: it does not unlock the differentiation story and keeps the CLI coupled to a
  body it may not have.
- **Fork a separate general-agent CLI.** Rejected: duplicates the engine and diverges from
  the robot product; the seam already exists and a plugin split avoids a fork.

## Scope of the first increment (Phase A)

Packaging fix; world-selectable persona (general default); the `World` seam + a default
dev world; un-gate VGG from a connected robot; make the `GoalDecomposer` vocabulary
injectable. Code-as-policy execution, verify-as-eval, experience compilation, and
persistent stats are deferred to Phase B (see the design doc).
