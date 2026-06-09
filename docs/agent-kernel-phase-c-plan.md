# Verified Agent Kernel — Phase C Plan (Heterogeneous Model-Zoo Routing)

- Status: **C.1 + C.2 SHIPPED** on `feat/verified-agent-kernel` (keystone (a) taken).
  **C.3 + C.4 await owner sign-off** — C.3 is the actual product (a real specialized model
  in the robot world) and needs embodiment/model/skill-migration decisions (see "Shipped"
  note + open questions 4 & the C.3 keystone).
- Date: 2026-06-04 (updated 2026-06-05)
- Branch: `feat/verified-agent-kernel` (Phase A + Phase B shipped on this branch)
- **Blocked-by (2026-06-05): Phase D precedes C.3.** C.3 (a real specialized model in the
  robot world) requires a robot world whose VGG decomposer reliably produces correct arm-only
  long chains — see [agent-kernel-phase-d-plan.md](agent-kernel-phase-d-plan.md).
- Related: [ARCHITECTURE.md](ARCHITECTURE.md) ("Forward direction: from one LLM to a model
  zoo"), [ADR-006](architecture-decisions/ADR-006-agent-kernel-world-plugin.md).
  Phase B plan is in git history (`git log --all -- docs/agent-kernel-phase-b-plan.md`).
- Note: file:line references are against the current branch (post Phase B); treat as
  approximate anchors, not exact addresses.

## Goal

Generalize the kernel from "route a sub-goal to one of `{skill, primitive, code, tool}`
behind a single chat LLM" to "route a sub-goal to the right **capability** across a
heterogeneous model zoo" — a chat LLM, a specialized detector/segmenter, a planner, a VLA
policy, a classical skill, an atomic action — each with a typed `(input -> output)` contract
and measured stats, chosen by the `StrategySelector` by measured fit. **Verification stays
byte-identical**: every routed step still carries a deterministic `verify` predicate
evaluated in the `GoalVerifier` sandbox, with the existing escalation ladder unchanged.

This is the bridge described in `docs/ARCHITECTURE.md` ("Forward direction: from one LLM to
a model zoo"). Like Phase B, the strategy is **the smallest set of new seams that reuses the
Phase A/B machinery** — we are wiring and generalizing existing dispatch, not greenfield.
Concretely: today `_resolve_explicit` (`strategy_selector.py:196-227`) maps a strategy
*string* to a fixed `executor_type`, and `_execute_strategy` (`goal_executor.py:386-408`)
hardcodes a 4-way `if` over `{skill, primitive, code, tool}`. Phase C makes the *fifth+*
branches (detector, planner, VLA, …) pluggable per world without touching the kernel's
dispatch logic.

macOS / Python 3.12 / uv / ruff / pytest. LLM and any model-zoo backend mocked in all
default tests; new persistence under `~/.vector/`. Robot + MCP + dev stay green at every
stage.

## Shipped (C.1 + C.2)

Keystone **(a)** taken. The capability seam is real and the cross-capability bandit routes:

- **C.1** `feat(kernel): capability seam …` — `cognitive/capabilities/` (`Capability` protocol,
  `CapabilityResult`, `CapabilityRegistry`, `LLMChatCapability` over `create_backend`); one
  `"capability"` executor branch (`goal_executor._execute_capability`); `StrategySelector`
  resolves registered capability names; `World.register_capabilities`; dev registers `chat`
  (+ `"chat"` in `DEV_VOCAB.strategies`/`KNOWN_STRATEGIES`); robot no-op. The invariant is
  tested: invoke-success-but-verify-false ⇒ `StepRecord.success=False`. Side-effecting
  capabilities fail closed (gate deferred to C.3).
- **C.2** `feat(kernel): cross-capability routing …` — `StrategySelector._route` makes the
  navigate/observe/detect keyword rules capability-aware (capability if registered, else the
  classical skill — inert today); the existing `StrategyStats` bandit promotes the
  measured-better capability for a sub-goal pattern with **no schema change**.
- Tests: `tests/vcli/test_level69_capability_seam.py`, `test_level70_capability_routing.py`.
  Robot + dev byte-identical (every injection defaults `None`/empty/no-op).

**C.3 / C.4 NOT started — they need owner decisions** (this is the actual product): which
embodiment + which specialized model(s) to wire (detector/planner/VLA), and whether to
re-express existing skills as capabilities or keep the legacy branch (recommend: keep
legacy, register only net-new model-zoo capabilities). See the C.3 keystone + open
questions 4–5, 7 below.

## KEYSTONE DECISION (resolved for C.1/C.2; C.3 keystone still open)

**Where does the capability `(input -> output)` contract live, and who owns dispatch?**

Today dispatch is a hardcoded `if executor_type == ...` chain inside
`GoalExecutor._execute_strategy` (`goal_executor.py:397-408`), and
`StrategyResult.executor_type` (`strategy_selector.py:62`) is a free string that *both* the
selector and the executor must agree on by convention. Adding a detector/planner/VLA the
same way means editing the kernel's executor for every new capability kind — exactly the
"edit the kernel to add a world capability" coupling Phase A removed for tools/verify/vocab.
So the keystone is a choice of *seam shape*:

- **(a) `Capability` protocol + per-world `CapabilityRegistry`, kernel dispatch stays generic
  [RECOMMENDED].** Define a `Capability` Protocol (`kind`, typed
  `input_schema`/`output_schema`, `cost`/`latency` estimate, `invoke(payload, context) ->
  CapabilityResult`). A world registers concrete capabilities into a `CapabilityRegistry`
  (the way it already registers tools, verify-ns, and vocab — `worlds/base.py:72-95`).
  `GoalExecutor` gains **one** new branch — `executor_type == "capability"` -> look up
  `result.name` in the registry -> `capability.invoke(...)` — replacing the need to ever add
  a 6th, 7th `if`. The existing `{skill, primitive, code, tool}` branches stay as-is for
  backward compatibility. One audited dispatch surface, smallest kernel diff, mirrors the
  Phase B `ToolDispatcher` pattern (`tool_dispatcher.py`: allowlist gate -> lookup -> typed
  invoke -> structured `(success, error)`).

- **(b) Generalize `backends/` into the capability registry.** `backends/create_backend`
  already is a factory returning an `LLMBackend` Protocol. Tempting to make it
  `create_capability(kind, ...)`. **Not recommended as the primary seam**: `backends/` is a
  *chat-LLM* abstraction (`call(messages, tools, system, max_tokens) -> LLMResponse`). A
  detector's contract is `(image, query) -> [bbox]`; a VLA's is `(obs, instruction) ->
  action`. Forcing those through `LLMResponse` is a category error. The chat LLM *becomes
  one capability whose `invoke` wraps the existing `LLMBackend`*, but the capability registry
  is a **new module** (`cognitive/capabilities/`), not a mutated `backends/`.

**Recommendation: (a).** New `cognitive/capabilities/` package (registry + protocol + a thin
`LLMChatCapability` adapter over `create_backend`); one new `"capability"` executor branch;
per-world registration through the existing `World` seam. `backends/` is left intact and
becomes the implementation behind the chat capability.

**Lower-stakes defaults (confirm or override):**

- **Payload carrier:** reuse `SubGoal.strategy_params` (`types.py:24`), as Phase B did for
  tool/code. A capability sub-goal carries `strategy_params = {"capability": "<name>",
  "input": {...}}`. **No new field on `SubGoal`** — keeps the frozen DTO and all serializers
  (template_library, trace_store) untouched.
- **Routing-hint surface:** the decomposer expresses "this wants a detect-capability" by
  emitting `strategy="detect"` (a *capability kind*, not a fixed strategy), gated through the
  same `KNOWN_STRATEGIES` mechanism (`goal_decomposer.py:525-531`) populated per world.
- **Side-effect class:** capabilities declare `side_effecting: bool`. Read-only capabilities
  (detector, planner) need no permission gate; side-effecting ones (a VLA policy that moves a
  robot, a tool) route through `PermissionContext` exactly like `ToolDispatcher`. This
  directly addresses the Phase B finding that a stats-promoted side-effecting capability onto
  a world that lacks it must fail closed, not silently.
- **Stats key:** keep `(strategy_name, sub_goal_pattern)` (`strategy_stats.py:115-116`); make
  `strategy_name` the **capability name** for capability routing. No schema change.

## Current-state findings (grounded)

**Dispatch is a fixed 4-way string switch.** `GoalExecutor._execute_strategy`
(`goal_executor.py:386-408`) reads `executor_type` off the `StrategyResult` and branches
`skill -> primitive -> code -> tool -> fallback`. Each branch is a private method. Adding a
capability kind today means a 5th hand-written branch + a 5th injected handler on `__init__`.
This is the coupling Phase C must break.

**The selector maps a *string* to an `executor_type` by hardcoded convention.**
`_resolve_explicit` (`strategy_selector.py:196-227`): `code_as_policy -> code`, `tool_call ->
tool`, `*_skill -> skill`, `_PRIMITIVE_NAMES -> primitive`, else `-> skill`. The keyword
rules in `select()` (`strategy_selector.py:105-139`) already *want* capability routing —
`detect`/`find`/`check` -> a `detect` strategy, `observe`/`look`/`scan` -> `look` — but they
bottom out in `skill` because there is no detector capability to route to yet. These rules
are the natural insertion point.

**Stats are keyed by `(strategy_name, sub_goal_pattern)` and rank by success rate.**
`get_rankings(pattern)` (`strategy_stats.py:145-158`) returns all strategies for a pattern,
best-first; `_maybe_override_with_stats` (`strategy_selector.py:156-190`) promotes the top
when `attempts >= 3` and `success_rate > 0.5`. **This is already a multi-armed bandit over
strategy *names* per sub-goal pattern.** If a detector and a chat-LLM register names that
resolve to capability dispatch, the *same* ranking machinery chooses between them by measured
fit — **no stats schema change needed**.

**The chat LLM is a single, chat-shaped backend.** `backends/create_backend` returns an
`LLMBackend` whose Protocol is chat-specific. Phase C wraps it as one capability; it does not
generalize it in place.

**The World seam already registers four things; a fifth slots in cleanly.** `World`
(`worlds/base.py:58-95`): `persona_blocks`, `register_tools`, `build_verify_namespace`,
`decompose_vocab`. `DecomposeVocab` already carries `strategies: frozenset[str]` (the exact
`KNOWN_STRATEGIES` gate). Phase B added `tool_call` here (`worlds/dev.py`). A capability
registration is the *same shape*: extend `DecomposeVocab.strategies` + add
`register_capabilities(registry)` to `World`.

**`ToolDispatcher` is the template for a side-effecting capability invoke.**
`tool_dispatcher.py`: allowlist gate -> registry lookup -> `PermissionContext.check` ->
ask-resolution (deny-by-default) -> `tool.execute` -> structured `(success, error)`. A
side-effecting `Capability.invoke` follows this exact contract; a read-only capability skips
the permission gate. The `(bool, str)` return `_execute_strategy` expects is already what
every branch produces.

**Verify is fully decoupled from execution.** `_execute_sub_goal` (`goal_executor.py`) runs
`_execute_strategy`, then *separately* calls `self._verifier.verify(sub_goal.verify)`. The
verifier (`goal_verifier.py:94-153`) only sees the `verify` string + the namespace — it has
**zero knowledge** of which executor ran. Visual escalation and `fail_action` fallback sit
entirely on the verify side. **Capability routing cannot touch verification** — it is on the
other side of the `_execute_strategy`/`verify` seam.

## Design

### 1. Capability abstraction

New package `vector_os_nano/vcli/cognitive/capabilities/`:

```python
# capabilities/types.py
@dataclass(frozen=True)
class CapabilityResult:
    success: bool
    output: dict[str, Any] = field(default_factory=dict)  # typed per capability
    error: str = ""
    cost_usd: float = 0.0
    latency_sec: float = 0.0

@runtime_checkable
class Capability(Protocol):
    name: str            # registry key + stats strategy_name (e.g. "detect", "grasp_planner")
    kind: str            # "chat" | "detector" | "planner" | "vla" | "skill" | "atomic"
    side_effecting: bool # True -> route invoke through PermissionContext
    input_schema: dict
    output_schema: dict
    def estimate(self, payload: dict) -> tuple[float, float]: ...  # (cost_usd, latency_sec)
    def invoke(self, payload: dict, context: Any) -> CapabilityResult: ...
```

We add exactly **one** new `executor_type`: `"capability"`. `_resolve_explicit` returns
`StrategyResult("capability", name, params)` for any capability-kind strategy; `_execute_strategy`
gains one branch:

```python
if executor_type == "capability":
    return self._execute_capability(name, params)
```

`_execute_capability` looks the name up in the injected `CapabilityRegistry`, validates
`params["input"]` against `input_schema`, gates on `PermissionContext` **iff**
`capability.side_effecting`, calls `invoke`, returns `(result.success, result.error)`. The
four existing branches are **unchanged**, so robot + dev stay byte-identical when no
capability sub-goal is produced.

`backends/` stays a *chat-LLM* abstraction; the chat LLM becomes one registered capability
via a thin adapter:

```python
# capabilities/chat.py
class LLMChatCapability:
    name = "chat"; kind = "chat"; side_effecting = False
    def __init__(self, backend: LLMBackend): self._backend = backend
    def invoke(self, payload, context) -> CapabilityResult:
        resp = self._backend.call(payload["messages"], payload.get("tools", []), ...)
        return CapabilityResult(success=True, output={"text": resp.text},
                                cost_usd=_usd(resp.usage), latency_sec=...)
```

```
StrategySelector.select(sub_goal)
   -> StrategyResult(executor_type="capability", name="detect", params={"input": {...}})
GoalExecutor._execute_strategy            (one new branch; existing 4 untouched)
   -> _execute_capability(name, params)
        -> CapabilityRegistry.get("detect")  -> Capability
        -> validate params["input"] vs input_schema
        -> if side_effecting: PermissionContext.check(...)   (reuses tool_dispatcher gate)
        -> capability.invoke(input, context) -> CapabilityResult
        -> return (result.success, result.error)
   ... then UNCHANGED: verifier.verify(sub_goal.verify)   [the invariant]
```

### 2. Registration

Extend `World` (`worlds/base.py:58-95`) with one optional method, mirroring `register_tools`:

```python
def register_capabilities(self, registry: Any, agent: Any) -> None:
    """Register this world's routable capabilities into the CapabilityRegistry.
    Dev registers `chat`; robot registers detectors/planners/VLA policies/skills.
    Default: no-op (kernel keeps the built-in skill/primitive/code/tool branches)."""
```

`DecomposeVocab.strategies` is *already* the `KNOWN_STRATEGIES` gate; capability kinds go in
here exactly as `tool_call` did for dev. The world's `register_capabilities` and its
`DecomposeVocab.strategies` must agree (a capability the decomposer can name must exist in
the registry) — a startup assertion catches drift.

- **Dev world** keeps `tool_call`; optionally registers `chat` so a sub-goal can route to the
  LLM. The `file_write`-via-`tool_call` path is untouched.
- **Robot world** is where a **specialized detector gets declared**. C.3 gives
  `RobotWorld.register_capabilities` registering, e.g., a read-only `DetectorCapability`
  backed by the perception stack, a `GraspPlannerCapability`, a `VLACapability(side_effecting
  =True)`, plus existing skills. Until C.3, robot returns the same `None`/no-ops it does
  today — no robot regression. Models load lazily inside `invoke` (no heavy import at module
  load) and are config/env-driven, never hardcoded.

`engine.init_vgg` builds one `CapabilityRegistry`, calls `world.register_capabilities`, and
passes it to `GoalExecutor` as a new `capability_registry=None`-defaulted arg (same pattern
as `code_executor`/`tool_dispatcher`). `None` default => the capability branch is inert =>
robot/dev byte-identical when no capability is registered.

### 3. Routing

Make **`strategy_name` carry the capability name** for capability routing. Then a sub-goal
pattern like `detect_*` accumulates records for *every* capability tried on it —
`("detect", "detect_*")`, `("chat", "detect_*")`, `("yolo_detector", "detect_*")`.
`get_rankings("detect_*")` already returns these best-first, and `_maybe_override_with_stats`
already promotes the winner — **the cross-capability bandit, for free, no stats schema
change.**

Localized changes in `strategy_selector.py`:

1. **`_resolve_explicit` learns capability kinds.** Add, before the `_skill` suffix check: if
   `strategy` is a registered capability kind/name (the selector holds the registry key set,
   injected like `stats`), return `StrategyResult("capability", strategy, params)`. The
   `code_as_policy`/`tool_call` special-cases stay.
2. **Keyword rules emit capability kinds where a capability exists.** The `detect` rule
   becomes: if a `detect` capability is registered, route to it; else the current `skill`
   result (back-compat). No new keywords.
3. **`_maybe_override_with_stats` is unchanged.** It calls
   `_resolve_explicit(top.strategy_name, ...)`; since that now resolves capability names, a
   stats-promoted capability routes correctly with zero change.

The decomposer names a capability *kind* (`strategy="detect"`), gated by
`DecomposeVocab.strategies` so `KNOWN_STRATEGIES` doesn't silently clear it (the exact
omission Phase B caught for `tool_call`). **The decomposer names a kind, not a specific
model** — picking which detector is the *selector's* job via stats, keeping model choice out
of the LLM-authored plan. Cold-start: the rule layer's kind -> default-capability mapping is
the prior; stats override only after `>= 3` attempts and `> 0.5` success.

### 4. Verification invariant (unchanged)

The deterministic predicate + escalation ladder is provably untouched: `_execute_sub_goal`
runs `_execute_strategy` and **then independently** calls `self._verifier.verify(...)`. The
verifier takes only the `verify` string + namespace; it has no awareness of which capability
ran. The escalation ladder (deterministic -> visual override, still flagged
`visual_override=True` so it is *not* deterministic evidence per the Phase B fix ->
`fail_action` re-verify) reads no `executor_type`. Every routed capability step still carries
a `verify` predicate (a required field on `SubGoal`); the *predicate*, not the capability's
self-report, decides success.

**Invariant test (C.1 gate):** a capability sub-goal whose `invoke` returns `success=True`
but whose `verify` predicate is false must produce `StepRecord.success=False` — proving the
capability cannot self-certify around the verifier.

### 5. Migration / staging

Mirrors the B.1/B.2 split: each stage independently shippable; robot + MCP + dev green
throughout; new injections default `None`/no-op.

**C.1 — Capability seam (kernel-side, dev-only proof), zero new model.**
1. `cognitive/capabilities/`: `Capability` Protocol + `CapabilityResult` (`types.py`),
   `CapabilityRegistry` (get/register/keys, boundary input-schema validation),
   `LLMChatCapability` adapter over `create_backend` (`chat.py`).
2. `goal_executor.py`: add `capability_registry=None` to `__init__`; add `_execute_capability`;
   one branch in `_execute_strategy` before the fallthrough; side-effecting capabilities reuse
   the `ToolDispatcher`-style permission gate.
3. `strategy_selector.py`: inject the registry key set; resolve a registered capability name ->
   `StrategyResult("capability", name, params)`.
4. `worlds/base.py`: add `register_capabilities`; `worlds/dev.py` registers `chat`, adds the
   kinds to `DEV_VOCAB.strategies` + the `KNOWN_STRATEGIES` gate.
5. `engine.init_vgg`: build `CapabilityRegistry`, call `world.register_capabilities`, pass to
   `GoalExecutor`.
6. Tests `tests/vcli/test_level69_capability_seam.py`: a dev `chat` capability routes +
   verifies; invoke-success-but-verify-fail => `success=False` (invariant); unregistered name
   fails closed.

**Keystone gate for C.1:** owner signs off on **(a)** before any code.

**C.2 — Cross-capability routing by measured fit.**
7. Ensure `step.strategy` records the capability name through `goal_executor` stats recording.
8. Keyword rules emit capability kinds when registered; `_maybe_override_with_stats` unchanged.
9. Tests `tests/vcli/test_level70_capability_routing.py`: two mocked `detect_*` capabilities;
   3+ attempts favoring one => selector promotes it; `strategy_stats.json` schema unchanged.

**C.3 — Robot world registers a model-zoo capability (the product).**
10. `worlds/robot.py:register_capabilities`: a perception-backed read-only `DetectorCapability`
    (+ optional `GraspPlanner`, `VLACapability(side_effecting=True)` gated by `PermissionContext`
    + confirmation).
11. Robot `DecomposeVocab` optionally gains capability kinds; until then robot routes via
    skills/primitives unchanged.
12. Tests (mujoco-gated): a `detect` sub-goal routes to the detector; verify unchanged;
    existing level45/46/54/56 + mujoco e2e green.

**C.4 — Cost/latency-aware tiebreak + persistence polish (optional).**
13. Use `Capability.estimate` as a cold-start prior/tiebreak; persist measured cost alongside
    success rate (extend `StrategyRecord` with a tolerant loader, per the Phase B serializer
    pattern).

**Keystone decisions needing owner sign-off:** C.1 protocol shape ("one branch,
registry-driven, `backends/` intact"); C.3 whether existing skills are re-expressed as
capabilities or kept on the legacy branch (recommend: keep legacy, register only new
model-zoo capabilities — smaller diff, zero robot regression).

## Success criteria

- **C-1:** a dev `chat` capability sub-goal routes through `_execute_capability` and is gated
  by its `verify` predicate; invoke-success-but-verify-fail is recorded `success=False`; an
  unregistered capability name fails closed.
- **C-2:** two capabilities competing on one `*_*` pattern: after `>= 3` attempts favoring
  one, `StrategySelector` promotes it via the unchanged `get_rankings`; `strategy_stats.json`
  schema is byte-unchanged.
- **C-3:** a robot world registers a real detector; a `detect_*` sub-goal routes to it and is
  verified deterministically; robot VGG harness (level45/46/54/56, mujoco e2e) + MCP + all
  dev/eval tests stay green.
- **Global:** every new injection defaults `None`/no-op, so robot and dev paths are
  behaviorally identical when no capability is registered — the Phase B safety bar.

## Risks & non-goals (honest)

- **The LLM still authors the routing hint.** The decomposer names a kind and the predicate.
  *Mitigation:* the LLM names a *kind*, not a model — model choice is the measured layer; the
  predicate, not the capability's self-report, decides success. Subjectivity moved from
  "which model" to "which kind," not eliminated.
- **Cold-start before stats exist.** With `< 3` attempts, routing falls back to the rule
  prior. *Mitigation:* sensible per-world default per kind; optional `estimate()` tiebreak
  (C.4). Don't overclaim optimal routing from step one.
- **Cost of wrong routing for side-effecting capabilities — the Phase B finding generalized.**
  A mis-promoted side-effecting capability (a VLA moving a robot) is a *physical action*, not
  just a failed step. *Mitigation, load-bearing:* (1) side-effecting capabilities route
  through `PermissionContext` + confirmation like `ToolDispatcher`; (2) stats are recorded
  **per world** (extending the Phase B dev-only scoping) so a dev capability can never promote
  onto a robot world; (3) a capability absent from the world's registry fails closed before
  invoke. Read-only capabilities carry none of this risk.
- **Schema drift between `DecomposeVocab.strategies` and the registry** — the
  `KNOWN_STRATEGIES`-clearing trap of Phase B. *Mitigation:* a startup assertion that named
  capability kinds ⊆ registry keys.
- **Novelty — do not overclaim.** "Route a sub-goal to the right capability across a
  heterogeneous zoo, verified per step" is engineering synthesis, not a new primitive. Prior
  art: model/tool routing (RouteLLM, FrugalGPT), bandits for model selection, hierarchical
  skill libraries (Voyager). The defensible contribution remains the *conjunction*:
  deterministic per-step verification + measured cross-capability routing + verified template
  compilation, in one fine-tuning-free runtime. Keep external claims hedged.

**Non-goals:** not building or fine-tuning any model (capabilities wrap existing brains); not
rewriting `backends/` (chat LLM stays a chat backend, wrapped as one capability); not
re-expressing the existing `skill`/`primitive`/`code`/`tool` branches as capabilities in
C.1–C.3 (only net-new model-zoo capabilities use the new branch); not driving real robot
hardware from macOS (specialized-model capabilities run in the robot world on Linux; the
dev-world `chat` capability is the macOS proof).

## Open questions for the owner

1. **Keystone:** confirm **(a)** `Capability` protocol + `CapabilityRegistry` + one
   `"capability"` executor branch, `backends/` left intact (recommended).
2. **Payload carrier:** reuse `SubGoal.strategy_params = {"capability","input"}` (recommended)
   vs a new typed `payload` field on `SubGoal`.
3. **Routing-hint granularity:** decomposer names a capability *kind* and stats pick the model
   (recommended) vs the decomposer naming a specific capability.
4. **Skill migration:** keep `skill`/`primitive` on their legacy branches and register only
   new model-zoo capabilities (recommended, zero robot regression) vs re-express skills.
5. **Side-effecting capability gate:** confirm side-effecting capabilities route through
   `PermissionContext` + confirmation, read-only ones do not (recommended).
6. **PR split C.1 / C.2 / C.3 / C.4** (recommended yes).
7. **Stats scoping:** confirm capability stats stay **per world** (extending the Phase B
   dev-only scoping) so a dev capability can never promote onto a robot world.
