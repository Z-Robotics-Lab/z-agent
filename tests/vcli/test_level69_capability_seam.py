# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Level 69 — Phase C.1: the routable-capability seam (dev-only proof).

Acceptance criteria (docs/agent-kernel-phase-c-plan.md, C-1):
- a capability sub-goal routes through GoalExecutor._execute_capability and is
  gated by its deterministic verify predicate;
- THE INVARIANT: a capability whose invoke() returns success=True but whose
  verify predicate is False produces StepRecord.success=False (the capability
  cannot self-certify around the verifier);
- an unregistered / no-registry / side-effecting capability fails closed;
- engine wires the dev chat capability (+ KNOWN_STRATEGIES); the robot world
  registers none (path byte-identical).

Pure kernel logic — no robot, no network, no mujoco fixtures.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from zeno.vcli.cognitive.capabilities import (
    CapabilityRegistry,
    CapabilityResult,
    LLMChatCapability,
    validate_input,
)
from zeno.vcli.cognitive.goal_executor import GoalExecutor
from zeno.vcli.cognitive.strategy_selector import StrategyResult, StrategySelector
from zeno.vcli.cognitive.types import GoalTree, SubGoal


class _Cap:
    """Minimal fake capability."""

    def __init__(self, name: str, *, side: bool = False, ok: bool = True,
                 required: list[str] | None = None) -> None:
        self.name = name
        self.kind = "test"
        self.side_effecting = side
        self.input_schema: dict[str, Any] = {"required": required or []}
        self.output_schema: dict[str, Any] = {}
        self.invoked = False
        self._ok = ok

    def estimate(self, payload: dict) -> tuple[float, float]:
        return (0.0, 0.0)

    def invoke(self, payload: dict, context: Any) -> CapabilityResult:
        self.invoked = True
        return CapabilityResult(success=self._ok, output={"echo": payload},
                                error="" if self._ok else "cap failed")


def _result(executor_type: str, name: str, params: dict) -> Any:
    m = MagicMock()
    m.executor_type = executor_type
    m.name = name
    m.params = params
    return m


# ---------------------------------------------------------------------------
# Registry + selector routing
# ---------------------------------------------------------------------------


def test_registry_basics() -> None:
    reg = CapabilityRegistry()
    cap = _Cap("detect")
    reg.register(cap)
    assert reg.get("detect") is cap
    assert "detect" in reg
    assert reg.names() == frozenset({"detect"})
    assert reg.get("missing") is None
    assert len(reg) == 1


def test_validate_input_required_keys() -> None:
    assert validate_input({"required": ["image"]}, {"image": 1}) is None
    assert "missing" in validate_input({"required": ["image"]}, {})
    assert "dict" in validate_input({}, "not a dict")  # type: ignore[arg-type]


def test_selector_routes_registered_capability() -> None:
    sel = StrategySelector(capability_names={"chat", "detect"})
    sg = SubGoal(name="ask", description="d", verify="True", strategy="chat",
                 strategy_params={"prompt": "hi"})
    r = sel.select(sg)
    assert isinstance(r, StrategyResult)
    assert (r.executor_type, r.name) == ("capability", "chat")
    assert r.params == {"prompt": "hi"}


def test_selector_unregistered_name_is_not_capability() -> None:
    sel = StrategySelector(capability_names={"chat"})
    # An unregistered explicit strategy falls through to the skill convention.
    assert sel._resolve_explicit("detect", {}).executor_type == "skill"


# ---------------------------------------------------------------------------
# Executor dispatch
# ---------------------------------------------------------------------------


def test_executor_invokes_readonly_capability() -> None:
    reg = CapabilityRegistry()
    cap = _Cap("echo")
    reg.register(cap)
    ex = GoalExecutor(strategy_selector=None, verifier=None, capability_registry=reg)
    ok, err, _ = ex._execute_strategy(_result("capability", "echo", {"x": 1}))
    assert ok is True and err == ""
    assert cap.invoked is True


def test_executor_side_effecting_fails_closed() -> None:
    reg = CapabilityRegistry()
    reg.register(_Cap("vla", side=True))
    ex = GoalExecutor(strategy_selector=None, verifier=None, capability_registry=reg)
    ok, err, _ = ex._execute_strategy(_result("capability", "vla", {}))
    assert ok is False
    assert "permission gate" in err


def test_executor_unknown_capability_fails_closed() -> None:
    ex = GoalExecutor(strategy_selector=None, verifier=None,
                      capability_registry=CapabilityRegistry())
    ok, err, _ = ex._execute_strategy(_result("capability", "ghost", {}))
    assert ok is False and "unknown capability" in err


def test_executor_no_registry_fails_closed() -> None:
    ex = GoalExecutor(strategy_selector=None, verifier=None)  # default None
    ok, err, _ = ex._execute_strategy(_result("capability", "echo", {}))
    assert ok is False and "none configured" in err


def test_executor_invalid_input_fails() -> None:
    reg = CapabilityRegistry()
    reg.register(_Cap("detect", required=["image"]))
    ex = GoalExecutor(strategy_selector=None, verifier=None, capability_registry=reg)
    ok, err, _ = ex._execute_strategy(_result("capability", "detect", {}))  # no image
    assert ok is False and "invalid" in err


# ---------------------------------------------------------------------------
# THE INVARIANT: a capability cannot self-certify around the verifier
# ---------------------------------------------------------------------------


def _exec_one(verify_ok: bool, cap_ok: bool = True):
    reg = CapabilityRegistry()
    reg.register(_Cap("echo", ok=cap_ok))
    selector = StrategySelector(capability_names={"echo"})
    verifier = MagicMock()
    verifier.verify.return_value = verify_ok
    ex = GoalExecutor(strategy_selector=selector, verifier=verifier, capability_registry=reg)
    sg = SubGoal(name="echo_it", description="d", verify="file_exists('x')",
                 strategy="echo", strategy_params={"prompt": "hi"})
    return ex.execute(GoalTree("g", (sg,)))


def test_invoke_success_but_verify_false_is_step_failure() -> None:
    trace = _exec_one(verify_ok=False)  # capability ran, predicate fails
    assert trace.success is False
    assert trace.steps[0].verify_result is False


def test_invoke_success_and_verify_true_is_step_success() -> None:
    trace = _exec_one(verify_ok=True)
    assert trace.success is True
    assert trace.steps[0].strategy == "echo"


def test_invoke_failure_short_circuits_before_verify() -> None:
    trace = _exec_one(verify_ok=True, cap_ok=False)  # invoke fails -> no verify
    assert trace.success is False


# ---------------------------------------------------------------------------
# LLMChatCapability adapter
# ---------------------------------------------------------------------------


def test_chat_capability_wraps_backend() -> None:
    backend = MagicMock()
    backend.call.return_value = MagicMock(text="a summary")
    res = LLMChatCapability(backend).invoke({"prompt": "summarize"}, None)
    assert res.success is True
    assert res.output["text"] == "a summary"
    backend.call.assert_called_once()


def test_chat_capability_backend_error_is_failure() -> None:
    backend = MagicMock()
    backend.call.side_effect = RuntimeError("429 rate limit")
    res = LLMChatCapability(backend).invoke({"prompt": "x"}, None)
    assert res.success is False
    assert "rate limit" in res.error


# ---------------------------------------------------------------------------
# Engine wiring
# ---------------------------------------------------------------------------


def test_engine_wires_chat_capability_for_dev() -> None:
    from zeno.vcli.engine import VectorEngine
    from zeno.vcli.worlds import DevWorld

    eng = VectorEngine(backend=MagicMock(), intent_router=MagicMock())
    eng.init_vgg(agent=None, skill_registry=None, world=DevWorld())
    assert eng._vgg_enabled is True
    reg = eng._goal_executor._capability_registry
    assert reg is not None and "chat" in reg.names()
    assert "chat" in eng._goal_decomposer.KNOWN_STRATEGIES


def test_engine_robot_world_registers_no_capabilities() -> None:
    from zeno.vcli.engine import VectorEngine
    from zeno.vcli.worlds import RobotWorld

    eng = VectorEngine(backend=MagicMock(), intent_router=MagicMock())
    eng.init_vgg(agent=None, skill_registry=None, world=RobotWorld())
    reg = getattr(eng._goal_executor, "_capability_registry", None)
    assert reg is None or len(reg) == 0
