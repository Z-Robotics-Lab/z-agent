# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""native_loop — a frontier-model NATIVE TOOL-USE turn producer (strangler-fig core).

Campaign #13, M1 FIRST STEP. This is the producer half of the strangle move: the
MODEL drives a native tool-use ReAct loop (skills-as-tools + a synthetic
``verify(expr)`` + ``finish``), and the loop assembles an ``ExecutionTrace`` the
EXISTING honest verify spine consumes BYTE-FOR-BYTE UNCHANGED. It does NOT compute
``verified`` itself — it hands the trace to ``VerdictReport.from_trace`` /
``evidence_passed`` (rule 5: verify is the moat, single-sourced).

REPLACE-NOT-REBUILD, enforced BY CONSTRUCTION (review fix 5):

    This module imports ONLY the honest spine — ``actor_causation``,
    ``trace_store`` (the verdict + oracle names live one hop further), the
    GoalVerifier namespace builder (via the engine, passed in), and
    ``SkillWrapperTool``. It MUST NOT import ``goal_decomposer`` / ``goal_executor``
    / ``strategy_selector`` / ``vgg_harness``. ``tests/unit/vcli/test_native_loop
    _import_firewall.py`` FAILS if any of those appear in this module's imports.
    The runner's ONLY logic is: capture baseline -> dispatch the skill via
    SkillWrapperTool -> evaluate verify via the live GoalVerifier -> grade via
    ``actor_causation.grade`` -> append ONE StepRecord. The MODEL owns
    decompose / route / replan — there is NO replan / iteration / "landed-short"
    bookkeeping here (that would be re-growing the planner — the tell).

StepRecord granularity (review fix 2): EXACTLY ONE StepRecord per
(action-chain -> verify) pair. Intermediate bare skill calls between two
``verify`` calls are NOT each a checked sub-goal and are NOT sentinel-verified
(that would re-open the no-op/teleport hole). The ``verify`` tool HANDLER is what
appends the StepRecord, binding the just-run skill calls as the producing action
and the model's expr as the SubGoal.verify.

Capture/grade timing (review fix 3), mirroring ``GoalExecutor._execute_sub_goal``:
the actor-causation baseline is captured immediately BEFORE the first skill call
of a step; the grade reads a FRESH post-capture immediately AFTER evaluating that
step's verify expr, NEVER spanning a later step's actions (else the go2 daemon's
between-turn motion folds into the causation grade).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from vector_os_nano.vcli.backends.types import LLMResponse
from vector_os_nano.vcli.cognitive import actor_causation
from vector_os_nano.vcli.cognitive.trace_store import verify_oracle_names
from vector_os_nano.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)
from vector_os_nano.vcli.tools.base import ToolContext, ToolResult
from vector_os_nano.vcli.tools.skill_wrapper import wrap_skills

logger = logging.getLogger(__name__)

# Synthetic tool names the runner OWNS (never wrapped from a skill).
VERIFY_TOOL = "verify"
FINISH_TOOL = "finish"

# A hard cap on native round-trips so a misbehaving model / script can never spin
# forever. Mirrors the engine's _max_turns spirit; the loop also stops on finish.
_MAX_NATIVE_TURNS = 24

# The registry category whose tools are the kernel's domain-general ACTION surface
# (file_read/file_write/file_edit/bash/glob/grep — see tools.__init__._TOOL_CATEGORIES
# and worlds.dev.DEV_TOOL_ALLOWLIST, which is this category). The native loop offers
# these as motor tools alongside the world's skills, so the dev world (no robot agent,
# hence no wrapped skills) can still ACT — and the robot world gains the same code
# tools. World-agnostic BY CONSTRUCTION: native asks the ENGINE'S registry for its
# registered action tools; there is NO "if dev" branch.
_CODE_TOOL_CATEGORY = "code"

# at_position tolerance (metres) — single-sourced for the system-prompt vocab from
# the go2 oracle so the model's verify expr and the verifier agree. Read live with
# a safe fallback so this module never hard-depends on the oracle's private const.
def _at_position_tol() -> float:
    try:
        from vector_os_nano.vcli.worlds.go2_sim_oracle import _AT_POSITION_TOL_M
        return float(_AT_POSITION_TOL_M)
    except Exception:  # noqa: BLE001
        return 0.5


# ---------------------------------------------------------------------------
# Synthetic tool schemas (the verify/finish/motor tool-set the model is offered)
# ---------------------------------------------------------------------------


def _verify_tool_schema(oracle_names: frozenset[str]) -> dict[str, Any]:
    """Anthropic-shaped schema for the synthetic ``verify(expr)`` tool.

    The description single-sources the registry-derived verify vocab (the live
    oracle names + the ``at_position`` tol semantics) so the model's verify expr is
    grounded in the SAME namespace ``verify_oracle_names`` reads (review fix 6).
    """
    names = ", ".join(sorted(oracle_names)) if oracle_names else "(none)"
    tol = _at_position_tol()
    desc = (
        "Check a deterministic post-condition predicate against real world state, "
        "then bind it as this step's verification. Call this AFTER the action skill(s) "
        "that should have achieved the goal. The predicate is evaluated by an "
        "independent verifier over real sensor/sim ground truth — it cannot be faked. "
        f"Available predicate oracles: {names}. "
        f"at_position(x, y, tol={tol}) is True when the robot's planar position is "
        f"within tol metres of (x, y) (tol defaults to {tol}). "
        "Pass the FULL predicate as 'expr', e.g. at_position(2.0, 0.0)."
    )
    return {
        "name": VERIFY_TOOL,
        "description": desc,
        "input_schema": {
            "type": "object",
            "properties": {
                "expr": {
                    "type": "string",
                    "description": "The deterministic verify predicate to evaluate.",
                }
            },
            "required": ["expr"],
        },
    }


def _finish_tool_schema() -> dict[str, Any]:
    return {
        "name": FINISH_TOOL,
        "description": (
            "Signal the task is complete. Call this once every step has been "
            "executed and verified."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    }


# ---------------------------------------------------------------------------
# NativeStepRunner — the ONLY stateful piece (capture -> dispatch -> verify -> grade)
# ---------------------------------------------------------------------------


class NativeStepRunner:
    """Assemble an ExecutionTrace from a native tool-use turn loop.

    Holds the live GoalVerifier namespace + oracle names + the motor tool-set, and
    the per-step accumulator (the action chain + its capture baseline). The MODEL
    issues the tool calls; this runner only dispatches, verifies, grades, and
    records — never decides what to do next.
    """

    def __init__(
        self,
        agent: Any,
        verifier: Any,
        oracle_names: frozenset[str],
        motor_tools: dict[str, Any],
        tool_context: ToolContext,
    ) -> None:
        self._agent = agent
        self._verifier = verifier
        self._oracle_names = oracle_names
        self._motor_tools = motor_tools
        self._ctx = tool_context

        # Per-step accumulator: the producing action chain (skill names) + the
        # capture baseline taken BEFORE the first skill of the current step.
        self._chain: list[str] = []
        self._baseline: Any = None
        self._step_open: bool = False

        # The assembled trace pieces (one SubGoal + one StepRecord per verify pair).
        self._sub_goals: list[SubGoal] = []
        self._steps: list[StepRecord] = []
        self._step_idx: int = 0

    # ------------------------------------------------------------------
    # Skill dispatch (capture baseline before the first skill of a step)
    # ------------------------------------------------------------------

    def dispatch_skill(self, name: str, params: dict[str, Any]) -> ToolResult:
        """Run a motor/skill tool via SkillWrapperTool; open a step if needed.

        The actor-causation baseline is captured immediately BEFORE the FIRST skill
        call of the current step (review fix 3), then frozen — advancing the robot
        afterwards cannot mutate it (ActorBaseline is a value snapshot).
        """
        tool = self._motor_tools.get(name)
        if tool is None:
            return ToolResult(content=f"Unknown tool '{name}'.", is_error=True)
        if not self._step_open:
            # First skill of a fresh step -> capture the causation baseline NOW.
            self._baseline = actor_causation.capture(self._agent)
            self._step_open = True
        self._chain.append(name)
        try:
            return tool.execute(params, self._ctx)
        except Exception as exc:  # noqa: BLE001
            logger.debug("native_loop: skill '%s' raised: %s", name, exc)
            return ToolResult(content=f"Skill '{name}' raised: {exc}", is_error=True)

    # ------------------------------------------------------------------
    # The verify-tool HANDLER — appends EXACTLY ONE StepRecord per pair
    # ------------------------------------------------------------------

    def handle_verify(self, expr: str) -> ToolResult:
        """Evaluate *expr* via the live GoalVerifier, grade causation, record ONE step.

        This is the heart of the granularity contract (review fix 2): the
        (action-chain -> verify) pair becomes ONE StepRecord whose SubGoal.verify is
        the model's expr and whose strategy is the producing action chain. The loop
        NEVER computes verified — the spine does, from this trace.
        """
        expr = (expr or "").strip()
        # Evaluate the predicate via the SAME GoalVerifier sandbox the spine uses.
        try:
            verify_result = bool(self._verifier.verify(expr))
        except Exception as exc:  # noqa: BLE001
            logger.debug("native_loop: verify(%r) raised: %s", expr, exc)
            verify_result = False

        # Grade actor-causation with a FRESH post-capture, immediately after the
        # verify read (review fix 3) — only for a graded robot predicate, else
        # NOT_GRADED (legacy-equivalent). The baseline was captured before this
        # step's first skill; if no skill ran (a verify-only NO-OP step), baseline
        # is None -> grade fail-closed UNCAUSED for a robot predicate.
        actor_caused = self._grade(expr)

        strategy = self._chain[-1] if self._chain else ""
        step_name = f"native_step_{self._step_idx}"
        self._step_idx += 1

        sub_goal = SubGoal(
            name=step_name,
            description=f"native: {' -> '.join(self._chain) or '(no action)'} | verify {expr}",
            verify=expr,
            strategy=strategy,
        )
        # The step "ran" (success) iff at least one action skill was dispatched for
        # it OR it is a pure check; verify_result + actor_caused carry the moat. A
        # verify-only step (no skill) still records success=True so the gate keys on
        # GROUNDED/RAN (a NO-OP must reach the verdict as RAN, not FAILED).
        step = StepRecord(
            sub_goal_name=step_name,
            strategy=strategy,
            success=True,
            verify_result=verify_result,
            duration_sec=0.0,
            actor_caused=actor_caused,
        )
        self._sub_goals.append(sub_goal)
        self._steps.append(step)

        # Close the step: reset the action chain + baseline for the next pair. NEVER
        # carry a baseline across a verify (else the next step's causation folds in).
        self._chain = []
        self._baseline = None
        self._step_open = False

        return ToolResult(
            content=(
                f"verify({expr}) -> {verify_word(verify_result)} "
                f"(result={verify_result}, actor={actor_caused.value})"
            )
        )

    def _grade(self, expr: str) -> "actor_causation.ActorCaused":
        """Grade actor-causation for the just-verified step (R2b semantics).

        Mirrors ``GoalExecutor._grade_actor_causation``: NOT_GRADED unless the
        verify names a graded robot predicate live in the oracle set; otherwise a
        fresh post-capture vs the step's entry baseline -> CAUSED / UNCAUSED.
        Fail-safe to NOT_GRADED on any error (never raises). A robot-predicate step
        whose baseline is None (no skill ran) grades UNCAUSED (grade fail-closes).
        """
        try:
            if not actor_causation.is_robot_predicate(expr, self._oracle_names):
                return actor_causation.ActorCaused.NOT_GRADED
            post = actor_causation.capture(self._agent)
            return actor_causation.grade(self._baseline, post, expr, self._oracle_names)
        except Exception as exc:  # noqa: BLE001
            logger.debug("native_loop: grade(%r) raised: %s", expr, exc)
            return actor_causation.ActorCaused.NOT_GRADED

    # ------------------------------------------------------------------
    # Trace assembly
    # ------------------------------------------------------------------

    def build_trace(self, goal: str) -> ExecutionTrace:
        """Assemble the ExecutionTrace from the recorded (chain -> verify) steps.

        ``success`` is True iff at least one step was recorded AND none failed —
        the structural success flag the verdict reads (the moat is GROUNDED/RAN, not
        this flag). An empty trace (no verify ever called) is success=False, so the
        verdict gate fails closed (no checked step -> not verified).
        """
        steps = tuple(self._steps)
        success = bool(steps) and all(s.success for s in steps)
        goal_tree = GoalTree(goal=goal, sub_goals=tuple(self._sub_goals))
        return ExecutionTrace(
            goal_tree=goal_tree,
            steps=steps,
            success=success,
            total_duration_sec=0.0,
        )


def verify_word(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


# ---------------------------------------------------------------------------
# run_turn_native — the producer (drives the model, hands the spine a trace)
# ---------------------------------------------------------------------------


def run_turn_native(
    engine: Any,
    user_message: str,
    *,
    agent: Any | None = None,
    session: Any = None,
    app_state: dict[str, Any] | None = None,
    max_turns: int = _MAX_NATIVE_TURNS,
) -> ExecutionTrace:
    """Run ONE user turn through the native tool-use loop; return an ExecutionTrace.

    The producer half of the strangle. The MODEL (via ``engine._backend``) is given
    a NARROW tool-set — the motor skills + the synthetic ``verify``/``finish`` — and
    drives a ReAct loop: it calls action skills, then ``verify(expr)``, re-issuing a
    tool call after a False verify tool_result (the loop does NOT replan). When the
    model finishes (``finish`` or end_turn with no tool calls), the runner assembles
    the trace from the recorded (action-chain -> verify) pairs and returns it.

    The caller (``cli.run_one_turn``) feeds the returned trace to the EXISTING
    ``VerdictReport.from_trace(trace, verify_oracle_names(agent, engine))`` — this
    function NEVER computes ``verified``.
    """
    agent = agent if agent is not None else getattr(engine, "_vgg_agent", None)

    # The live verifier + oracle names — single-sourced from the SAME namespace the
    # spine reads (rule 3). Fail closed on any error (empty oracle set -> every
    # predicate classifies RAN downstream).
    verifier = _build_verifier(engine, agent)
    oracle_names = verify_oracle_names(agent, engine)

    # The motor tool-set: the world's skills + the engine registry's code tools
    # (file_write/bash/...), wrapped as tools. The synthetic verify/finish tools are
    # handled in-loop, never dispatched as skills.
    motor_tools = _build_motor_tools(agent, engine)
    tool_schemas = _native_tool_schemas(motor_tools, oracle_names)

    ctx = _build_tool_context(agent, session, app_state, engine)
    runner = NativeStepRunner(agent, verifier, oracle_names, motor_tools, ctx)

    backend = getattr(engine, "_backend", None)
    if backend is None:
        # No backend wired -> no native turns -> empty trace (verdict fails closed).
        return runner.build_trace(user_message)

    system_prompt = _native_system_prompt(engine, oracle_names)
    _append_user(session, user_message)

    turns = 0
    while turns < max_turns:
        messages = _to_messages(session)
        response: LLMResponse = backend.call(
            messages=messages,
            tools=tool_schemas,
            system=system_prompt,
            max_tokens=getattr(engine, "_max_tokens", 4096),
        )
        tool_calls = list(response.tool_calls or [])
        _append_assistant(session, response, tool_calls)

        if not tool_calls:
            break  # end_turn, no tools — conversation complete

        finished = False
        result_dicts: list[dict[str, Any]] = []
        for tc in tool_calls:
            if tc.name == FINISH_TOOL:
                finished = True
                result_dicts.append(_tool_result_dict(tc.id, "Task finished."))
                continue
            if tc.name == VERIFY_TOOL:
                expr = str((tc.input or {}).get("expr", ""))
                res = runner.handle_verify(expr)
            else:
                res = runner.dispatch_skill(tc.name, dict(tc.input or {}))
            result_dicts.append(_tool_result_dict(tc.id, res.content, res.is_error))

        _append_tool_results(session, result_dicts)
        turns += 1
        if finished:
            break

    return runner.build_trace(user_message)


# ---------------------------------------------------------------------------
# Helpers — verifier / tools / system prompt / session glue (no planner imports)
# ---------------------------------------------------------------------------


def _build_verifier(engine: Any, agent: Any) -> Any:
    """Build a live GoalVerifier over the engine's verify namespace.

    Reuses the EXISTING namespace builder so the verify sandbox is byte-identical
    to the one the spine uses. Reuses the already-wired GoalVerifier on the engine's
    goal executor when present (same namespace), else constructs a fresh one.
    """
    from vector_os_nano.vcli.cognitive.goal_verifier import GoalVerifier

    executor = getattr(engine, "_goal_executor", None)
    live = getattr(executor, "_verifier", None)
    if live is not None and hasattr(live, "verify"):
        return live
    builder = getattr(engine, "_build_verifier_namespace", None)
    ns = builder(agent) if builder is not None else {}
    return GoalVerifier(ns)


def _build_motor_tools(agent: Any, engine: Any) -> dict[str, Any]:
    """Assemble the loop's ACTION surface: the world's skills + the engine's code tools.

    Two sources, both world-agnostic by construction:

    1. ``wrap_skills(agent)`` — the world's robot skills (``walk`` etc.). ``navigate``
       is intentionally NOT surfaced as a step strategy: its cmd_vel is GATED OUT of
       the actor-causation counter, so offering it would false-FAIL an honest move. We
       drop it by construction (the acceptance pins per-step strategy == 'walk', never
       'navigate'). When ``agent`` is None (the dev world), this source is empty.
    2. The engine registry's ``code``-category tools (file_read/file_write/file_edit/
       bash/glob/grep) — the kernel's domain-general action surface, the SAME tools the
       legacy dev path dispatches via ``DEV_TOOL_ALLOWLIST`` + ``ToolDispatcher``. These
       are real ``Tool`` objects whose ``.execute(params, ctx)`` is the interface
       ``dispatch_skill`` already calls, so they slot in directly. This is what lets the
       dev world (no agent -> no skills) ACT, and adds the code tools to the robot world
       too. Native asks the ENGINE for its registered action tools — there is NO
       embodiment/"if dev" branch in this module (rule 7).

    The synthetic ``verify``/``finish`` names are loop-owned and never collide with a
    registry tool; a code tool can never shadow them. A wrapped skill that happens to
    share a code-tool name (none do today) would take precedence — skills are layered
    AFTER the code tools so the world's own skill wins if a clash ever arises.
    """
    tools: dict[str, Any] = {}
    # Source 2: the engine registry's code tools (present in every world).
    for name, code_tool in _code_tools_from_registry(engine).items():
        tools[name] = code_tool
    # Source 1: the world's skills (robot worlds only; dev world has no agent).
    if agent is not None:
        try:
            for skill_tool in wrap_skills(agent):
                if skill_tool.name == "navigate":
                    continue  # gated-out of actor-causation -> never a native step strategy
                tools[skill_tool.name] = skill_tool
        except Exception as exc:  # noqa: BLE001
            logger.debug("native_loop: wrap_skills failed: %s", exc)
    return tools


def _code_tools_from_registry(engine: Any) -> dict[str, Any]:
    """Return the engine registry's ``code``-category Tool objects, keyed by name.

    Pulls the live, instantiated tools out of the engine's ``CategorizedToolRegistry``
    so the native loop offers the EXACT action surface the kernel registered (no
    duplicate construction, no hand-authored allowlist here — single-sourced from the
    registry, rule 3). Defensive: a registry without the categorized API, a missing
    ``code`` category, or any lookup failure yields an empty set (the dev world then
    falls back to offering only verify/finish, the pre-fix behaviour). Disabled
    categories are still surfaced here on purpose — ``code`` is never disabled in any
    world, and the loop's tool-set is independent of the chat-path category gating.
    """
    registry = getattr(engine, "_registry", None)
    if registry is None:
        return {}
    list_categories = getattr(registry, "list_categories", None)
    get = getattr(registry, "get", None)
    if list_categories is None or get is None:
        return {}  # a plain ToolRegistry (no categories) -> no code tools to surface
    tools: dict[str, Any] = {}
    try:
        names = list_categories().get(_CODE_TOOL_CATEGORY, [])
        for name in names:
            code_tool = get(name)
            if code_tool is not None:
                tools[name] = code_tool
    except Exception as exc:  # noqa: BLE001
        logger.debug("native_loop: code-tool discovery failed: %s", exc)
    return tools


def _native_tool_schemas(
    motor_tools: dict[str, Any], oracle_names: frozenset[str]
) -> list[dict[str, Any]]:
    """The Anthropic-shaped tool schemas the model is offered for a native turn."""
    schemas: list[dict[str, Any]] = []
    for name, tool in motor_tools.items():
        schemas.append(
            {
                "name": name,
                "description": getattr(tool, "description", name),
                "input_schema": getattr(tool, "input_schema", {"type": "object", "properties": {}}),
            }
        )
    schemas.append(_verify_tool_schema(oracle_names))
    schemas.append(_finish_tool_schema())
    return schemas


def _native_system_prompt(engine: Any, oracle_names: frozenset[str]) -> list[dict[str, Any]]:
    """A minimal native system prompt, single-sourcing the verify vocab.

    Anthropic 'system' is a list of text blocks; the verify-vocab (oracle names +
    at_position tol) is taken from the SAME source ``verify_oracle_names`` reads, so
    the model's verify expr is grounded in the live namespace (review fix 6).
    """
    names = ", ".join(sorted(oracle_names)) if oracle_names else "(none)"
    tol = _at_position_tol()
    text = (
        "You control a robot through tools. For each goal: call the MOTION skill "
        "that achieves it (e.g. walk), then IMMEDIATELY call verify(expr) with a "
        "deterministic predicate to PROVE the goal was achieved, then call finish. "
        "verify reads the real world state itself, so do NOT call a read-only "
        "status/query skill (e.g. where_am_i, look) before verify — the motion "
        "skill must be the LAST action call before each verify. "
        f"Available verify predicate oracles: {names}. "
        "Choose the predicate that MEASURES the goal quantity: a goal of reaching a "
        "place/coordinate is proven by at_position (a position check), NOT by a "
        "scene/description oracle. "
        "A goal of picking up / grasping an object is proven by the holding_object(...) "
        "gripper oracle: call holding_object('<name>') with the object's scene name as a "
        "QUOTED string, e.g. holding_object('banana'), to prove you grasped THAT specific "
        "object (a bare word without quotes is not a valid argument). "
        f"at_position(x, y, tol={tol}) is True when the robot is within tol metres of "
        f"(x, y). To reach a target coordinate, walk toward it (a forward walk "
        "advances along the robot's heading) and verify with at_position(x, y) for "
        "that target. The legged gait UNDER-SHOOTS the commanded distance "
        "substantially, so command a walk distance well LARGER than the straight-line "
        "gap to the target (about 2x, and never less than ~1.5m even for a short hop) "
        "so a single move lands within tolerance. CRITICAL — RECOVER on failure: if a "
        "verify returns FAIL the robot fell SHORT, so you MUST immediately issue "
        "ANOTHER walk covering the remaining gap and verify again, repeating "
        "(walk -> verify) until at_position returns PASS. NEVER call finish while the "
        "latest verify is FAIL, and NEVER stop after a single failed verify — always "
        "walk again and re-verify. Only finish once a verify has PASSED."
    )
    return [{"type": "text", "text": text}]


def _build_tool_context(
    agent: Any, session: Any, app_state: dict[str, Any] | None, engine: Any
) -> ToolContext:
    """Build the ToolContext skills run under (no-permission, headless-safe)."""
    import threading
    from pathlib import Path

    return ToolContext(
        agent=agent,
        cwd=Path.cwd(),
        session=session,
        permissions=getattr(engine, "_permissions", None),
        abort=threading.Event(),
        app_state=app_state,
    )


# -- session glue (duck-typed; works with the real Session + None) -----------


def _append_user(session: Any, text: str) -> None:
    if session is not None and hasattr(session, "append_user"):
        session.append_user(text)


def _append_assistant(session: Any, response: LLMResponse, tool_calls: list[Any]) -> None:
    if session is None or not hasattr(session, "append_assistant"):
        return
    tool_use_dicts = (
        [{"id": tc.id, "name": tc.name, "input": tc.input, "type": "tool_use"} for tc in tool_calls]
        if tool_calls
        else None
    )
    session.append_assistant(response.text, tool_use_dicts)


def _append_tool_results(session: Any, result_dicts: list[dict[str, Any]]) -> None:
    if session is not None and hasattr(session, "append_tool_results"):
        session.append_tool_results(result_dicts)


def _to_messages(session: Any) -> list[dict[str, Any]]:
    if session is not None and hasattr(session, "to_messages"):
        return session.to_messages()
    return []


def _tool_result_dict(tool_use_id: str, content: str, is_error: bool = False) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": tool_use_id,
        "content": content,
        "is_error": is_error,
    }
