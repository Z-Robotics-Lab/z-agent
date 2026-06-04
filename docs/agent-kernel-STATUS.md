# Verified Agent Kernel — STATUS (resume anchor)

One-page "where are we / what's next" for the agent-kernel line of work. Read this first
when resuming; the detailed plans are linked at the bottom.

- Branch: `feat/verified-agent-kernel` (pushed; tip `48c208b`). Base: `master`. No PR yet.
- Last updated: 2026-06-04.
- Scope guard: this is **vector-os-nano only** — not the UniLab go2arm-grasp work.

## Shipped (on the branch, pushed)

- **Phase A** — kernel/world decoupling; `vector-cli` boots robot-free on macOS
  (decompose + verify). `vcli/worlds/` (World protocol, DevWorld, RobotWorld shim).
- **Phase B.1** `80916f4` — dev world *acts*: `tool_call` sub-goals dispatch real tools
  through `ToolDispatcher` (allowlist + `PermissionContext`); code-as-policy AST sandbox;
  verify-as-eval (`cognitive/trace_store.py`: save/load/replay + evidence gate); the
  `vector-eval` headless harness.
- **Phase B.2** `f5b9eb4` — persistent `StrategyStats` (atomic, `~/.vector/`) + experience
  compilation → template reuse (no-LLM fast path), `strategy_params` carried through.
  Persistence is opt-in (`init_vgg(persist_dir=...)`); dev-world only (robot byte-identical).
- **Hardening** `8e961f8` — fixed all 17 confirmed findings from a multi-agent adversarial
  review (intrinsic tool deny beats `--no-permission`; write-path dangerous-path guard;
  code sandbox strips `tests_pass`; visual-override not counted as evidence; concrete
  `tool_call` templates need a full-name match; word-boundary param substitution; …).
- **e2e suite restored** `bee46f7` — `tests/integration/vcli/test_end_to_end.py` rewired to
  the `LLMBackend` abstraction (was dead since the backends refactor); 10/10 green.
- **Phase C.1** `62fcfc1` — the capability seam: `cognitive/capabilities/` (`Capability`
  protocol, `CapabilityRegistry`, `LLMChatCapability` over `create_backend`); one
  `"capability"` executor branch; `World.register_capabilities`; dev registers `chat`. The
  invariant is tested: a capability whose `invoke()` succeeds but whose `verify` predicate
  is false ⇒ `StepRecord.success=False` (no self-certifying). Side-effecting caps fail closed.
- **Phase C.2** `2a7c942` — cross-capability routing: `StrategySelector._route` makes the
  navigate/observe/detect keyword rules capability-aware (inert until a capability is
  registered); the existing `StrategyStats` bandit promotes the measured-better capability
  for a sub-goal pattern, with no schema change.

Tests: kernel-only tests live in `tests/vcli/` (level63–70) — robot-free, run on macOS with
zero robot deps. Run: `cd ~/vector-os-nano && .venv-nano/bin/python -m pytest tests/vcli -q`.
All green; robot harness + MCP unaffected (every new injection defaults `None`/no-op).

Known pre-existing red tests (NOT from this work): `tests/integration/test_sensors_against_world.py`
(needs `MUJOCO_GL`).

## Next — needs owner decisions (paused)

- **Phase C.3 (the actual product)** — register a **real specialized model** in the robot
  world. Three decisions before coding:
  1. Which embodiment first (Go2 / SO-101 / Piper)?
  2. Which model(s) to wire (detector / planner / VLA) and from which perception stack?
  3. Re-express existing skills as capabilities, or keep the legacy `skill`/`primitive`
     branch and register only net-new model-zoo capabilities? (Recommend: keep legacy.)
  Side-effecting capabilities (e.g. a VLA that moves the robot) route through
  `PermissionContext` + confirmation (already designed; gate is the C.3 work).
- **Phase C.4 (optional)** — cost/latency-aware tiebreak; persist measured cost. Thin until
  real capabilities exist to measure.
- **Deferred B follow-ups** (noted in `8e961f8`): incremental experience compilation
  (currently a bounded O(n) recompile per success); full cwd-containment for the autonomous
  write path.
- **Owner actions:** open a PR (`base = master`); decide C.3 direction.

## Pointers

- Direction / vision: [agent-kernel.md](agent-kernel.md)
- Phase B plan + shipped notes: [agent-kernel-phase-b-plan.md](agent-kernel-phase-b-plan.md)
- Phase C plan (C.1/C.2 shipped, C.3/C.4 open): [agent-kernel-phase-c-plan.md](agent-kernel-phase-c-plan.md)
- ADR: [architecture-decisions/ADR-006-agent-kernel-world-plugin.md](architecture-decisions/ADR-006-agent-kernel-world-plugin.md)
