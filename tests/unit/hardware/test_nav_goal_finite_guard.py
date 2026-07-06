# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""E190 regression: the navigation-GOAL boundary must reject non-finite input.

``navigate_to(x, y)`` / ``publish_goal(x, y)`` is the pose-target command boundary
for every mobile base — reachable from NL/CaP-X (``vcli/primitives/navigation.py``
``publish_goal`` → ``nav_client``/``base.navigate_to``) and from the ``navigate``
tool call (``native_loop`` does ``float(params["x"])``; ``json.loads`` accepts the
``NaN``/``Infinity`` tokens, so ``{"x": NaN}`` parses to ``float('nan')``). Before
this gate the goal escaped the process onto an external ROS2 topic UNCHECKED:

  * ``Go2ROS2Proxy.navigate_to`` did ``self._nav_goal = (float(x), float(y))`` then
    ``_publish_goal_point`` published ``msg.point.x = float(x)`` onto ``/goal_point``
    (the FAR planner routing input) — a NaN/inf goal poisoned the external planner.
  * ``NavStackClient._cmu_navigate`` published ``msg.point.x = float(x)`` onto the
    waypoint topic; ``_nav2_navigate`` set ``goal.pose.pose.position.x = float(x)``
    on a NAV2 action goal — both unchecked.

Unlike the velocity boundary (E189), the goal is handed to an EXTERNAL nav stack,
so a poisoned goal is invisible to the honest-verify spine while the robot may be
commanded toward it — a fail-open. The mujoco vgraph drivers are protected
downstream (plan_path → unreachable, or the E189 set_velocity gate catches NaN
waypoints), but they are gated too for defense-in-depth and mirror-safety. The
global security floor (rules/common/security.md) mandates rejecting NaN/inf before
acting. Same class as E187 (loader) / E188 (arm move_joints) / E189 (base velocity),
now the pose-TARGET boundary.

Sim-free by design: the pure validator is tested directly (the sim slot is a single
global resource). A source-level wiring guard proves every concrete ``navigate_to``
and ``publish_goal`` calls it, so the guard cannot silently regress out of a sink.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from zeno.hardware.base import ensure_finite_nav_goal

_PKG = Path(__file__).resolve().parents[3] / "zeno"


class TestEnsureFiniteNavGoal:
    def test_accepts_finite(self) -> None:
        # Legitimate world-frame goals incl. negatives and zero (metres).
        ensure_finite_nav_goal(0.0, 0.0)
        ensure_finite_nav_goal(-2.5, 11.0)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_nonfinite_x(self, bad: float) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            ensure_finite_nav_goal(bad, 0.0)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_rejects_nonfinite_y(self, bad: float) -> None:
        with pytest.raises(ValueError, match="non-finite"):
            ensure_finite_nav_goal(0.0, bad)

    def test_error_names_the_bad_axis(self) -> None:
        with pytest.raises(ValueError, match=r"\by\b"):
            ensure_finite_nav_goal(1.0, float("nan"))

    def test_context_label_in_message(self) -> None:
        with pytest.raises(ValueError, match="Go2ROS2Proxy.navigate_to"):
            ensure_finite_nav_goal(float("inf"), 0.0, ctx="Go2ROS2Proxy.navigate_to")


def _navigate_to_impls() -> list[Path]:
    """Every module that defines a real ``navigate_to`` body (non-Protocol)."""
    out: list[Path] = []
    for p in _PKG.rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        if "def navigate_to(" not in src:
            continue
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "navigate_to":
                body = [n for n in node.body if not isinstance(n, ast.Expr)]
                if body:  # skip the pure Protocol stub (docstring + ellipsis)
                    out.append(p)
                    break
    return out


class TestEveryGoalSinkGuards:
    def test_impls_discovered(self) -> None:
        impls = _navigate_to_impls()
        assert len(impls) >= 3, f"expected multiple navigate_to sinks, found {impls}"

    @pytest.mark.parametrize("path", _navigate_to_impls(), ids=lambda p: p.name)
    def test_navigate_to_calls_finite_guard(self, path: Path) -> None:
        src = path.read_text(encoding="utf-8")
        assert "ensure_finite_nav_goal(" in src, (
            f"{path.name}: navigate_to does not call ensure_finite_nav_goal — "
            "a non-finite nav goal would be published to the external nav stack "
            "silently (E190)"
        )

    def test_publish_goal_primitive_guards(self) -> None:
        prim = _PKG / "vcli" / "primitives" / "navigation.py"
        src = prim.read_text(encoding="utf-8")
        assert "ensure_finite_nav_goal(" in src, (
            "publish_goal (the CaP-X navigation primitive) does not call "
            "ensure_finite_nav_goal — the NL goal boundary is fail-open (E190)"
        )


class TestPublishGoalRejectsBeforeDispatch:
    """Behavioral: the NL/CaP-X boundary must fail loud BEFORE the goal reaches
    any client — proving the guard is not merely present but actually gates."""

    def test_nan_goal_never_reaches_nav_client(self) -> None:
        from zeno.vcli.primitives import PrimitiveContext, navigation

        class _TripwireClient:
            def navigate_to(self, x: float, y: float) -> bool:  # pragma: no cover
                raise AssertionError(
                    "publish_goal dispatched a non-finite goal to nav_client"
                )

        prev = navigation._ctx
        navigation._ctx = PrimitiveContext(nav_client=_TripwireClient())
        try:
            with pytest.raises(ValueError, match="non-finite"):
                navigation.publish_goal(float("nan"), 0.0)
            with pytest.raises(ValueError, match="non-finite"):
                navigation.publish_goal(0.0, float("inf"))
        finally:
            navigation._ctx = prev
