# ADR-001 — Navigate capability: convergence + the planner-backend plug point

**Status:** Accepted (design); implementation of the planner-plugin is GATED + DEFERRED.
**Date:** 2026-06-24 · branch `arch/plug-and-play` · loop R6 (S3c-design).
**Context doc:** the plug-and-play refactor (CLAUDE.md North Star + Rule 11 — one shared,
config-parameterized impl per capability, never a per-embodiment fork).

## Context

The round-ladder item "S3c navigate convergence" framed go2 and g1 as having two forked
`navigate` implementations to collapse into one. On analysis (verified by reading the code),
the picture is more precise:

- **The TOOL layer is already converged.** `vcli/native_loop._NativeBaseNavigateTool` is the
  single coordinate-navigation tool. Its `execute` calls `base.navigate_to(x, y, timeout=…)`
  **polymorphically** — there is NO go2-vs-g1 branch in the kernel/tool layer. Rule 11 is
  already satisfied *here*. (Pinned by `tests/unit/embodiments/test_navigate_contract.py`.)
- **The fork is two PLANNER BACKENDS behind one interface:**
  - go2 → `Go2ROS2Proxy.navigate_to(x, y, timeout=60.0, on_progress=None) -> bool` — the
    **external ROS2 CMU FAR planner** routing over the lidar terrain map. (The bare in-process
    `MuJoCoGo2` has NO `navigate_to`; coordinate-nav requires the ROS2 proxy + FAR node.)
  - g1 → `MuJoCoG1.navigate_to(x, y, tol, speed, timeout=None, **_ignored) -> _G1NavResult` —
    an **in-driver visibility-graph planner** (`g1_vgraph`), pure-python, no external process.
  Both honor the polymorphic call shape (`x, y, timeout`; truthy-on-arrival) — g1 carries
  `**_ignored` explicitly "for call-shape compatibility with go2".

These are genuinely *different planning stacks* chosen for genuinely different reasons (go2
ships the full ROS2 nav stack + lidar terrain; g1 is a lighter in-sim planner). They are NOT
accidental duplication of one algorithm.

## Decision

The Rule-11-correct convergence is **NOT** "make both robots use one planner". It is:

> **`navigate` is ONE generic capability (`navigate_to(x, y, timeout) -> truthy`); the PLANNER
> is a pluggable BACKEND selected by the embodiment's `robot.yaml`** — the 5-contract *Capability*
> pattern (bring-your-own planner), exactly as the gait *Policy* is plugged. A driver's
> `navigate_to` becomes a thin generic delegate to the configured planner
> (`planner: far | vgraph | …`); adding a robot or a planner is config + a registered backend,
> never a new per-driver `navigate_to` fork.

So the "one impl" is the generic delegate + the planner registry; the FAR/vgraph backends are
plugged capabilities, not embodiment branches.

## Why this is GATED (and queued, not done this round)

Implementing the planner-plugin touches **interfaces** (CEO gate, per `rules/common/agents.md`):
1. a **Planner protocol** + a planner registry (a NEW INTERFACE the kernel/world contract gains);
2. a `nav`/`planner` field on `EmbodimentConfig` / `robot.yaml` (additive frozen-dataclass field —
   Rule 6 OK on its own, but it co-defines the new interface);
3. formalizing the **external ROS2 FAR planner as a declared external DEP/backend** (dep + the
   nav-interface the audit flagged S3c as gate-adjacent for).

Per loop discipline these are NOT crossed autonomously → queued in `agent-kernel-STATUS.md`
"Pending CEO gates" for Yusen's go/no-go, batched with S8/S4/S5/S6.

## Consequences / recommendation

- **No regression risk today:** the tool layer is already converged + invariant-pinned by a
  contract test; both backends keep working unchanged.
- **YAGNI — defer the planner-plugin until N ≥ 3 planners/embodiments motivate it.** With exactly
  two backends behind a compatible interface, the plugin abstraction earns little and adds an
  interface to maintain. Build it when a 3rd planner (or a bring-your-own-planner developer)
  arrives — that is the moment the abstraction pays for itself and the killer-demo ("drop a robot
  + its planner") needs it.
- **When built:** the generic `navigate_to` delegate + planner registry should live world-side
  (the World's routable capabilities), reusing the `Capability` seam (`vcli/cognitive/capabilities/`)
  and the `EmbodimentConfig` loader — no kernel edit (Rule 11).
