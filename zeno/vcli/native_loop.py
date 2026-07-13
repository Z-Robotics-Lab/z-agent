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

import ast
import logging
from typing import Any, Callable

from zeno.vcli.backends.types import LLMResponse
from zeno.vcli.cognitive import actor_causation
from zeno.vcli.cognitive.trace_store import verify_oracle_names
from zeno.vcli.cognitive.types import (
    ExecutionTrace,
    GoalTree,
    StepRecord,
    SubGoal,
)
from zeno.vcli.tools.base import ToolContext, ToolResult
from zeno.vcli.tools.skill_wrapper import wrap_skills

logger = logging.getLogger(__name__)

# Synthetic tool names the runner OWNS (never wrapped from a skill).
VERIFY_TOOL = "verify"
FINISH_TOOL = "finish"

# A hard cap on native round-trips so a misbehaving model / script can never spin
# forever. Mirrors the engine's _max_turns spirit; the loop also stops on finish.
_MAX_NATIVE_TURNS = 24

# How many times the runner re-prompts a model that tries to finish/stop with an
# action it never verified (D23). Bounded so a model that stubbornly refuses to
# verify still terminates — the unverified action then grades honestly (empty/RAN),
# never a false green. The verify stays MODEL-authored; the runner never invents it.
_MAX_VERIFY_NUDGES = 2

# The re-prompt sent when the model tries to finish/stop while its OWN latest verify
# returned FAIL. Brain-agnostic quantity/multi-object guardrail: it names the next
# action generically (place the NEXT remaining object) WITHOUT the runner parsing the
# goal for N — the model still owns decompose/route, so the loop stays planner-free.
_FINISH_ON_FAIL_NUDGE = (
    "Cannot finish: your most recent verify() returned FAIL, so the goal is NOT yet "
    "proven achieved (for a quantity/multi-object task this usually means only SOME of "
    "the requested objects are on the receptacle). Do NOT stop. Take the next action "
    "toward the goal — for a multi-object place, grasp and place the NEXT remaining "
    "object (call navigate_to_object('<next name>') once first if the grasp returns "
    "no_detections) — then call verify(<the same goal predicate>) again. Only finish "
    "once that verify PASSES."
)

# Grasp/pick skills that RE-ACQUIRE an object into the gripper. After a SUCCESSFUL
# place the gripper is legitimately EMPTY (that is the place's whole purpose); a brain
# that misreads the empty gripper as an accidental drop ('掉了') and issues one of these
# RE-GRASPS the just-placed object off the receptacle, UNDOING the place (R255/R256
# courtyard PLACE flake, E60). The runner refuses a re-grasp until ONE verify closes the
# place — for a single place that verify PASSES (finish); for a quantity place it FAILS
# (more to place) and the guard clears so the next-object grasp runs.
_GRASP_SKILLS: frozenset[str] = frozenset(
    {"perception_grasp", "mobile_pick", "pick", "pick_top_down"}
)
# Place skills whose SUCCESS empties the gripper onto a receptacle.
_PLACE_SKILLS: frozenset[str] = frozenset({"mobile_place", "place", "place_top_down"})


def _skill_is_grasp(skill_tool: Any) -> bool:
    """Whether *skill_tool* GRASPS an object (the re-grasp the post-place guard refuses).

    UNION of the curated ``_GRASP_SKILLS`` name-list and the skill's OWN structured metadata
    (``SkillWrapperTool._is_grasp``, precondition ``gripper_empty``) so the guard is complete for
    a plug-and-play grasp skill the kernel has never named (North-Star BYO skill, no kernel edit).
    Byte-IDENTICAL to the name-list for every shipped skill — the shipped ``gripper_empty``-
    precondition skills are EXACTLY ``_GRASP_SKILLS`` (R385/E174)."""
    return skill_tool.name in _GRASP_SKILLS or bool(getattr(skill_tool, "_is_grasp", False))


def _skill_is_place(skill_tool: Any) -> bool:
    """Whether a SUCCESSFUL *skill_tool* releases a held object and empties the gripper (arms the
    post-place guard).

    UNION of the curated ``_PLACE_SKILLS`` name-list and the skill's OWN structured metadata
    (``SkillWrapperTool._releases_object``: precondition ``gripper_holding_any`` AND a gripper-
    emptying effect). A strict SUPERSET of the name-list: it ADDS the shipped ``handover`` (which
    empties the gripper — the same '掉了' re-grasp risk, previously un-guarded) plus any BYO place
    skill; it never drops a shipped place. Strictly stricter (more arming ⇒ more re-grasp refusal),
    bounded by ``_MAX_VERIFY_NUDGES`` so it can never wedge (R385/E174)."""
    return skill_tool.name in _PLACE_SKILLS or bool(
        getattr(skill_tool, "_releases_object", False)
    )

# Re-prompt sent when the model tries to RE-GRASP immediately after a successful place
# without first verifying it. Brain-agnostic + planner-free: it names the real check
# (resting_on_receptacle) without parsing the goal for N — the model still owns the
# decision (finish vs. place the next object). Bounded by _MAX_VERIFY_NUDGES so a model
# that stubbornly re-grasps still terminates (the guard can never wedge the turn).
_POST_PLACE_REGRASP_NUDGE = (
    "You just placed an object with the place skill — it RELEASED the object onto the "
    "receptacle, so an EMPTY gripper (holding_object == False) is the EXPECTED, correct "
    "result, NOT an accidental drop ('掉了'). Do NOT re-grasp the object you just placed. "
    "First call verify(resting_on_receptacle() >= <the requested count>): if it PASSES "
    "the goal is DONE — call finish. Only grasp again if that verify is still BELOW the "
    "requested count (a quantity task with more objects still to place)."
)

# R274/E74 degenerate-spin guard. A flaky routing brain (R272/R273 non-determinism)
# can keep issuing action skills (perception_grasp / navigate / detect / describe) turn
# after turn WITHOUT ever calling verify — it burns the whole _MAX_NATIVE_TURNS budget
# producing ZERO verdicts (~15min wall-clock on the sim), so nothing grounds AND the
# eyes-judge never fires (no verdict snapshot). This is DISTINCT from the finish-on-fail
# guard (which fires only when the model DID verify and it FAILED). Here the model never
# measures at all. We count consecutive skill-only turns with no verify: at the SOFT
# threshold nudge ONCE to force a measurement (a verify yields a real — usually False —
# verdict, so the run terminates honestly AND the judge finally fires); at the HARD
# threshold break to an honest fail (the trace grades RAN/empty, NEVER a forced green).
# Planner-free + brain-agnostic: keys ONLY on "did a verify happen this turn", no goal
# parsing, no per-object bookkeeping. Both thresholds sit well above a healthy task's
# cadence (a normal fetch/place verifies within ~3 turns; the R272 healthy fetch verified
# repeatedly, the R273 thrash verified ZERO times across all 24 turns).
_UNPRODUCTIVE_NUDGE_AT = 6
_MAX_TURNS_WITHOUT_VERIFY = 12
_UNPRODUCTIVE_SPIN_NUDGE = (
    "You have taken several actions in a row without measuring progress. STOP acting and "
    "call verify(<the goal predicate>) NOW to check whether the goal is actually achieved "
    "(e.g. holding_object('<name>') for a fetch, or resting_on_receptacle() >= <count> for "
    "a place). Re-scanning / re-navigating / re-grasping without a verify makes no "
    "measurable progress. If the verify FAILS, take ONE corrective action then verify again; "
    "if it PASSES, call finish."
)

# The registry category whose tools are the kernel's domain-general ACTION surface
# (file_read/file_write/file_edit/bash/glob/grep — see tools.__init__._TOOL_CATEGORIES
# and worlds.dev.DEV_TOOL_ALLOWLIST, which is this category). The native loop offers
# these as motor tools alongside the world's skills, so the dev world (no robot agent,
# hence no wrapped skills) can still ACT — and the robot world gains the same code
# tools. World-agnostic BY CONSTRUCTION: native asks the ENGINE'S registry for its
# registered action tools; there is NO "if dev" branch.
_CODE_TOOL_CATEGORY = "code"

# The MUTATING code tools — the ones whose effect is a file/shell WRITE the model can
# author at will (so it can "accomplish" a task by writing a marker file or running a
# shell command), NEVER a read-only diagnostic. In a ROBOT world these must NOT be an
# action path to a PHYSICAL goal: the fakeable-grasp defect was deepseek satisfying
# "抓前面的东西" by ``file_write('grabbed.txt')`` then ``verify(file_exists('grabbed.txt'))``
# (D17). A physical robot task is accomplished by a robot SKILL and proven by a GT
# oracle the actor cannot author — never by touching a file. So a robot world drops
# these from the loop's ACTION toolset (Prong 1) while KEEPING the read-only diagnostics
# (file_read / glob / grep) the persona uses to inspect code. The DEV world is untouched
# — it has no robot agent, so the gate below never fires there. Prong 2 (the goal-
# authenticity gate in the frozen spine) is the un-fakeable backstop if a model ever
# reaches a file oracle another way; this prong removes the easy path by construction.
_MUTATING_CODE_TOOLS: frozenset[str] = frozenset({"file_write", "file_edit", "bash"})

# Manipulation skills that REQUIRE an arm to do anything (grep-verified: each references
# ctx.arm / the gripper). A camera-only body (g1: ``has_arm`` False) must NOT be offered
# these — a frontier model would otherwise chain a doomed ``pick`` on an armless robot and
# false-FAIL the honest verdict (the g1 detect step GROUNDS, then a chained pick with "No
# arm connected" drags the compound to RAN-False). Gated on the SAME single-source
# ``resolve_capability_profile`` as the has_base/navigate gate so the two can't drift.
# Perception skills (describe/detect) are embodiment-agnostic and are NEVER gated here.
# The CURATED half of the manipulation-gate classifier (see ``_skill_needs_arm``). Encodes
# domain knowledge a metadata scan CANNOT derive: ``scan``/``describe`` drive the arm-mounted
# head-cam and ``wave`` homes the arm, yet their STRUCTURED metadata is arm-silent, so a
# keyword scan alone would wrongly offer them to an armless body. This list is UNIONED with
# the skill's own structured arm/gripper declaration (``SkillWrapperTool._requires_arm``) so
# the gate is also complete for plug-and-play skills the kernel has never named (R384/E173).
_ARM_REQUIRING_SKILLS: frozenset[str] = frozenset(
    {"pick", "place", "pick_top_down", "place_top_down", "mobile_place",
     "home", "wave", "scan", "handover", "gripper_open", "gripper_close",
     # ``describe`` auto-runs ``scan`` first (auto_steps=["scan","describe"]) and scan
     # needs an arm -> on an armless body describe fails "No arm connected", adding a
     # non-GROUNDED checked step that false-FAILS an otherwise-clean perception turn.
     # Gated on armless only (go2+arm keeps it). Frontier: an arm-free describe path.
     "describe"}
)


def _skill_needs_arm(skill_tool: Any) -> bool:
    """Whether an armless body must NOT be offered *skill_tool* (the D175 manipulation gate).

    UNION of two signals so the gate is complete for plug-and-play skills, not just the
    shipped set:
      1. the curated ``_ARM_REQUIRING_SKILLS`` name-list — domain knowledge a metadata scan
         can't derive (``scan``/``describe`` use the arm-mounted head-cam; ``wave``/``home``
         home the arm) whose structured metadata is arm-silent;
      2. the skill's OWN structured arm/gripper declaration (``SkillWrapperTool._requires_arm``,
         scanned over preconditions+effects) — catches a BYO manipulation skill the kernel has
         never named (North-Star plug-and-play, no kernel edit).

    Strictly STRICTER than the name-list alone (Invariant 1: the sandbox only gets stricter):
    every skill the list already withholds stays withheld; the metadata half only ADDS
    withholding, never offers. Behavior-identical for every shipped skill on every shipped
    body — the only armless-offered shipped skill (``detect``) is arm-silent (R384/E173).
    """
    if skill_tool.name in _ARM_REQUIRING_SKILLS:
        return True
    return bool(getattr(skill_tool, "_requires_arm", False))

# at_position tolerance (metres) — single-sourced for the system-prompt vocab from
# the go2 oracle so the model's verify expr and the verifier agree. Read live with
# a safe fallback so this module never hard-depends on the oracle's private const.
def _at_position_tol() -> float:
    try:
        from zeno.vcli.worlds.go2_sim_oracle import _AT_POSITION_TOL_M
        return float(_AT_POSITION_TOL_M)
    except Exception:  # noqa: BLE001
        return 0.5


# D9 #1 — the avoidance NAVIGATION route.
_NAV_TIMEOUT_S = 60.0


def _agent_base(context: ToolContext) -> Any:
    """The connected mobile base from the tool context's agent (the WIRED accessor).

    The ``walk`` skill, the verify oracles, and actor-causation all reach the live base
    via ``agent._base`` — the standalone ``vcli/primitives`` layer is NOT wired in the
    product (``init_primitives`` is never called; its ``_ctx`` is None). So native must
    use ``agent._base`` too, never ``primitives.navigation/locomotion``.
    """
    agent = getattr(context, "agent", None)
    return getattr(agent, "_base", None)


class _NativeBaseNavigateTool:
    """Coordinate navigation through the nav-stack AVOIDANCE route (D9 #1).

    ``execute`` calls the connected base's ``navigate_to(x, y)`` — the go2 ROS2 proxy
    method that sets the nav flag, publishes ``/goal_point`` to the FAR planner (which
    routes over the lidar terrain map and AVOIDS obstacles), and blocks until arrival or
    timeout. This is the obstacle avoidance the open-loop ``walk`` lacks. The planner
    drives the base over ``cmd_vel``, which is GATED OUT of the actor-causation counter
    (it runs on the bridge thread, never setting ``_skill_ctrl_tid``) — so a ``navigate``
    step's ``at_position`` verify grades UNCAUSED and the spine downgrades GROUNDED -> RAN:
    an HONEST "ran, cannot prove the actor caused it" until actor-causation is extended to
    cmd_vel. The moat is never loosened (rule 5). Duck-typed like a ``Tool`` so
    ``dispatch_skill`` runs it uniformly.
    """

    name = "navigate"
    description = (
        "Go to a world coordinate (x, y) using the navigation PLANNER, which AVOIDS "
        "obstacles (lidar + local planner). Use this to REACH a place/coordinate. After "
        "it returns, call verify(at_position(x, y))."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "Target x (world frame, metres)."},
            "y": {"type": "number", "description": "Target y (world frame, metres)."},
        },
        "required": ["x", "y"],
    }

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            x = float(params["x"])
            y = float(params["y"])
        except (KeyError, TypeError, ValueError):
            return ToolResult(content="navigate requires numeric x and y.", is_error=True)

        base = _agent_base(context)
        navigate_to = getattr(base, "navigate_to", None)
        if not callable(navigate_to):
            return ToolResult(
                content="navigate: the connected base has no navigate_to (no nav stack).",
                is_error=True,
            )

        try:
            ok = bool(navigate_to(x, y, timeout=_NAV_TIMEOUT_S))
        except TypeError:
            # A base whose navigate_to does not accept a timeout kwarg.
            try:
                ok = bool(navigate_to(x, y))
            except Exception as exc:  # noqa: BLE001
                return ToolResult(content=f"navigate({x}, {y}) failed: {exc}", is_error=True)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(content=f"navigate({x}, {y}) failed: {exc}", is_error=True)

        pos = None
        getter = getattr(base, "get_position", None)
        if callable(getter):
            try:
                pos = getter()
            except Exception as exc:  # noqa: BLE001
                logger.debug("native_loop: navigate get_position failed: %s", exc)
        where = f"({pos[0]:.2f}, {pos[1]:.2f})" if pos else "unknown"
        status = "arrived" if ok else "did NOT confirm arrival (FAR graph unavailable or timeout)"
        return ToolResult(
            content=f"navigate: {status}; now at {where} (target ({x}, {y})). "
            "Call verify(at_position) to confirm."
        )


class _NativeDetectTool:
    """Route a NAMED/COLOUR query to the learned grounding-dino DETECTOR capability.

    R4 — composes the two North-Star axes on ONE turn: this surfaces the registered
    ``DetectorCapability`` (the learned SECOND model family, grounding-dino-tiny) into
    the native loop so a bare-cli detect command reaches it on whatever camera-bearing
    embodiment is connected — go2+arm OR g1 (the humanoid, camera but NO arm). It does
    NOT re-implement detection: ``execute`` pulls the SAME capability instance the world
    registered into the engine's ``CapabilityRegistry`` (agent-bound for the live
    perception) and invokes it — single-sourced, no second model load (rule 3).

    Read-only PERCEPTION: the detector only localizes, it does not act on the world, so
    a detect step grades RAN — the honest grade for a perceive-only route (mirrors D50;
    actor-causation has no displacement to attribute). The capability never self-
    certifies; the model-authored ``verify(len(detect_objects()) > 0)`` is the moat.

    The detection result (boxes/labels/scores) is stashed on the agent so the world's
    ``detect_objects()`` verify oracle reflects what the LEARNED MODEL actually saw on
    the live camera (rule 4: the structured observation flows to the verify step, never
    collapsed to (success, error)). Duck-typed like a ``Tool`` so ``dispatch_skill``
    runs it uniformly. Only surfaced when a ``detect`` capability is registered AND the
    agent has a camera (see ``_build_motor_tools``) — sensorless/dev paths never see it.
    """

    name = "detect"
    description = (
        "Localize a named or coloured object in the robot's CAMERA view using the "
        "learned open-vocabulary detector (grounding-dino). Pass the target as 'query' "
        "(e.g. 'red object', 'a red stool', '红色的东西'). Returns bounding box(es) + "
        "label(s) + score(s). This is PERCEPTION only (read-only). After it returns, "
        "call the verify expression the tool result tells you to use to confirm the "
        "model localized the object (the exact verify depends on the embodiment)."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural-language target to localize (named or coloured).",
            },
        },
        "required": ["query"],
    }

    def __init__(self, capability: Any) -> None:
        # The SAME registered DetectorCapability the world bound to the agent's live
        # perception — never a fresh instance, never a second model load.
        self._capability = capability

    @staticmethod
    def _verify_hint(agent: Any, query: str) -> str:
        """The verify call the model should make AFTER detect, matched to the live oracle.

        Two honest grades depending on the embodiment's verify namespace:
          - g1-shape (camera + SIM GT base + NO arm): the GT-backed SPATIAL-MATCH
            oracle ``detection_matches_gt`` is bound (R7), so the GROUNDED verify is
            ``detection_matches_gt('<query>') == True`` — True iff the detector's box
            matches where the INDEPENDENT GT object projects (not a self-read).
          - go2+arm or anything with a GT ``detect_objects`` oracle: the existing
            ``len(detect_objects()) > 0`` hint (its GROUND-TRUTH oracle, D62).
        World-side hint only; the model still AUTHORS the verify and the spine grades it.
        """
        arm = getattr(agent, "_arm", None) if agent is not None else None
        base = getattr(agent, "_base", None) if agent is not None else None
        if (
            arm is None
            and base is not None
            and getattr(base, "_model", None) is not None
            and getattr(base, "_data", None) is not None
        ):
            return f"verify(detection_matches_gt({query!r}) == True)"
        return "verify(len(detect_objects()) > 0)"

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        query = str((params or {}).get("query", "")).strip()
        if not query:
            return ToolResult(content="detect requires a non-empty 'query'.", is_error=True)
        hint = self._verify_hint(getattr(context, "agent", None), query)
        try:
            result = self._capability.invoke({"query": query}, context)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(content=f"detect({query!r}) raised: {exc}", is_error=True)

        output = dict(getattr(result, "output", {}) or {})
        boxes = output.get("boxes") or []
        labels = output.get("labels") or []
        scores = output.get("scores") or []

        # MOAT DISCIPLINE (R6 audit): the detector's OWN output is deliberately NOT
        # stashed on the agent. R4 stashed it as ``agent._last_detection`` so a
        # world ``detect_objects()`` oracle could read it back — that made
        # ``verify(len(detect_objects()) > 0)`` a TAUTOLOGY (the detector certifying
        # itself) and minted a FALSE GREEN (D61). The self-read oracle was removed
        # (worlds/robot.py), and the orphaned stash is removed here so no future
        # round can re-wire the means' own output into the verify namespace. The
        # detector's result still flows to the HUMAN-READABLE tool output below and
        # (when a sim arm is present) the GROUND-TRUTH ``detect_objects`` oracle reads
        # ``arm.get_object_positions()`` — independent of the means, never this output.
        if not getattr(result, "success", False) and not boxes:
            err = getattr(result, "error", "") or "no detections"
            return ToolResult(
                content=(
                    f"detect({query!r}): the detector RAN but localized nothing ({err}). "
                    f"Call {hint} to confirm (it will be False — nothing matched the GT)."
                )
            )
        first = (
            f"label={labels[0]!r} box={[round(float(v), 1) for v in boxes[0]]} "
            f"score={float(scores[0]):.2f}"
            if boxes and labels and scores
            else "(box)"
        )
        return ToolResult(
            content=(
                f"detect({query!r}): grounding-dino localized {len(boxes)} object(s); "
                f"top {first}. To COMPLETE this perception task call EXACTLY {hint} — it "
                f"is the ONLY grounding oracle here. If it returns True the task is DONE: "
                f"call finish immediately. Do NOT call detect again and do NOT invent other "
                f"verify predicates (find_object/detect_objects/describe_scene are not oracles "
                f"and will not ground)."
            )
        )


def _scene_object_names(agent: Any) -> tuple[str, ...]:
    """Return the world's graspable object NAMES, the canonical names the oracle matches.

    Single-sourced from the SAME ground truth the ``holding_object`` oracle reads:
    the connected arm's ``get_object_positions()`` keys ARE the scene's canonical
    object names (the MuJoCo body names, e.g. "banana"). Reaching the arm via the
    duck-typed ``getattr(agent, "_arm", None)`` accessor (the oracle's own accessor)
    keeps this WORLD-AGNOSTIC — native asks whatever world is connected for its
    object vocab; no embodiment is hardcoded.

    Why this closes the cross-language gap: ``holding_object(target)`` matches
    ``target`` case-insensitively-EXACT against these keys. A model commanded in a
    NON-English language (e.g. "把香蕉抓起来") cannot guess the canonical English
    scene name on its own. Listing these names in the verify vocab lets the MODEL
    translate the user's wording to the matching scene name (LLMs do 香蕉->banana
    trivially) while the oracle stays untouched-strict.

    Fail-safe / defensive: a None agent, no arm, no ``get_object_positions``, or any
    read failure -> an EMPTY tuple. The prompt then simply omits the object list,
    which is the exact pre-step-7 behaviour. Sorted for a stable, deterministic prompt.
    """
    if agent is None:
        return ()
    arm = getattr(agent, "_arm", None)
    if arm is None:
        return ()
    getter = getattr(arm, "get_object_positions", None)
    if not callable(getter):
        return ()
    try:
        objects = getter()
    except Exception as exc:  # noqa: BLE001
        logger.debug("native_loop: get_object_positions failed: %s", exc)
        return ()
    try:
        return tuple(sorted(str(name) for name in objects))
    except Exception as exc:  # noqa: BLE001
        logger.debug("native_loop: object-name extraction failed: %s", exc)
        return ()


# ---------------------------------------------------------------------------
# Synthetic tool schemas (the verify/finish/motor tool-set the model is offered)
# ---------------------------------------------------------------------------


def _verify_teaching_tail(oracle_names: frozenset[str]) -> str:
    """Predicate-specific teaching for the verify tool description — PRESENT names only.

    Verify-vocab integrity (field forensics 2026-07-10): the kernel must never
    name a predicate the connected world does not serve. The pre-fix description
    hardcoded ``at_position(x, y, tol)`` teaching + example into EVERY world —
    a phantom on go2w_real (arrival oracle ``at``), so the kernel itself taught
    the model an oracle that resolves to nothing.

    Branches (single-sourced from the LIVE oracle set passed in):
      * ``at_position`` served (the sim worlds) -> the EXACT pre-fix teaching
        text, byte-identical (CEO ruling 2026-07-10).
      * ``at`` served (go2w_real's odometry arrival oracle) -> the same tol
        semantics taught for ``at``, WITHOUT a hardcoded default — the tol
        default lives in the world's oracle, which the kernel must not import
        (Invariant 4).
      * otherwise -> the example names a predicate from the live set (or no
        example at all when the set is empty).
    """
    if "at_position" in oracle_names:
        tol = _at_position_tol()
        return (
            f"at_position(x, y, tol={tol}) is True when the robot's planar position is "
            f"within tol metres of (x, y) (tol defaults to {tol}). "
            "Pass the FULL predicate as 'expr', e.g. at_position(2.0, 0.0)."
        )
    if "at" in oracle_names:
        return (
            "at(x, y, tol=...) is True when the robot's planar position is within "
            "tol metres of map-frame (x, y); omit tol to use the world's arrival "
            "tolerance. Pass the FULL predicate as 'expr', e.g. at(2.0, 0.0)."
        )
    if oracle_names:
        return f"Pass the FULL predicate as 'expr', e.g. {sorted(oracle_names)[0]}(...)."
    return "Pass the FULL predicate as 'expr'."


def _verify_tool_schema(oracle_names: frozenset[str]) -> dict[str, Any]:
    """Anthropic-shaped schema for the synthetic ``verify(expr)`` tool.

    The description single-sources the registry-derived verify vocab (the live
    oracle names + arrival-tol semantics for the arrival predicate ACTUALLY
    served — see ``_verify_teaching_tail``) so the model's verify expr is
    grounded in the SAME namespace ``verify_oracle_names`` reads (review fix 6),
    and never names a predicate absent from it.
    """
    names = ", ".join(sorted(oracle_names)) if oracle_names else "(none)"
    desc = (
        "Check a deterministic post-condition predicate against real world state, "
        "then bind it as this step's verification. Call this AFTER the action skill(s) "
        "that should have achieved the goal. The predicate is evaluated by an "
        "independent verifier over real sensor/sim ground truth — it cannot be faked. "
        f"Available predicate oracles: {names}. "
        + _verify_teaching_tail(oracle_names)
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
# Verify-vocab allowlist helpers (field forensics 2026-07-10) — a foreign
# predicate must be REJECTED with a corrective error, never silently evaluated
# against a leftover engine stub (stub-falsy -> 'verdict 0/N grounded').
# ---------------------------------------------------------------------------


def _sandbox_builtin_names() -> frozenset[str]:
    """The GoalVerifier sandbox's safe-builtin names (len/str/abs/...).

    Single-sourced from the sandbox itself so the allowlist gate and the eval
    can never drift; the defensive fallback mirrors the sandbox's shipped set
    (only reachable if the spine import itself breaks).
    """
    try:
        from zeno.vcli.cognitive.goal_verifier import _SAFE_BUILTINS

        return frozenset(_SAFE_BUILTINS)
    except Exception:  # noqa: BLE001 — gate must never crash a verify
        return frozenset(
            {"len", "str", "int", "float", "bool", "list", "tuple",
             "abs", "min", "max", "isinstance", "any", "all",
             "True", "False", "None"}
        )


def _called_root_names(expr: str) -> frozenset[str] | None:
    """Root names of every function CALL in *expr*; None when unparseable.

    Only CALL roots are collected (``at(1, 2)`` -> ``at``; ``a.b()`` -> ``a``) —
    bare names, comparisons, and literals stay the sandbox's business. An
    unparseable expr returns None so the existing GoalVerifier syntax handling
    (False + warning) remains the single authority on malformed input.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return None
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            root: Any = node.func
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                names.add(root.id)
    return frozenset(names)


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
        # The model's MOST-RECENT verify result (None until it verifies once). Read by
        # ``latest_verify_failed`` so the runner can refuse a finish/stop while the
        # model's own proof of the goal is still FAILING (D-quantity: a flaky brain
        # places obj-1, verifies resting_on_receptacle()>=2 -> False, then quits with
        # only one object placed). Enforces the prompt's "NEVER finish while the latest
        # verify is FAIL" mechanically + brain-agnostically; the MODEL still owns what
        # action fixes it (no goal parsing, no per-object loop here -> still planner-free).
        self._last_verify_result: bool | None = None
        # R257/E60 post-place guard: set True when a PLACE skill succeeds (gripper now
        # legitimately empty), cleared by the next verify. While True, a RE-GRASP skill
        # is refused (bounded by ``_post_place_regrasp_nudges``) so the brain must first
        # verify resting_on_receptacle instead of misreading the empty gripper as a drop
        # and re-grasping the just-placed object. Planner-free: no goal parsing, keys
        # only on the skill NAMES + the model's own next verify (rule 5).
        self._place_awaiting_verify: bool = False
        self._post_place_regrasp_nudges: int = 0
        # Backlog #2 — the most-recent INFORMATIONAL skill diagnosis seen during the
        # current step's action chain (from a dispatched skill's ToolResult.metadata).
        # Threaded onto the StepRecord at verify time so triage codes (e.g.
        # 'ran_no_weld', 'nav_failed') survive into the verdict. NEVER feeds the moat.
        self._step_diag: str | None = None

        # The assembled trace pieces (one SubGoal + one StepRecord per verify pair).
        self._sub_goals: list[SubGoal] = []
        self._steps: list[StepRecord] = []
        self._step_idx: int = 0

    @property
    def has_unverified_action(self) -> bool:
        """True iff a skill ran for the current step but no verify has closed it —
        i.e. the model is about to finish/stop WITHOUT proving the action achieved
        the goal (D23: weak models skip verify on easy tasks, yielding an empty,
        ungraded trace). Used to nudge a model-authored verify before accepting finish.
        """
        return self._step_open

    @property
    def latest_verify_failed(self) -> bool:
        """True iff the model's MOST-RECENT verify returned False (and it has verified
        at least once) — i.e. it is about to finish/stop while its OWN proof of the
        goal is still FAILING. Distinct from ``has_unverified_action`` (a ran-but-never-
        verified step): here the model DID author a verify and it FAILED. The runner
        uses this to refuse a premature finish and re-prompt (bounded), enforcing the
        prompt rule "NEVER finish while the latest verify is FAIL" — the deterministic,
        brain-agnostic guardrail for quantity/multi-object goals (the flaky-brain
        obj-2-abandon mode). It reads only the model's own latest verdict: no goal
        parsing, no per-object bookkeeping -> the loop stays planner-free (rule 5).
        """
        return self._last_verify_result is False

    @property
    def last_verify_result(self) -> bool | None:
        """The model's MOST-RECENT verify result (None until it verifies once). Read by
        the loop's goal-aware degenerate-spin guard to decide whether a verify MEASURED
        something NEW (novel (predicate,result)) versus re-read an already-known
        sub-check — the latter is not progress and must not keep resetting the counter.
        """
        return self._last_verify_result

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
        # R257/E60 post-place guard: refuse a RE-GRASP that rides on an unverified place
        # (the '掉了' misread that undoes the placement). Fires BEFORE the step opens so a
        # refused grasp neither captures a baseline nor runs the skill. Bounded, so a
        # model that will not verify still terminates (the guard can never wedge).
        if (
            self._place_awaiting_verify
            and _skill_is_grasp(tool)
            and self._post_place_regrasp_nudges < _MAX_VERIFY_NUDGES
        ):
            self._post_place_regrasp_nudges += 1
            return ToolResult(content=_POST_PLACE_REGRASP_NUDGE, is_error=True)
        if not self._step_open:
            # First skill of a fresh step -> capture the causation baseline NOW.
            self._baseline = actor_causation.capture(self._agent)
            self._step_open = True
        self._chain.append(name)
        try:
            result = tool.execute(params, self._ctx)
        except Exception as exc:  # noqa: BLE001
            logger.debug("native_loop: skill '%s' raised: %s", name, exc)
            return ToolResult(content=f"Skill '{name}' raised: {exc}", is_error=True)
        # Backlog #2 — capture an INFORMATIONAL skill diagnosis from the tool's
        # metadata (the skill wrapper passes the skill's result_data through there).
        # Keep the LAST non-empty code seen this step (the grasp/terminal action is
        # last in a chain) so handle_verify can thread it onto the StepRecord. This
        # is pure triage metadata — it never touches verify_result / actor causation.
        md = getattr(result, "metadata", None)
        if isinstance(md, dict):
            diag = md.get("diagnosis")
            if diag:
                self._step_diag = str(diag)
        # R257/E60: a SUCCESSFUL place empties the gripper on purpose -> arm the
        # post-place guard so the very next re-grasp is refused until a verify closes it.
        if _skill_is_place(tool) and not getattr(result, "is_error", False):
            self._place_awaiting_verify = True
        return result

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
        # Verify-vocab allowlist (field forensics 2026-07-10): reject a foreign
        # predicate BEFORE it can evaluate against a leftover engine stub.
        rejection = self._reject_foreign_verify(expr)
        if rejection is not None:
            return rejection
        # Evaluate the predicate via the SAME GoalVerifier sandbox the spine uses.
        try:
            verify_result = bool(self._verifier.verify(expr))
        except Exception as exc:  # noqa: BLE001
            logger.debug("native_loop: verify(%r) raised: %s", expr, exc)
            verify_result = False
        # Track the model's latest verdict so the finish-gate can refuse a stop while
        # the goal is still unproven (see ``latest_verify_failed``).
        self._last_verify_result = verify_result
        # R257/E60: a verify CLOSES the post-place guard — the brain checked the place
        # (PASS -> it should finish; FAIL quantity -> the next-object grasp may run).
        self._place_awaiting_verify = False

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
            # Backlog #2 — INFORMATIONAL triage code from the step's last action
            # skill (e.g. 'ran_no_weld'). Read by verdict._step_diagnosis as the
            # fallback after the deterministic failure_class; NEVER feeds the moat
            # (verified is delegated verbatim to evidence_passed).
            result_data=({"diagnosis": self._step_diag} if self._step_diag else {}),
        )
        self._sub_goals.append(sub_goal)
        self._steps.append(step)

        # ADR-002 Stage 3: env-gated (VECTOR_SNAPSHOT_STRIP=1), inert per-step TEMPORAL frame — a
        # PNG + base pose for the strip. Renders on THIS (the producer) thread from an isolated qpos
        # copy; a failure is swallowed so it can NEVER affect the StepRecord / verdict just built.
        try:
            from zeno.acceptance.capture import capture_strip_frame

            capture_strip_frame(self._agent, self._step_idx - 1)
        except Exception:  # noqa: BLE001 — a strip frame must never touch grading
            pass

        # Close the step: reset the action chain + baseline for the next pair. NEVER
        # carry a baseline across a verify (else the next step's causation folds in).
        # Reset the per-step diagnosis too, so a stale code can never leak forward.
        self._chain = []
        self._baseline = None
        self._step_open = False
        self._step_diag = None

        return ToolResult(
            content=(
                f"verify({expr}) -> {verify_word(verify_result)} "
                f"(result={verify_result}, actor={actor_caused.value})"
            )
        )

    def _reject_foreign_verify(self, expr: str) -> ToolResult | None:
        """Corrective rejection for an expr calling names OUTSIDE the live oracle set.

        The allowlist is ``self._oracle_names`` — the SAME set
        ``_verify_tool_schema`` advertised to the model (single source, rule 3;
        post-deny via ``verify_oracle_names``). Pre-fix, a foreign predicate
        (``at_position``/``describe_scene``/... on go2w_real) resolved to a
        leftover engine stub, evaluated falsy, and minted an honest-LOOKING but
        content-free FAIL step ('verdict 0/N grounded') with no signal that the
        predicate was phantom. Now it returns a LOUD is_error ToolResult naming
        the valid predicates so the model self-repairs, and records NO step —
        strictly stricter, never looser (Inv-1).

        Only function CALL roots are gated; the sandbox's safe builtins stay
        allowed and a malformed expr returns None (the sandbox's SyntaxError
        handling stays the single authority on garbage input).
        """
        called = _called_root_names(expr)
        if called is None:
            return None
        foreign = called - self._oracle_names - _sandbox_builtin_names()
        if not foreign:
            return None
        allowed = ", ".join(sorted(self._oracle_names)) or "(none)"
        offenders = ", ".join(sorted(foreign))
        return ToolResult(
            content=(
                f"verify REJECTED — {offenders} is not a verify predicate oracle in "
                f"this world (no step was recorded). Re-issue verify using ONLY these "
                f"predicate oracles: {allowed}."
            ),
            is_error=True,
        )

    def _grade(self, expr: str) -> "actor_causation.ActorCaused":
        """Grade actor-causation for the just-verified step (R2b + step-9 semantics).

        ROBOT predicate (base/arm/gripper, graded live in the oracle set): a fresh
        post-capture vs the step's entry baseline -> CAUSED / UNCAUSED (mirrors
        ``GoalExecutor._grade_actor_causation``). A robot-predicate step whose
        baseline is None (no skill ran) grades UNCAUSED (grade fail-closes).

        NON-ROBOT predicate (dev / state oracle — ``file_exists`` / ``path_contains``
        / a ``get_position()`` compare): actor-causation has no displacement metric.
        If NO action skill was dispatched (``self._chain`` empty), the verify reads
        pre-existing / ambient state the actor did not cause -> UNCAUSED. Since the
        2026-07-13 CEO-gated grounding semantics this is an ANNOTATION for a
        verify-only step: ``classify_step_evidence`` downgrades an UNCAUSED step
        only when it ACTED (non-empty strategy), so a passing verify-only step is a
        grounded OBSERVATION of world truth (the old STEP-9 tie reported every
        honest confirmation turn as unverified — the field 'verified=False (0/N
        grounded)' bug class). If ≥1 action
        skill ran -> NOT_GRADED (legacy-equivalent; the action plausibly produced the
        state — e.g. file_write -> path_contains stays GROUNDED). Goal AUTHENTICITY of
        the verify (does the constant match the task goal; an action + a trivial-but-
        true compare like ``len(get_position())==3``) remains the deepest residual,
        deferred — it needs the real task goal, not a structural check.

        Fail-safe to NOT_GRADED on any unexpected error (never raises).
        """
        try:
            if not actor_causation.is_robot_predicate(expr, self._oracle_names):
                # No action dispatched this step -> the actor caused nothing.
                if not self._chain:
                    return actor_causation.ActorCaused.UNCAUSED
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


def _progress_args(inp: Any) -> str:
    """A short '(k=v, …)' summary of a tool call's input for progress display."""
    if not isinstance(inp, dict) or not inp:
        return ""
    parts = []
    for k, v in inp.items():
        parts.append(f"{k}={str(v)[:18]}")
        if len(parts) >= 2:
            break
    return "(" + ", ".join(parts) + ")"


def run_turn_native(
    engine: Any,
    user_message: str,
    *,
    agent: Any | None = None,
    session: Any = None,
    app_state: dict[str, Any] | None = None,
    max_turns: int = _MAX_NATIVE_TURNS,
    on_progress: Callable[[str], None] | None = None,
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

    system_prompt = _native_system_prompt(
        engine, oracle_names, _scene_object_names(agent), has_navigate="navigate" in motor_tools
    )
    _append_user(session, user_message)

    # Progress feedback (D9 #2 perceived latency): the user's "load 好几秒" is the
    # opaque wait during the synchronous LLM round-trips. Stream the model's text
    # TAIL while it thinks (on_text deltas) and emit each tool call as it dispatches,
    # so the spinner shows live activity instead of a frozen line. Pure UX — no
    # effect on the trace, the verify spine, or routing. Fail-safe: never raises.
    def _emit(msg: str) -> None:
        if on_progress is None:
            return
        try:
            on_progress(msg)
        except Exception:  # noqa: BLE001 — progress is best-effort, never fatal
            pass

    _narration: list[str] = []

    def _on_text(chunk: str) -> None:
        _narration.append(chunk)
        tail = "".join(_narration)[-72:].replace("\n", " ").strip()
        if tail:
            _emit(tail)

    turns = 0
    verify_nudges = 0  # D23: re-prompts spent forcing a verify before a finish/stop
    # Re-prompts spent refusing a finish/stop while the model's own LATEST verify is
    # FAIL (the quantity/multi-object obj-2-abandon guardrail). Bounded like the D23
    # nudge so a model that CANNOT reach a passing verify still terminates — the trace
    # then ends on a False step and grades honestly RAN/False, never a forced green.
    finish_on_fail_nudges = 0
    # R274/E74 degenerate-spin guard: consecutive turns without MEASURABLE PROGRESS.
    # R279/E76 makes the reset GOAL-AWARE: a verify only resets the counter when it
    # measures something NEW — a (predicate, result) not seen before this loop. Re-reading
    # an already-known passing sub-check (the at_position-thrash: a flaky brain interleaves
    # ONE off-goal verify every few turns purely to keep the counter pinned) is NOT
    # progress, so those repeats let the counter climb to the honest hard break instead of
    # dodging it forever (R278 frontier: a single interleaved verify pushed worst-case
    # turns back to the _MAX_NATIVE_TURNS cap). Planner-free + brain-agnostic: keys only on
    # the model's OWN verify expr + its result, never on the goal string.
    unproductive_turns = 0
    unproductive_nudges = 0
    seen_verify_outcomes: set[tuple[str, bool]] = set()
    while turns < max_turns:
        messages = _to_messages(session)
        _narration.clear()  # fresh "thinking" tail per round-trip
        response: LLMResponse = backend.call(
            messages=messages,
            tools=tool_schemas,
            system=system_prompt,
            max_tokens=getattr(engine, "_max_tokens", 4096),
            on_text=_on_text if on_progress is not None else None,
        )
        tool_calls = list(response.tool_calls or [])
        _append_assistant(session, response, tool_calls)

        if not tool_calls:
            # D23: the model stopped (narrated, no tools). If it ran an action but
            # never verified it, force a model-authored verify before accepting the
            # stop (up to a bounded number of nudges) — else the trace is empty and
            # nothing is graded. Never invent the predicate; the model must choose it.
            if runner.has_unverified_action and verify_nudges < _MAX_VERIFY_NUDGES:
                verify_nudges += 1
                _emit("re-prompting: verify before finishing")
                _append_user(
                    session,
                    "You ran an action but did NOT verify it. You MUST call "
                    "verify(<predicate>) to PROVE the goal was achieved before you "
                    "stop. Pick the deterministic predicate that measures the goal "
                    "and call verify now.",
                )
                continue
            if runner.latest_verify_failed and finish_on_fail_nudges < _MAX_VERIFY_NUDGES:
                # The model verified and it FAILED, yet it is stopping — the goal is not
                # proven (e.g. only one of N objects placed). Re-prompt it to keep acting
                # and re-verify (brain-agnostic quantity guardrail; model still decides).
                finish_on_fail_nudges += 1
                _emit("re-prompting: last verify FAILED — keep going")
                _append_user(session, _FINISH_ON_FAIL_NUDGE)
                continue
            break  # end_turn, no tools — conversation complete

        finished = False
        # R279/E76: did the model MEASURE NEW progress this turn? True only when a verify
        # yields a (predicate, result) not seen before — a novel measurement. A re-read of
        # an already-known outcome leaves this False so the spin counter keeps climbing.
        progressed_this_turn = False
        result_dicts: list[dict[str, Any]] = []
        for tc in tool_calls:
            if tc.name == FINISH_TOOL:
                # D23: refuse a finish that rides on an unverified action — re-prompt
                # for a model-authored verify first (bounded). Honest: a model that
                # never verifies still terminates, with the action graded RAN/empty.
                if runner.has_unverified_action and verify_nudges < _MAX_VERIFY_NUDGES:
                    verify_nudges += 1
                    _emit("verify required before finish")
                    result_dicts.append(_tool_result_dict(
                        tc.id,
                        "Cannot finish yet: you ran an action but did not verify it. "
                        "Call verify(<predicate>) to PROVE the goal FIRST, then finish.",
                        is_error=True,
                    ))
                    continue
                if runner.latest_verify_failed and finish_on_fail_nudges < _MAX_VERIFY_NUDGES:
                    # The model DID verify but it FAILED, and it is trying to finish
                    # anyway — refuse (bounded). This is the quantity/multi-object
                    # guardrail: obj-1 placed, resting_on_receptacle()>=N still False,
                    # brain quits. Push it to place the NEXT object and re-verify.
                    finish_on_fail_nudges += 1
                    _emit("finish blocked: last verify FAILED")
                    result_dicts.append(_tool_result_dict(
                        tc.id, _FINISH_ON_FAIL_NUDGE, is_error=True,
                    ))
                    continue
                _emit("finishing")
                finished = True
                result_dicts.append(_tool_result_dict(tc.id, "Task finished."))
                continue
            if tc.name == VERIFY_TOOL:
                expr = str((tc.input or {}).get("expr", ""))
                _emit(f"verify {expr[:56]}")
                res = runner.handle_verify(expr)
                # R279/E76 goal-aware reset: a verify is PROGRESS only if it measures a
                # (normalized predicate, result) not seen before. Re-reading the same
                # already-known outcome (the at_position-thrash) is not progress.
                # A REJECTED verify (is_error: foreign predicate — nothing evaluated,
                # no step) is NEVER progress: without this guard a stale non-None last
                # result would mint a novel key per rejected spelling and pin the R274
                # spin counter open. handle_verify never errors on an ACCEPTED verify,
                # so accepted verifies are byte-identical. Strictly stricter (rule 5).
                key = (" ".join(expr.split()), runner.last_verify_result)
                if (
                    not res.is_error
                    and runner.last_verify_result is not None
                    and key not in seen_verify_outcomes
                ):
                    seen_verify_outcomes.add(key)
                    progressed_this_turn = True
            else:
                _emit(f"{tc.name} {_progress_args(tc.input)}".strip())
                res = runner.dispatch_skill(tc.name, dict(tc.input or {}))
            result_dicts.append(_tool_result_dict(tc.id, res.content, res.is_error))

        _append_tool_results(session, result_dicts)
        turns += 1
        if finished:
            break

        # R274/E74 degenerate-spin guard (runs AFTER a non-empty tool-call turn that did
        # not finish). R279/E76: a NOVEL verify (new (predicate,result)) RESETS the counter
        # — real progress was measured; a skill-only turn OR a re-read of an already-known
        # outcome increments it. At the soft threshold nudge ONCE to force a measurement; at
        # the hard threshold break to an honest fail. Never fires on a healthy task (which
        # keeps measuring NEW state within a few turns) — only on the never-verify
        # perception/nav spin OR a thrash that dodges the break by re-reading one sub-check.
        if progressed_this_turn:
            unproductive_turns = 0
        else:
            unproductive_turns += 1
            if (
                unproductive_turns == _UNPRODUCTIVE_NUDGE_AT
                and unproductive_nudges < _MAX_VERIFY_NUDGES
            ):
                unproductive_nudges += 1
                _emit("re-prompting: measure progress with verify")
                _append_user(session, _UNPRODUCTIVE_SPIN_NUDGE)
                continue
            if unproductive_turns >= _MAX_TURNS_WITHOUT_VERIFY:
                _emit("degenerate spin: no verify progress — stopping honestly")
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
    from zeno.vcli.cognitive.goal_verifier import GoalVerifier

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
    # Source 2: the engine registry's code tools (present in every world). In a ROBOT
    # world (a connected robot ``agent``), the MUTATING code tools (file_write/file_edit/
    # bash) are DROPPED from the action surface — a physical robot goal must be achieved
    # by a robot SKILL and proven by a GT oracle, never by writing a marker file or
    # running a shell command (the D17 fakeable-grasp path). The READ-ONLY diagnostics
    # (file_read/glob/grep) are kept so the persona can still inspect code. The dev world
    # (no robot agent) keeps the full set unchanged.
    is_robot_world = agent is not None
    for name, code_tool in _code_tools_from_registry(engine).items():
        if is_robot_world and name in _MUTATING_CODE_TOOLS:
            continue  # Prong 1: no file/shell WRITE as a path to a physical robot task
        tools[name] = code_tool
    # Source 3 (D9 #1): the avoidance NAVIGATION route, only for a world with a mobile
    # base (go2). ``publish_goal`` -> FAR/local planner/lidar, so "go to a place/
    # coordinate" AVOIDS obstacles instead of blind-walking into them. cmd_vel is gated
    # out of actor-causation -> a navigate step honestly grades RAN (the moat never
    # loosens). The arm/dev worlds (no base) do not get it. The base gate is single-
    # sourced (Rule 11) onto the capability resolver — byte-identical to the prior
    # ``agent is not None and agent._base is not None`` (resolver -> has_base False for
    # a None agent), so the navigate/base/camera gates can never drift apart.
    from zeno.embodiments.capability_profile import resolve_capability_profile

    if resolve_capability_profile(agent).has_base:
        tools["navigate"] = _NativeBaseNavigateTool()
    # Source 4 (R4): the learned grounding-dino DETECTOR capability, surfaced into the
    # native loop so a bare-cli detect command reaches the SECOND model family on
    # whatever camera-bearing embodiment is connected (go2+arm OR g1). Single-sourced
    # from the engine's CapabilityRegistry — the SAME instance the world registered
    # (agent-bound for the live perception), never a second model load. Only present
    # when a 'detect' capability is registered (camera present + torch importable);
    # a sensorless/dev path never sees it. Layered before the world skills so this
    # learned route WINS over the classical DetectSkill if both share the 'detect' name
    # (R4 intent: the bare-cli 'detect' is the MODEL route, not the keyword skill).
    detect_cap = _registered_capability(engine, "detect")
    if detect_cap is not None:
        tools["detect"] = _NativeDetectTool(detect_cap)
    # Source 1: the world's skills (robot worlds only; dev world has no agent). The
    # world's own ``navigate`` skill (door-chain walk, NOT lidar avoidance) stays
    # excluded; our coordinate ``navigate`` above is the planner/avoidance route.
    if agent is not None:
        # Capability gate (Rule 11 single-source): a body without an arm is not offered
        # manipulation skills — same resolver the navigate/base gate reads above.
        has_arm = resolve_capability_profile(agent).has_arm
        try:
            for skill_tool in wrap_skills(agent):
                if skill_tool.name == "navigate":
                    continue  # world room-navigate is door-chain walk; ours is the avoidance route
                if skill_tool.name == "detect" and "detect" in tools:
                    continue  # the learned grounding-dino route (Source 4) wins over the classical DetectSkill
                if not has_arm and _skill_needs_arm(skill_tool):
                    continue  # armless embodiment (g1): no manipulation tools it can't execute
                    # (name-list OR the skill's own arm/gripper metadata — plug-and-play safe)
                tools[skill_tool.name] = skill_tool
        except Exception as exc:  # noqa: BLE001
            logger.debug("native_loop: wrap_skills failed: %s", exc)
    return tools


def should_attempt_native(user_input: str, *, agent: Any, engine: Any) -> bool:
    """REGISTRY-DRIVEN native-attempt hint (S5c) — the replacement for the keyword router.

    The native producer routes by the MODEL reading tool DESCRIPTIONS, not a keyword
    table — so the only PRE-gate question ("is it worth attempting native?") collapses
    to "does this world expose any actionable tool the model could dispatch?". That is
    derived SINGLE-SOURCE from ``_build_motor_tools`` (the EXACT toolset the native loop
    offers; Rule 3), never from ``IntentRouter._RULES`` / ``should_use_vgg`` keyword sets.

    FAIL-OPEN by design: when the world is actionable, attempt native and let the model
    decide routing — a goal it cannot route falls back to legacy on no-action (a wasted
    LLM call, NEVER a missed command). This makes the hint a SAFE SUPERSET of the keyword
    ``should_use_vgg`` **WITHIN AN ACTIONABLE WORLD** (proven in
    tests/vcli/test_native_routing_hint.py): for every input the keyword router routes to
    VGG, this also attempts — so S8 can rewire the gate sites off ``should_use_vgg`` onto
    this with no missed routing. The superset is SCOPED to an actionable world by
    construction: in a TOOLLESS world (``_build_motor_tools`` empty — a sensorless/dev path)
    this returns False even for an action-shaped command, which is CORRECT (nothing for the
    model to route to; the keyword router's VGG attempt would only fail there too). The
    trivial-input threshold MATCHES ``should_use_vgg`` exactly (``len(user_input) < 2`` on the
    RAW input — NOT stripped — so a 1-char-after-strip command like "去 " that ``should_use_vgg``
    accepts is not silently dropped; the earlier ``len(strip())`` was an off-by-strip MISS,
    D79). A toolset-build error fails OPEN to native. SHADOW for now: not wired into live routing.
    """
    if not user_input or len(user_input) < 2:
        return False
    try:
        tools = _build_motor_tools(agent, engine)
    except Exception:  # noqa: BLE001 — fail OPEN to native; never silently skip the redesign
        return True
    return len(tools) >= 1


def _registered_capability(engine: Any, name: str) -> Any:
    """The named Capability the world registered into the engine's CapabilityRegistry.

    Reaches the LIVE registry through ``engine._goal_executor._capability_registry``
    (the same registry the producer/StrategySelector route uses) so the native loop
    surfaces the EXACT capability instance the world bound to the agent — never a fresh
    construction, never a second model load (rule 3). Defensive: any missing link
    (no executor, no registry, lookup failure) yields None and the capability simply
    is not surfaced (the pre-R4 behaviour — native offered no detector).
    """
    executor = getattr(engine, "_goal_executor", None)
    registry = getattr(executor, "_capability_registry", None) if executor is not None else None
    if registry is None:
        return None
    getter = getattr(registry, "get", None)
    if not callable(getter):
        return None
    try:
        return getter(name)
    except Exception as exc:  # noqa: BLE001
        logger.debug("native_loop: capability lookup %r failed: %s", name, exc)
        return None


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


def _native_system_prompt(
    engine: Any,
    oracle_names: frozenset[str],
    object_names: tuple[str, ...] = (),
    has_navigate: bool = False,
) -> list[dict[str, Any]]:
    """A minimal native system prompt, single-sourcing the verify vocab.

    Anthropic 'system' is a list of text blocks; the verify-vocab (oracle names +
    at_position tol) is taken from the SAME source ``verify_oracle_names`` reads, so
    the model's verify expr is grounded in the live namespace (review fix 6).

    ``object_names`` (step 7) is the connected world's graspable object vocab — the
    canonical scene names the ``holding_object`` oracle matches against, single-
    sourced from the world via ``_scene_object_names``. When non-empty, the prompt
    lists them so a model commanded in ANY language passes the CANONICAL scene name
    to ``holding_object('<name>')`` (it translates the user's wording, e.g.
    香蕉->banana) and the strictly-canonical oracle still matches. An EMPTY tuple
    (no world objects exposed) omits the list — the exact pre-step-7 prompt.
    """
    names = ", ".join(sorted(oracle_names)) if oracle_names else "(none)"
    tol = _at_position_tol()
    # Step 7: when the world exposes graspable object names, teach them so the model
    # verifies with the CANONICAL scene name regardless of the command's language.
    if object_names:
        object_vocab = (
            f"The scene's graspable objects are: {', '.join(object_names)}. "
            "Always pass one of these EXACT scene names (English) as the QUOTED argument "
            "to holding_object, translating the user's wording (in any language) to the "
            "matching scene name — e.g. a request to grasp 香蕉 / the banana is verified "
            "with holding_object('banana'). "
        )
    else:
        object_vocab = ""
    # Compound FETCH-AND-PLACE guidance (frontier: a single utterance that both fetches
    # AND places one object, e.g. "把红色的罐子拿过来放到架子上"). Gated on a manipulation
    # world (object_names present -> the mobile_place skill + resting_on_receptacle oracle
    # exist). The combo failure mode: the sentence LEADS with a fetch word (拿过来) that the
    # grasp guidance matches, so the model grasps, verifies holding_object, and finishes —
    # dropping the trailing place clause. This teaches the two-action compound WITHOUT any
    # runner-side clause parsing (the MODEL still decides; the runner stays planner-free).
    if object_names:
        place_guidance = (
            "FETCH-AND-PLACE (one object, TWO actions): if the request asks you to not "
            "just fetch / bring an object but ALSO put or place it somewhere — e.g. "
            "'拿过来放到架子上', '放到...上', 'put it on the shelf', 'place it on the "
            "receptacle' — then grasping is only HALF the task. Even when the sentence "
            "LEADS with a fetch / bring word (拿 / 拿过来 / bring / fetch), the trailing "
            "place clause STILL STANDS and you must NOT finish after only the grasp. Do "
            "this: (1) grasp the object and verify holding_object('<name>') PASSES, then "
            "(2) call the place skill mobile_place — it auto-resolves the scene's place "
            "receptacle, so call it with NO target argument — then (3) verify "
            "resting_on_receptacle() PASSES, and ONLY THEN finish. NEVER finish after "
            "only the grasp when the request also asked to place the object. "
            "CRITICAL — a place-on-a-receptacle clause is NOT a navigation goal: the "
            "receptacle (shelf/table/box) is NOT a coordinate to drive to. mobile_place "
            "walks to it ITSELF and drops. Do NOT use navigate / walk / at_position to "
            "'reach the shelf' or invent a coordinate for the receptacle and loop "
            "navigate until at_position passes — that is the #1 way this fails (the "
            "robot walk-loops to a made-up coordinate and never places). The ONLY way to "
            "satisfy a place clause is mobile_place -> verify resting_on_receptacle(). "
            # QUANTITY place (R198/E35): "把两个瓶子放到架子上" / "put two bottles on the
            # shelf" / N objects onto the SAME receptacle. resting_on_receptacle() RETURNS A
            # COUNT, so the goal predicate is resting_on_receptacle() >= N. The gripper holds
            # ONE at a time, so this is N sequential grasp->place cycles, NOT one call.
            "QUANTITY place — putting MORE THAN ONE object onto the receptacle (e.g. "
            "'把两个瓶子放到架子上', 'put two bottles on the shelf', 'both bottles onto the "
            "bin'): the gripper holds ONE object at a time, so do the objects ONE AT A TIME. "
            "For EACH object in turn: (1) grasp it (grasp skill, first action) and verify "
            "holding_object('<name>') PASSES, then (2) mobile_place (no target arg) to drop "
            "it on the receptacle. Do NOT gripper_open to release in mid-air between objects "
            "(that is for a fetch-and-drop, not a place-on-the-receptacle) — mobile_place "
            "already releases onto the shelf. After ALL N objects are placed, verify the "
            "QUANTITY with resting_on_receptacle() >= N (the oracle COUNTS objects on the "
            "receptacle, e.g. resting_on_receptacle() >= 2 for two bottles) and ONLY THEN "
            "finish. Do NOT finish after placing just one when more were requested. If a "
            "grasp comes back no_detections (the just-placed object left the dog docked too "
            "close to see the next), call navigate_to_object('<next name>') once, then grasp. "
            # POST-PLACE (R255/R256/E60 courtyard flake): mobile_place RELEASES the object
            # onto the receptacle, so an empty gripper afterwards is CORRECT, not a drop. The
            # brain re-grasped the just-placed bottle off the bin ('掉了。让我重新抓取它。'),
            # undoing the place. Teach: after a place, check resting_on_receptacle, never
            # holding_object/describe; an empty gripper is expected; do NOT re-grasp.
            "AFTER A PLACE — an EMPTY gripper is EXPECTED, NOT a drop: the place skill "
            "(mobile_place) RELEASES the object onto the receptacle, so once it returns your "
            "gripper is CORRECTLY empty and holding_object('<name>') is now False BY DESIGN. "
            "This is SUCCESS, not an accidental drop ('掉了'). Do NOT re-grasp / re-pick / "
            "mobile_pick the object you just placed, and do NOT call describe or "
            "holding_object to 'check' after a place — that is exactly how the placement gets "
            "UNDONE (you grab the object right back off the receptacle). The ONLY correct check "
            "after a place is verify(resting_on_receptacle() >= <requested count>): if it "
            "PASSES, the task is DONE — call finish immediately. Only grasp again when that "
            "resting_on_receptacle count is still BELOW the requested number (a quantity task "
            "with more objects left to place). "
        )
    else:
        place_guidance = ""
    # Locomotion guidance: when the avoidance NAVIGATION route is available (a world
    # with a mobile base, D9 #1) the model REACHES a place/coordinate via navigate(x, y)
    # — the planner avoids obstacles — and uses walk only for an explicit relative step.
    # Without it, fall back to the open-loop walk-toward-coordinate guidance.
    if has_navigate:
        locomotion_guidance = (
            f"at_position(x, y, tol={tol}) is True when the robot is within tol metres "
            "of (x, y). To reach an EXPLICIT coordinate (x, y) or named location the "
            "USER gave, call navigate(x, y): it "
            "routes through the planner and AVOIDS obstacles (lidar + local planner). Do "
            "NOT walk toward a far target — walk is OPEN-LOOP and collides with anything "
            "in the way; use walk ONLY for an explicit short relative step the user asked "
            "for (e.g. 'walk forward 2m'). After navigate, verify at_position(x, y). "
            "CRITICAL — RECOVER on failure: if a verify returns FAIL, call navigate(x, y) "
            "AGAIN and re-verify, repeating until at_position PASSES. NEVER call finish "
            "while the latest verify is FAIL. Only finish once a verify has PASSED."
        )
    else:
        locomotion_guidance = (
            f"at_position(x, y, tol={tol}) is True when the robot is within tol metres of "
            "(x, y). To reach a target coordinate, walk toward it (a forward walk "
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
    text = (
        "You control a robot through tools. For each goal: call the MOTION skill or "
        "navigate that achieves it, then IMMEDIATELY call verify(expr) with a "
        "deterministic predicate to PROVE the goal was achieved, then call finish. "
        "A PHYSICAL action (grasp / pick / 抓 / 拿 / walk / navigate / place) is performed "
        "ONLY by the robot SKILL for it and proven ONLY by a ground-truth oracle. NEVER "
        "simulate or stand in for a physical action by writing a file, creating a marker, "
        "or running a shell command — a grasp is real only when the GRIPPER holds the "
        "object (holding_object), never when a file says so. If no skill can do it, say so "
        "and stop; do NOT fake it. "
        "verify reads the real world state itself, so do NOT call a read-only "
        "status/query skill (e.g. where_am_i, look) before verify — the motion "
        "action must be the LAST action call before each verify. "
        f"Available verify predicate oracles: {names}. "
        "Choose the predicate that MEASURES the goal quantity: a goal of reaching a "
        "place/coordinate is proven by at_position (a position check), NOT by a "
        "scene/description oracle. "
        "A goal of picking up / grasping an object is proven by the holding_object(...) "
        "gripper oracle: call holding_object('<name>') with the object's scene name as a "
        "QUOTED string, e.g. holding_object('banana'), to prove you grasped THAT specific "
        "object (a bare word without quotes is not a valid argument). "
        "To DO the grasp, call the grasp / pick skill DIRECTLY and as your FIRST action — it "
        "is the COMPLETE grasp: in ONE call it PERCEIVES the target from the robot's camera, "
        "WALKS the robot to it on its own (obstacle-aware), AND grasps. Because it does all "
        "of that itself, you must NOT take any separate step before it: do NOT navigate / "
        "walk toward the object, do NOT detect it, do NOT scan, do NOT look or describe the "
        "scene first — every one of those is unnecessary and is the #1 way the goal stays "
        "UNMET (you burn your turns moving/looking and never actually grasp). The single "
        "biggest mistake here is calling navigate or detect instead of the grasp skill: "
        "don't. Commit to the grasp skill on the FIRST action, then verify holding_object(...). "
        "RECOVERY (only after a failure): if — and ONLY if — the grasp skill comes back "
        "reporting it could NOT see or reach the target (a result such as 'no_detections', it "
        "perceived nothing, or the object is too far to reach), then the object is out of reach "
        "from where you stand: call navigate_to_object('<name>') ONCE to drive up to it, then "
        "call the grasp skill again. Do this ONLY as recovery in response to that specific "
        "failure — NEVER as a preemptive first step (a preemptive navigate/detect is still the "
        "#1 way an in-reach grasp needlessly fails). "
        "MULTIPLE objects: if the user names MORE THAN ONE object to fetch / grasp (e.g. 'the "
        "green AND the blue one', a list, or 都/all), fetch them ONE AT A TIME — the gripper "
        "holds only ONE object at a time. For each named object in turn: grasp it, verify "
        "holding_object('<that object>') PASSES, THEN call gripper_open to RELEASE it before "
        "moving to the next (a new grasp cannot succeed while the gripper is still holding the "
        "previous object). After releasing, the robot is left docked CLOSE to where it just "
        "grasped — too close to see the next object — so before the NEXT grasp, back off to a "
        "viewing distance: walk backward about 0.8 m (walk direction='backward' distance=1.0), "
        "OR navigate_to_object('<next object>') if it returns no_detections. Only call finish "
        "once EVERY named object has had its OWN passed holding_object verify — never finish "
        "after grasping just one when more were named. "
        "BRING / FETCH IS COMPLETE AT THE HOLD: a plain request to bring / fetch / 拿 / 拿来 / "
        "拿过来 an object — with NO explicit place clause and NO explicit hand-over request — is "
        "FULLY satisfied the moment holding_object('<name>') PASSES; finish THERE. Do NOT call "
        "handover afterwards: handover RELEASES the object, which makes holding_object FAIL and "
        "UNDOES the fetch you just proved. Holding the object IS the delivery. Call handover "
        "ONLY when the user EXPLICITLY asks you to hand it over / give it to them (递给我 / 给我 / "
        "hand it to me / pass it to me); a bare 拿过来 (bring it over) is NOT such a request. "
        "SPATIAL / ORDINAL references (最左边的 / 最右边的 / 中间的 / leftmost / rightmost / "
        "middle / the one on the left): pass the user's phrase VERBATIM as the grasp target "
        "(e.g. query='最左边的瓶子') — do NOT decide yourself which COLOUR that position is and "
        "do NOT substitute a colour word. The grasp skill resolves the ordinal position "
        "deterministically from the camera geometry; if you guess the colour you will pick the "
        "WRONG object (leftmost is NOT a fixed colour — it depends on the live scene). Keep the "
        "category noun (瓶子/bottle, 罐子/can) in the phrase so the skill filters to it. "
        + place_guidance
        + object_vocab
        + locomotion_guidance
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
