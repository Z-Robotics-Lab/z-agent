# ADR-008: Playground as a Separate, Parallel Development Track via the Seam-as-Contract

- Status: Accepted — 2026-06-06
- Date: 2026-06-06
- Related: [docs/ARCHITECTURE.md](../ARCHITECTURE.md), ADR-006 (Agent Kernel / World-Plugin Architecture), ADR-007 (Closed-Loop Controller), [docs/agent-kernel-STATUS.md](../agent-kernel-STATUS.md)

## Context

Vector OS Nano needs a **carrier** to play and test the agentic system on, and a
**vehicle** to open-source and promote it: a "playground" where you open a world, an
agent is waiting, you type natural language ("put a Go2 in the kitchen and have it pick
everything up"), and the agent enters a preset scene and takes over long-chain planning +
execution — with the **verified closed loop visible** (goal tree + per-step verify +
replan), not just a robot moving. A normal sim shows a robot move; this must show "one
sentence -> a verifiable plan that self-corrects."

The open question was structural: build the playground in-tree (extract later) or as a
separate project — and in what order relative to the agentic kernel. The owner's goal is
**parallel development**: the playground and the kernel should advance independently.

The constraint is that the kernel/world seam (ADR-006) is real but still **partly molten**.
A fresh code probe confirmed: the robot verify namespace is built kernel-side
(`engine._build_verifier_namespace`, with `detect_objects`/`describe_scene` as `[]`/`""`
stubs), `RobotWorld.build_verify_namespace()` returns `{}`, and world selection is a
hardcoded binary (`resolve_world(agent) -> RobotWorld | DevWorld`) with no notion of
scenario or embodiment. Building a separate track against a molten internal seam risks
constant version-skew.

## Decision

Develop the **playground as a separate, parallel track** from the agentic kernel, and make
the **kernel/world seam the versioned public contract** the two tracks integrate across.
The seam already carries the four registrations (tools, verify namespace, decompose vocab,
persona); we extend it with a **verified-loop observation surface** — the kernel exposing
each run's `GoalTree`, per-step `StepRecord` (`success` / `verify_result` / `result_data`),
and replan `validation_notes` as structured, inspectable data a front-end can render.

**Parallelism is enabled by the contract, not by physical separation.** The two tracks meet
only at the contract:

- **Kernel track** — the closed-loop stages of ADR-007 (grounding, control-flow IR, unify
  paths), behind the contract.
- **Playground track** — preset scenes / embodiments / tasks registered as worlds, NL entry
  into a scene, and the view that renders the verified loop, in front of the contract.

### Forks locked

- **Separate track, via the seam contract** — not in-tree-only, and not a black-box
  integration over MCP. The playground depends on the kernel's public world-plugin API plus
  the verified-loop observation surface.
- **Preset scenes for v1 (a catalog entered via NL)** — the agent fully owns the long chain
  once inside; dynamic scene assembly (MjSpec composition) is deferred. The arm's existing
  `so101_mujoco.xml` (table + 6 graspable objects) is the first preset scene.
- **Deterministic sim-oracle grounding for verify; VLM perception for "seeing."** The verify
  predicate reads MuJoCo ground truth (`get_object_positions` / `get_joint_positions` / `fk`)
  so it stays deterministic (ADR-006 / the verify invariant); the VLM `detect`/`describe`
  pipeline remains the agent's perception skill. This keeps the generator (perceive) and the
  verifier (check) independent — the project's generator-verifier-gap thesis.

## Consequences

**A shared prelude comes first (not parallelizable).** Both tracks build against the
contract, so it must exist before they diverge:

1. World verify namespace owned by the world (migrate `engine._build_verifier_namespace` ->
   `World.build_verify_namespace`), so the playground track owns its predicates. This is the
   same refactor as ADR-007 Stage 3 grounding wearing a seam hat.
2. `resolve_world` -> a world/scenario registry (worlds discovered, not hardcoded).
3. The verified-loop observation surface exposed as stable structured data.

**Cross-track rendezvous.** The flagship "visible self-correcting long chain" needs the
kernel track's grounding (Stage 3) + control-flow IR (Stage 4) AND the playground track's
view. The tracks run in parallel but the marquee milestone gates on both — guard against the
playground becoming a pretty shell ahead of grounding.

**Extraction ladder.** The playground track starts as a clean, one-way-dependency package
(`playground -> kernel`, never reverse; heavy assets pulled via dependencies, never vendored
into git) and graduates to its own repo at the public-launch milestone, once the contract has
been stable for a release. The physical split tracks the contract's stability, not the
calendar.

**Preserved invariants.** ADR-006 holds: the kernel never imports a world. ADR-008 only
elevates the seam from an internal convenience to the explicit, versioned contract between
tracks, and names the observation surface as part of it.

## Alternatives considered

- **In-tree first, extract later (the prior recommendation).** Reasonable and lower-risk, but
  it does not give the playground its own identity / onboarding early, which the owner wants
  for the open-source push. Superseded by making the seam an explicit contract, which makes a
  separate track safe without paying the molten-seam tax — provided the shared prelude is done
  first.
- **Black-box integration over the MCP server only.** Rejected for v1: a request/response MCP
  boundary risks flattening the verified-loop observation surface (goal tree + per-step verify
  + replan events), which is exactly what the playground must render. The MCP path remains
  available as an additional, looser entry point, not the primary integration.
- **Keep everything in one track; build the playground after the loop closes.** Rejected:
  forgoes parallelism and delays the carrier/testbed and the open-source vehicle the owner
  wants now.
