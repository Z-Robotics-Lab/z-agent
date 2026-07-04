# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""M1 unit tests — native tool-use producer (run_turn_native + NativeStepRunner).

Deterministic, no MuJoCo, no network: a ``FakeToolScriptBackend`` replays a SCRIPT
of native tool_use turns through the REAL ``run_turn_native``, against a duck-typed
fake agent (a base exposing the actor-causation surface + a registered walk skill).

Pinned here (the RED-0 tripwire + the review fixes):
- (RED-0) the tool-script backend drives run_turn_native to the EXPECTED ordered
  tool calls (walk -> verify -> finish), and the legacy single-plan FakeBackend
  constructor is byte-identical (unchanged).
- (fix 2 granularity) N bare walks then ONE verify -> exactly ONE StepRecord whose
  strategy is the last walk; intermediate walks are NOT each a checked sub-goal.
- (fix 3 timing + spine parity) an HONEST walk -> CAUSED -> GROUNDED -> verified;
  a verify-only NO-OP (predicate true at baseline, no walk) -> UNCAUSED -> RAN ->
  NOT verified; verified == evidence_passed (the spine, not a re-derivation).
- (replan-via-model) a False verify is followed by ANOTHER model-issued walk +
  verify — the runner holds NO replan/iteration state; the trace has both pairs.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.harness.fake_backend import (
    FakeBackend,
    FakeToolScriptBackend,
    tool_turn,
)
from vector_os_nano.vcli.cognitive.actor_causation import ActorCaused
from vector_os_nano.vcli.cognitive.trace_store import (
    evidence_passed,
    verify_oracle_names,
)
from vector_os_nano.vcli.session import Session
from vector_os_nano.vcli.verdict import VerdictReport


# ---------------------------------------------------------------------------
# Fakes — a base on the actor-causation surface + a registered walk skill
# ---------------------------------------------------------------------------


class _FakeBase:
    """Go2-base stand-in: instrumented commanded-motion counter + pose.

    ``walk`` advances the commanded-motion counter AND displaces the pose (an
    honest, actor-caused move). ``cmd_motion`` / ``get_position`` / ``get_heading``
    are the SAME accessors actor_causation.capture reads.
    """

    # mark as a sim adapter so SkillWrapperTool auto-allows the motor skill.
    __module__ = "vector_os_nano.hardware.sim.fake"

    def __init__(self, x: float, y: float) -> None:
        self._x, self._y, self._yaw = float(x), float(y), 0.0
        self._cmd_motion = 0.0
        self._connected = True

    def get_position(self) -> list[float]:
        return [self._x, self._y, 0.0]

    def get_heading(self) -> float:
        return self._yaw

    def cmd_motion(self) -> float:
        return self._cmd_motion

    def walk(self, vx: float, vy: float, vyaw: float, duration: float) -> bool:
        # Command magnitude + a real displacement -> CAUSED.
        self._cmd_motion += abs(vx) + abs(vy) + abs(vyaw)
        self._x += vx * duration
        self._y += vy * duration
        return True


class _FakeWalkSkill:
    """Minimal Skill-protocol walk: drives base.walk, no auto_steps."""

    name = "walk"
    description = "Walk the quadruped forward by a given distance (moves the base)."
    parameters = {
        "distance": {"type": "number", "required": False, "default": 1.0},
        "speed": {"type": "number", "required": False, "default": 0.3},
    }
    preconditions = ["base"]
    effects = {"is_moving": False}

    def execute(self, params, context):
        from vector_os_nano.core.types import SkillResult

        base = context.base
        if base is None:
            return SkillResult(success=False, error_message="no base", diagnosis_code="no_base")
        distance = float(params.get("distance", 1.0))
        speed = float(params.get("speed", 0.3))
        duration = distance / speed if speed > 0 else 0.0
        base.walk(speed, 0.0, 0.0, duration)
        return SkillResult(success=True, result_data={"distance": distance})


def _make_agent(x: float = 0.0, y: float = 0.0):
    """A duck-typed agent: a fake base + a real SkillRegistry with the walk skill."""
    from vector_os_nano.core.skill import SkillRegistry

    base = _FakeBase(x, y)
    reg = SkillRegistry()
    reg.register(_FakeWalkSkill())
    agent = SimpleNamespace(
        _base=base,
        _arm=None,
        _gripper=None,
        _spatial_memory=None,
        _skill_registry=reg,
    )

    def _build_context():
        return SimpleNamespace(base=base, arm=None, gripper=None, services=None)

    def _sync_robot_state():
        return None

    agent._build_context = _build_context
    agent._sync_robot_state = _sync_robot_state
    return agent, base


def _make_engine(agent, backend):
    """A REAL VectorEngine wired for VGG over the fake agent + a scripted backend."""
    from vector_os_nano.vcli.engine import VectorEngine
    from vector_os_nano.vcli.permissions import PermissionContext
    from vector_os_nano.vcli.tools.base import CategorizedToolRegistry
    from vector_os_nano.vcli.worlds.robot import RobotWorld

    eng = VectorEngine(
        backend=backend,
        registry=CategorizedToolRegistry(),
        permissions=PermissionContext(),
    )
    eng._world = RobotWorld()
    eng.init_vgg(agent=agent, skill_registry=agent._skill_registry, world=RobotWorld())
    eng._vgg_agent = agent
    eng._backend = backend
    return eng


def _session() -> Session:
    return Session(
        session_id="native-test",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        path=Path("/tmp/native_test_session.jsonl"),
    )


# ---------------------------------------------------------------------------
# RED-0 — the tool-script backend + run_turn_native ordered drive
# ---------------------------------------------------------------------------


def test_legacy_fake_backend_constructor_unchanged() -> None:
    """The single-plan FakeBackend constructor is byte-identical (legacy seam)."""
    fb = FakeBackend({"goal": "g", "sub_goals": []})
    resp = fb.call(messages=[], tools=[], system=[], max_tokens=10)
    assert resp.stop_reason == "end_turn"
    assert resp.tool_calls == []
    assert "sub_goals" in resp.text


def test_tool_script_replays_ordered_turns() -> None:
    """from_tool_script replays the SEQUENCE; run_turn_native dispatches in order."""
    calls: list[str] = []

    class _Recorder(FakeToolScriptBackend):
        def call(self, **kw):  # type: ignore[override]
            # record the order the loop drives the model
            r = super().call(**kw)
            calls.append(",".join(tc.name for tc in r.tool_calls) or "end")
            return r

    backend = _Recorder.from_tool_script(
        [
            tool_turn(("walk", {"distance": 2.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 5.0)"})),
            tool_turn(end=True),
        ]
    )
    agent, _base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("walk somewhere then verify", session=_session())

    # Ordered drive: walk turn, then verify turn, then terminal end_turn.
    assert calls == ["walk", "verify", "end"]
    # Exactly ONE recorded (action-chain -> verify) step.
    assert len(trace.steps) == 1
    assert trace.steps[0].strategy == "walk"


# ---------------------------------------------------------------------------
# fix 2 — ONE StepRecord per (action-chain -> verify) pair, not per walk
# ---------------------------------------------------------------------------


def test_three_walks_then_one_verify_is_one_step() -> None:
    """3 bare walks then 1 verify -> a single GROUNDED step (intermediate walks
    are NOT each a checked sub-goal; no sentinel-verify of intermediates)."""
    backend = FakeToolScriptBackend.from_tool_script(
        [
            tool_turn(("walk", {"distance": 1.0, "speed": 0.3})),
            tool_turn(("walk", {"distance": 1.0, "speed": 0.3})),
            tool_turn(("walk", {"distance": 1.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(3.0, 0.0, 1.0)"})),
            tool_turn(("finish", {})),
        ]
    )
    agent, base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("walk 3m then verify", session=_session())

    assert len(trace.steps) == 1, "3 walks + 1 verify must be ONE checked step"
    step = trace.steps[0]
    assert step.verify_result is True
    assert step.actor_caused is ActorCaused.CAUSED
    # The honest-spine verdict: GROUNDED + verified.
    oracle_names = verify_oracle_names(agent, eng)
    report = VerdictReport.from_trace(trace, oracle_names)
    assert report.verified is True
    assert report.evidence == "GROUNDED"
    assert report.verified == evidence_passed(trace, oracle_names)


# ---------------------------------------------------------------------------
# fix 3 + spine parity — HONEST CAUSED vs NO-OP UNCAUSED through the producer
# ---------------------------------------------------------------------------


def test_honest_walk_is_caused_and_verified() -> None:
    backend = FakeToolScriptBackend.from_tool_script(
        [
            tool_turn(("walk", {"distance": 2.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(2.0, 0.0, 1.0)"})),
            tool_turn(("finish", {})),
        ]
    )
    agent, base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("go to (2,0)", session=_session())
    oracle_names = verify_oracle_names(agent, eng)
    report = VerdictReport.from_trace(trace, oracle_names)

    assert trace.steps[0].actor_caused is ActorCaused.CAUSED
    assert report.verified is True and report.evidence == "GROUNDED"
    assert report.verified == evidence_passed(trace, oracle_names)
    assert base.get_position()[0] > 1.5  # actually moved


def test_noop_verify_only_is_uncaused_and_not_verified() -> None:
    """verify-only (no walk), predicate true at baseline -> UNCAUSED -> RAN."""
    backend = FakeToolScriptBackend.from_tool_script(
        [
            tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 1.0)"})),
            tool_turn(("finish", {})),
        ]
    )
    agent, base = _make_agent(0.0, 0.0)  # already at (0,0) -> predicate true
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("claim you're at (0,0)", session=_session())
    oracle_names = verify_oracle_names(agent, eng)
    report = VerdictReport.from_trace(trace, oracle_names)

    step = trace.steps[0]
    assert step.verify_result is True, "predicate is true at baseline"
    assert step.actor_caused is ActorCaused.UNCAUSED, "no commanded motion"
    assert report.verified is False and report.evidence == "RAN"
    assert report.exit_code() == 2
    assert report.verified == evidence_passed(trace, oracle_names)


# ---------------------------------------------------------------------------
# replan-via-MODEL — the runner holds NO replan state; the model re-issues
# ---------------------------------------------------------------------------


def test_replan_is_model_driven_not_runner_state() -> None:
    """A False verify is followed by ANOTHER model walk+verify. Both pairs are
    recorded; the runner computed no 'retry' state. The final trace verifies only
    when EVERY checked step is GROUNDED, so a False first step keeps it unverified."""
    backend = FakeToolScriptBackend.from_tool_script(
        [
            tool_turn(("walk", {"distance": 0.3, "speed": 0.3})),  # lands short
            tool_turn(("verify", {"expr": "at_position(3.0, 0.0, 0.5)"})),  # FAIL
            tool_turn(("walk", {"distance": 3.0, "speed": 0.3})),  # the model retries
            tool_turn(("verify", {"expr": "at_position(3.0, 0.0, 0.5)"})),  # PASS
            tool_turn(("finish", {})),
        ]
    )
    agent, base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("go to (3,0), retry if short", session=_session())

    # TWO (action-chain -> verify) pairs recorded — the MODEL re-issued, the runner
    # did not loop internally.
    assert len(trace.steps) == 2
    assert trace.steps[0].verify_result is False  # the short attempt
    assert trace.steps[1].verify_result is True   # the corrected attempt
    oracle_names = verify_oracle_names(agent, eng)
    report = VerdictReport.from_trace(trace, oracle_names)
    # A trace with ANY non-GROUNDED checked step is NOT verified (all-must-pass).
    assert report.verified is False


def test_empty_script_yields_unverified_empty_trace() -> None:
    """No verify ever called -> empty trace -> fail closed (not verified)."""
    backend = FakeToolScriptBackend.from_tool_script([tool_turn(end=True)])
    agent, _ = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("do nothing", session=_session())
    oracle_names = verify_oracle_names(agent, eng)
    report = VerdictReport.from_trace(trace, oracle_names)
    assert len(trace.steps) == 0
    assert report.verified is False


# ---------------------------------------------------------------------------
# STEP 7 — cross-language grasp vocab: the native loop hands the MODEL the
# world's CANONICAL object names so a non-English command verifies the STRICT
# object-specific predicate, while the oracle stays untouched-strict.
# ---------------------------------------------------------------------------


class _FakeArmWithObjects:
    """Duck-typed arm exposing get_object_positions (the single-source vocab)."""

    def __init__(self, objects):
        self._objects = objects

    def get_object_positions(self):
        return self._objects


def _arm_agent(objects):
    return SimpleNamespace(_arm=_FakeArmWithObjects(objects))


def test_scene_object_names_single_sources_canonical_names() -> None:
    """``_scene_object_names`` returns the arm's object-position keys, sorted.

    This is the SAME ground truth ``holding_object`` matches against, so the names
    the model is taught are exactly the names the oracle accepts (no split source).
    """
    from vector_os_nano.vcli.native_loop import _scene_object_names

    agent = _arm_agent({"banana": [0.1, 0.1, 0.06], "mug": [0.2, 0.0, 0.06]})
    assert _scene_object_names(agent) == ("banana", "mug")


def test_scene_object_names_fail_safe_empty() -> None:
    """No agent / no arm / no getter / raising getter -> EMPTY (pre-step-7 prompt)."""
    from vector_os_nano.vcli.native_loop import _scene_object_names

    assert _scene_object_names(None) == ()
    assert _scene_object_names(SimpleNamespace(_arm=None)) == ()
    assert _scene_object_names(SimpleNamespace(_arm=SimpleNamespace())) == ()

    class _Raises:
        def get_object_positions(self):
            raise RuntimeError("boom")

    assert _scene_object_names(SimpleNamespace(_arm=_Raises())) == ()


def test_system_prompt_lists_object_vocab_when_present() -> None:
    """The prompt teaches the canonical names + the translate-to-scene-name rule."""
    from vector_os_nano.vcli.native_loop import _native_system_prompt

    blocks = _native_system_prompt(None, frozenset({"holding_object"}), ("banana", "mug"))
    text = blocks[0]["text"]
    assert "graspable objects are: banana, mug" in text
    # The rule that closes the cross-language gap: translate the user's wording to
    # the canonical scene name (the model does 香蕉->banana itself).
    assert "translating the user's wording" in text
    assert "holding_object('banana')" in text


def test_system_prompt_omits_object_vocab_when_empty() -> None:
    """An EMPTY object set yields the EXACT pre-step-7 prompt (no object list)."""
    from vector_os_nano.vcli.native_loop import _native_system_prompt

    with_names = _native_system_prompt(None, frozenset({"holding_object"}), ("banana",))
    without = _native_system_prompt(None, frozenset({"holding_object"}), ())
    assert "graspable objects are" not in without[0]["text"]
    # Default arg also omits it (back-compat with any caller passing only 2 args).
    default = _native_system_prompt(None, frozenset({"holding_object"}))
    assert default[0]["text"] == without[0]["text"]
    assert with_names[0]["text"] != without[0]["text"]


def test_system_prompt_teaches_compound_fetch_and_place() -> None:
    """A compound 'bring X AND place it' request must not end at the grasp.

    Frontier gap (combo probe '把红色的罐子拿过来放到架子上'): the native producer grasped,
    verified holding_object, and called finish — silently dropping the trailing place
    clause, because the sentence LEADS with a fetch word (拿过来) that the grasp guidance
    matches. The prompt now teaches the two-action compound: after the grasp verifies,
    call mobile_place + verify resting_on_receptacle BEFORE finishing.
    """
    from vector_os_nano.vcli.native_loop import _native_system_prompt

    text = _native_system_prompt(
        None,
        frozenset({"holding_object", "resting_on_receptacle"}),
        ("pickable_can_red",),
    )[0]["text"]
    assert "mobile_place" in text
    assert "resting_on_receptacle" in text
    # Must explicitly cover the fetch-LED compound (the exact combo failure mode).
    assert "放到" in text
    assert "never finish after only" in text.lower()
    # Omitted in a non-manipulation world (no graspable objects -> no place skill).
    dev = _native_system_prompt(None, frozenset({"holding_object"}), ())[0]["text"]
    assert "mobile_place" not in dev


def test_bring_is_complete_at_the_hold_no_auto_handover() -> None:
    """R196: a bare 拿过来 (bring over) must NOT trigger an auto-handover.

    E32: R194/R195 grounded the green ordinal grasp SUCCESSFULLY, but the brain
    (deepseek-v4-flash) then read '拿过来' as bring-to-user and routed `handover`,
    which RELEASES the weld -> the terminal holding_object verdict read False (the
    "grasp miss" symptom pointed away from the real cause). The grasp guidance now
    teaches that holding IS the delivery: finish at the hold, call handover ONLY on
    an explicit hand-over request (递给我/给我).
    """
    from vector_os_nano.vcli.native_loop import _native_system_prompt

    text = _native_system_prompt(
        None, frozenset({"holding_object"}), ("pickable_bottle_green",)
    )[0]["text"]
    # Teaches: a bare fetch is COMPLETE at the hold; do NOT auto-handover.
    assert "COMPLETE AT THE HOLD" in text
    assert "do NOT call" in text.lower() or "Do NOT call" in text
    assert "handover" in text
    # Reserves handover for an EXPLICIT hand-over request only.
    assert "递给我" in text and "给我" in text


def test_place_clause_is_not_a_navigation_goal() -> None:
    """R184: the compound PLACE leg must NOT be routed to navigate.

    R183 refuted `fetch-place.nl-compound` (RAN 1/4): after the grasp the model
    construed `放到架子上` as a nav destination, invented `at_position(10,5)`, and the
    unbounded navigate-RECOVER loop ('navigate AGAIN ... until at_position PASSES,
    NEVER finish while FAIL') burned all 24 turns without ever calling mobile_place
    -> walk-loop. Root cause: `locomotion_guidance` framed navigate as the way to
    'REACH a place or coordinate', colliding with the place clause. The prompt must
    (1) forbid navigate/walk for a place clause and (2) NOT offer navigate as the way
    to reach 'a place'.
    """
    from vector_os_nano.vcli.native_loop import _native_system_prompt

    text = _native_system_prompt(
        None,
        frozenset({"holding_object", "resting_on_receptacle", "at_position"}),
        ("pickable_can_red",),
        has_navigate=True,
    )[0]["text"]
    low = text.lower()
    # (1) place_guidance explicitly forbids navigate/walk for the place clause.
    assert "not a navigation" in low
    assert "do not use navigate" in low
    # (2) locomotion_guidance no longer offers navigate as the route to 'a place'
    #     (the exact colliding phrase that mis-routed the place clause).
    assert "reach a place or coordinate" not in low


def test_system_prompt_teaches_post_place_empty_gripper_is_not_a_drop() -> None:
    """R257/E60: a SUCCESSFUL place legitimately empties the gripper — that is the
    place's PURPOSE. The brain must NOT read holding_object==False after a place as an
    accidental drop ('掉了') and re-grasp the just-placed object off the receptacle
    (the R255/R256 courtyard PLACE flake: mobile_place placed OK -> brain '掉了。让我
    重新抓取它。' -> re-grasped -> undid the place). The prompt teaches: after
    mobile_place, an empty gripper is EXPECTED; verify resting_on_receptacle (NOT
    holding_object / describe); do NOT re-grasp; finish once it passes.
    """
    from vector_os_nano.vcli.native_loop import _native_system_prompt

    text = _native_system_prompt(
        None,
        frozenset({"holding_object", "resting_on_receptacle"}),
        ("pickable_bottle_green",),
    )[0]["text"]
    low = text.lower()
    # An empty gripper after a place is the EXPECTED terminal state, never a drop.
    assert "掉了" in text
    assert "empty gripper" in low
    assert "do not re-grasp" in low
    # The post-place check is resting_on_receptacle, and only THAT proves the place.
    assert "resting_on_receptacle" in text
    # Omitted in a non-manipulation world (no place skill -> no post-place guidance).
    dev = _native_system_prompt(None, frozenset({"holding_object"}), ())[0]["text"]
    assert "掉了" not in dev


def test_oracle_stays_strict_wrong_canonical_name_is_false() -> None:
    """STEP 7 moat guard: the fix did NOT loosen the oracle's exact match.

    While genuinely holding the banana, a WRONG canonical name (apple / mug) still
    returns False — verifying that the vocab-expose approach left ``make_holding_object``
    strictly canonical (case-insensitive EXACT on the scene name, no fuzzy/loose match).
    """
    from vector_os_nano.vcli.worlds.arm_sim_oracle import make_holding_object

    class _Arm:
        _connected = True

        def get_object_positions(self):
            # banana lifted at the EE; mug resting far away.
            return {"banana": [0.0, 0.0, 0.26], "mug": [0.5, 0.5, 0.0]}

        def get_joint_positions(self):
            return [0.0]

        def fk(self, _joints):
            return ([0.0, 0.0, 0.26], None)

    class _Gripper:
        def is_holding(self):
            return True

    agent = SimpleNamespace(_arm=_Arm(), _gripper=_Gripper())
    holding_object = make_holding_object(agent)
    assert holding_object("banana") is True  # the real, canonical match
    assert holding_object("apple") is False  # wrong name -> NOT loosened
    assert holding_object("mug") is False    # present but resting, not held
    assert holding_object("香蕉") is False    # localized name is NOT a canonical key


# ---------------------------------------------------------------------------
# D17 Prong-1 — a ROBOT world drops the MUTATING code tools (file_write/file_edit/
# bash) from the action surface so a physical robot goal cannot be "accomplished" by
# writing a marker file; read-only diagnostics (file_read/glob/grep) are KEPT. The
# DEV world (no robot agent) keeps the full code-tool set unchanged.
# ---------------------------------------------------------------------------


class _CodeTool:
    def __init__(self, name: str) -> None:
        self.name = name
        self.description = name
        self.input_schema = {"type": "object", "properties": {}}

    def execute(self, params, context):  # pragma: no cover - never dispatched here
        return None


class _CodeRegistry:
    def list_categories(self):
        return {"code": ["file_read", "file_write", "file_edit", "bash", "glob", "grep"]}

    def get(self, name):
        return _CodeTool(name)


def _engine_with_code_tools():
    return SimpleNamespace(_registry=_CodeRegistry(), _goal_executor=None)


def test_robot_world_drops_mutating_code_tools() -> None:
    from vector_os_nano.vcli.native_loop import _build_motor_tools

    robot_agent = SimpleNamespace(_base=None, _arm=None, _perception=None, _skill_registry=None)
    tools = _build_motor_tools(robot_agent, _engine_with_code_tools())
    # Prong-1: no file/shell WRITE is offered as an action in a robot world.
    assert "file_write" not in tools
    assert "file_edit" not in tools
    assert "bash" not in tools
    # Read-only diagnostics stay — the persona inspects code with them.
    assert "file_read" in tools
    assert "glob" in tools
    assert "grep" in tools


def test_dev_world_keeps_full_code_tool_set() -> None:
    from vector_os_nano.vcli.native_loop import _build_motor_tools

    tools = _build_motor_tools(None, _engine_with_code_tools())  # dev world: no agent
    for name in ("file_read", "file_write", "file_edit", "bash", "glob", "grep"):
        assert name in tools, f"dev world must keep {name}"


# ---------------------------------------------------------------------------
# Backlog #2 — the kernel threads a skill's result_data['diagnosis'] into the
# StepRecord so it surfaces on the StepVerdict. Without this, the native loop
# dropped every skill diagnosis (D103 diagnosis=null on the far failures).
# INFORMATIONAL only — the moat (verified) is delegated verbatim to the spine.
# ---------------------------------------------------------------------------


class _FakeGraspSkill:
    """A grasp double that 'succeeds' but emits a ran_no_weld diagnosis (RAN)."""

    name = "grasp"
    description = "Grasp the object in front of the robot (test double)."
    parameters = {"query": {"type": "string", "required": False}}
    preconditions = ["base"]
    effects: dict = {}

    def execute(self, params, context):
        from vector_os_nano.core.types import SkillResult

        return SkillResult(
            success=True,
            result_data={"diagnosis": "ran_no_weld", "weld_formed": False},
        )


def test_skill_diagnosis_threads_into_step_and_verdict() -> None:
    """A skill's result_data['diagnosis'] reaches StepRecord.result_data AND the
    StepVerdict.diagnosis — INFORMATIONAL only, ``verified`` stays the spine's call."""
    from vector_os_nano.vcli.cognitive.trace_store import evidence_passed

    backend = FakeToolScriptBackend.from_tool_script(
        [
            tool_turn(("grasp", {"query": "banana"})),
            # FALSE predicate -> the step is RAN (ran, did not ground).
            tool_turn(("verify", {"expr": "at_position(99.0, 99.0, 0.5)"})),
            tool_turn(("finish", {})),
        ]
    )
    agent, _base = _make_agent(0.0, 0.0)
    agent._skill_registry.register(_FakeGraspSkill())
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("grasp the banana then verify", session=_session())

    assert len(trace.steps) == 1
    step = trace.steps[0]
    # The kernel threaded the skill diagnosis onto the StepRecord.
    assert step.result_data.get("diagnosis") == "ran_no_weld"

    oracle_names = frozenset()
    report = VerdictReport.from_trace(trace, oracle_names)
    assert report.per_step[0].diagnosis == "ran_no_weld"
    # MOAT: verified is delegated VERBATIM to evidence_passed — diagnosis never feeds it.
    assert report.verified == bool(evidence_passed(trace, oracle_names))
    assert report.verified is False  # RAN, not grounded


# ---------------------------------------------------------------------------
# R257/E60 — deterministic post-place guard. After a SUCCESSFUL place the gripper is
# legitimately empty (the place's purpose); a brain that reads that as '掉了' and
# re-grasps the just-placed object UNDOES the place (R255/R256 courtyard flake). The
# runner refuses a re-grasp until ONE verify closes the place, forcing the brain to
# check resting_on_receptacle (passes -> finish) — brain-agnostic, planner-free, and
# quantity-safe (the intermediate FAIL verify clears the guard so the next grasp runs).
# ---------------------------------------------------------------------------


class _OkSkillTool:
    """A duck-typed motor tool whose execute always succeeds (no world needed)."""

    def __init__(self, name: str) -> None:
        self.name = name

    def execute(self, params, context):
        from vector_os_nano.vcli.tools.base import ToolResult

        return ToolResult(content=f"{self.name} ok")


def _post_place_runner():
    from vector_os_nano.vcli.native_loop import NativeStepRunner

    agent, _base = _make_agent(0.0, 0.0)
    motor = {"mobile_place": _OkSkillTool("mobile_place"),
             "perception_grasp": _OkSkillTool("perception_grasp")}
    verifier = SimpleNamespace(verify=lambda expr: True)
    ctx = SimpleNamespace()
    return NativeStepRunner(agent, verifier, frozenset({"resting_on_receptacle"}), motor, ctx)


def test_regrasp_after_place_is_refused_until_a_verify_closes_it() -> None:
    runner = _post_place_runner()
    # (1) place succeeds -> gripper legitimately empty.
    assert runner.dispatch_skill("mobile_place", {}).is_error is False
    # (2) an IMMEDIATE re-grasp (no verify between) is the '掉了' misread -> refused,
    #     with a nudge pointing at the real check.
    blocked = runner.dispatch_skill("perception_grasp", {"query": "green bottle"})
    assert blocked.is_error is True
    assert "resting_on_receptacle" in blocked.content
    # (3) once a verify closes the place, a subsequent grasp (quantity next-object) runs.
    runner.handle_verify("resting_on_receptacle() >= 2")
    assert runner.dispatch_skill("perception_grasp", {"query": "green bottle"}).is_error is False


def test_post_place_guard_is_bounded_never_wedges() -> None:
    """A model that stubbornly re-grasps without ever verifying still terminates: the
    guard is bounded (like the D23 verify nudge) so it can NEVER wedge the turn."""
    runner = _post_place_runner()
    runner.dispatch_skill("mobile_place", {})
    refusals = 0
    for _ in range(6):
        if runner.dispatch_skill("perception_grasp", {"query": "x"}).is_error:
            refusals += 1
        else:
            break
    # Refuses a bounded number of times, then lets the grasp through (no infinite block).
    assert 0 < refusals <= 2


# ---------------------------------------------------------------------------
# R274/E74 — degenerate-spin guard: a brain that keeps acting but NEVER verifies
# (the R272/R273 perception/nav thrash, 0 verdicts, ~15min) is broken to an honest
# fail EARLY, after one nudge to force a measurement. Distinct from finish-on-fail
# (which needs a FAILING verify to exist); here the model never verifies at all.
# ---------------------------------------------------------------------------


class _CallRecorder(FakeToolScriptBackend):
    """A tool-script backend that records the messages of every backend.call."""

    calls: list[list[dict]]

    @classmethod
    def make(cls, turns):  # type: ignore[no-untyped-def]
        b = cls.from_tool_script(turns)
        b.calls = []
        return b

    def call(self, **kw):  # type: ignore[override]
        self.calls.append(list(kw.get("messages") or []))
        return super().call(**kw)


def _spin(n: int):
    """n skill-only turns (walk, no verify) — the degenerate spin, plus a trailing end."""
    return [tool_turn(("walk", {"distance": 0.1, "speed": 0.3})) for _ in range(n)] + [
        tool_turn(end=True)
    ]


def test_degenerate_spin_without_verify_breaks_early_and_honestly() -> None:
    """20 action turns with NO verify -> the guard breaks BEFORE max_turns (and before
    the script ends), and the trace grades honestly (no steps, not verified)."""
    from vector_os_nano.vcli.native_loop import (
        _MAX_NATIVE_TURNS,
        _MAX_TURNS_WITHOUT_VERIFY,
    )

    backend = _CallRecorder.make(_spin(20))
    agent, _ = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("keep scanning forever", session=_session())

    # Broke early: fewer backend calls than the hard cap AND well under max_turns.
    assert len(backend.calls) <= _MAX_TURNS_WITHOUT_VERIFY
    assert len(backend.calls) < _MAX_NATIVE_TURNS
    # Honest: never verified -> zero graded steps -> fail closed.
    oracle_names = verify_oracle_names(agent, eng)
    report = VerdictReport.from_trace(trace, oracle_names)
    assert len(trace.steps) == 0
    assert report.verified is False


def test_degenerate_spin_nudges_once_to_verify_before_breaking() -> None:
    """At the soft threshold the runner injects ONE nudge telling the model to verify
    (so a thrashing run finally emits a verdict + fires the eyes-judge)."""
    from vector_os_nano.vcli.native_loop import _UNPRODUCTIVE_SPIN_NUDGE

    backend = _CallRecorder.make(_spin(20))
    agent, _ = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    eng.run_turn_native("keep scanning forever", session=_session())

    # The nudge (a user message) reaches the model on some later call.
    flat = "\n".join(str(m) for msgs in backend.calls for m in msgs)
    assert _UNPRODUCTIVE_SPIN_NUDGE in flat


def test_periodic_verify_never_trips_the_degenerate_guard() -> None:
    """A long run that verifies periodically with a DISTINCT measurement each time resets
    the counter, so the guard NEVER fires even across more turns than the hard cap -> no
    regression of a healthy, multi-step task (a NEW measurement is what proves progress,
    not the turn count). R279/E76: the reset is goal-aware — each burst closes on a NOVEL
    (predicate,result), not the SAME sub-check re-read (that is the thrash, tested below)."""
    from vector_os_nano.vcli.native_loop import _MAX_TURNS_WITHOUT_VERIFY

    walk = ("walk", {"distance": 0.1, "speed": 0.3})
    # THREE 4-walk bursts, each closed by a DISTINCT passing verify (novel expr -> real
    # progress; max unproductive run = 4 < 6). 12 total action-walks EXCEEDS the hard cap —
    # a bare spin of that length WOULD break; the periodic NEW measurement resets the
    # counter, so this healthy run must NOT be cut short.
    bursts = []
    for tol in (1000.0, 1001.0, 1002.0):
        verify = ("verify", {"expr": f"at_position(0.0, 0.0, {tol})"})
        bursts += [tool_turn(walk), tool_turn(walk), tool_turn(walk), tool_turn(walk),
                   tool_turn(verify)]
    script = bursts + [tool_turn(("finish", {}))]
    assert sum(1 for t in script if t.tool_calls and t.tool_calls[0].name == "walk") \
        >= _MAX_TURNS_WITHOUT_VERIFY
    backend = _CallRecorder.make(script)
    agent, _ = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("walk, verify, walk, verify, finish", session=_session())

    # Guard did NOT cut it short: all three verify pairs recorded, ran the whole script.
    assert len(trace.steps) == 3
    assert len(backend.calls) == len(script)


def test_repeated_identical_verify_does_not_dodge_the_spin_guard() -> None:
    """R279/E76 goal-aware reset: re-reading the SAME passing sub-check (the at_position-
    thrash where a flaky brain interleaves ONE off-goal verify to keep resetting the spin
    counter) is NOT progress -> only the FIRST occurrence of a given (predicate,result)
    resets; the repeats let the counter climb to the honest hard break. Without this a
    thrash dodges break@12 and falls back to the _MAX_NATIVE_TURNS cap (R278 frontier)."""
    from vector_os_nano.vcli.native_loop import (
        _MAX_NATIVE_TURNS,
        _MAX_TURNS_WITHOUT_VERIFY,
    )

    walk = ("walk", {"distance": 0.1, "speed": 0.3})
    # The SAME always-passing off-goal verify, re-read every burst. Under the OLD "any
    # verify resets" it would reset forever; under goal-aware reset only burst 1 counts.
    same_verify = ("verify", {"expr": "at_position(0.0, 0.0, 1000.0)"})
    burst = [tool_turn(walk), tool_turn(walk), tool_turn(walk), tool_turn(same_verify)]
    # Long enough that a novelty guard breaks (~turn 16) well before the script ends.
    script = burst * 6 + [tool_turn(("finish", {}))]
    backend = _CallRecorder.make(script)
    agent, _ = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    trace = eng.run_turn_native("re-read the same sub-check forever", session=_session())

    # Broke early on the thrash: fewer backend calls than the full script AND under the cap.
    assert len(backend.calls) < len(script)
    assert len(backend.calls) < _MAX_NATIVE_TURNS
    # Only the novel verifies were reached before the honest break (not all 6 repeats).
    assert len(trace.steps) < 6
    # The counter must have crossed the hard threshold -> at least that many turns ran.
    assert len(backend.calls) >= _MAX_TURNS_WITHOUT_VERIFY
