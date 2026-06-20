# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""STEP 12 regression — two adversarial-review moat false-greens flip to RAN through
the REAL ``cli.main`` on real go2 MuJoCo (the 2nd moat review, loop-until-dry).

Both holes graded a FALSE turn ``verified=True`` BEFORE the fix; this pins that the
real product now grades them RAN / exit 2 (the moat may only get STRICTER, rule 5):

(A) COMPARE-MEMBERSHIP SHORT-CIRCUIT (evidence_classifier): a real walk (CAUSED) +
    ``verify('True in (at_position(99,99), True)')`` — the constant member satisfies
    the membership while the oracle is dead weight, the ``... or True`` short-circuit
    hidden in an ``in`` node. The classifier now rejects a constant-literal container
    -> RAN even though the predicate EVALUATES True and the walk was CAUSED.

(B) FACING CROSS-CHANNEL CAUSATION (actor_causation): a forward walk (planar move,
    heading preserved) + ``verify('facing(0.0, 3.2)')`` (huge tol -> always true). The
    heading no-op used to grade CAUSED via the old ``max(planar, yaw)`` metric; the
    per-channel fix grades the FORWARD walk UNCAUSED for a facing predicate -> RAN.
    This ALSO empirically checks the yaw threshold against REAL forward-walk gait
    drift: if the straight walk drifted heading past ~10deg this would not flip.

SIM DISCIPLINE: serialized, headless, MuJoCo closed + rosm nuke + scene xml restored
after each case via the fixture.
"""
from __future__ import annotations

import subprocess

import pytest

pytest.importorskip("mujoco")

from tests.harness.pty_cli import run_cli_turn  # noqa: E402

_SIM_TIMEOUT_SEC = 360.0

# (A) real CAUSED walk + a membership short-circuit verify (predicate is dead weight).
_MEMBERSHIP_FALSE_GREEN = {
    "turns": [
        {"tool_calls": [{"name": "walk", "input": {"direction": "forward", "distance": 2.5, "speed": 0.3}}]},
        {"tool_calls": [{"name": "verify", "input": {"expr": "True in (at_position(99.0, 99.0), True)"}}]},
        {"tool_calls": [{"name": "finish", "input": {}}], "stop_reason": "end_turn"},
    ]
}

# (B) forward walk (no turn) + a facing predicate with huge tol (always true). The
# heading no-op must NOT grade CAUSED off the walk's planar displacement.
_FACING_FORWARD_WALK_FALSE_GREEN = {
    "turns": [
        {"tool_calls": [{"name": "walk", "input": {"direction": "forward", "distance": 2.5, "speed": 0.3}}]},
        {"tool_calls": [{"name": "verify", "input": {"expr": "facing(0.0, 3.2)"}}]},
        {"tool_calls": [{"name": "finish", "input": {}}], "stop_reason": "end_turn"},
    ]
}


def _nuke() -> None:
    try:
        subprocess.run(["rosm", "nuke", "--yes"], timeout=30, capture_output=True)
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture()
def sim_cleanup():
    yield
    _nuke()
    try:
        subprocess.run(
            ["git", "checkout",
             "vector_os_nano/hardware/sim/mjcf/go2/scene_room_piper.xml"],
            timeout=20, capture_output=True,
        )
    except Exception:  # noqa: BLE001
        pass


@pytest.mark.sim
@pytest.mark.cli_main
@pytest.mark.capability
def test_membership_shortcircuit_false_green_flips_to_ran(sim_cleanup) -> None:
    """(A) `True in (at_position(99,99), True)` after a real walk -> RAN / verified
    False / exit 2. The membership predicate EVALUATES True and the walk is CAUSED,
    so ONLY the structural classifier can stop it — and it must."""
    r = run_cli_turn(
        "走到坐标 (99.0,99.0)",
        sim_go2=True,
        timeout_sec=_SIM_TIMEOUT_SEC,
        extra_args=["--headless", "--native-loop"],
        tool_script=_MEMBERSHIP_FALSE_GREEN,
    )
    assert r.verified is False, f"membership short-circuit must NOT verify; got {r.verdict}"
    assert r.exit_code == 2, f"ran-not-verified must exit 2; got {r.exit_code}"
    assert r.evidence == "RAN", f"got evidence={r.evidence}"
    step = r.verdict["per_step"][0]
    assert step["evidence"] == "RAN"
    # The predicate genuinely evaluates True (the dead-weight constant) — the classifier
    # rejected the STRUCTURE, not the truth value.
    assert step["verify_result"] is True


@pytest.mark.sim
@pytest.mark.cli_main
@pytest.mark.capability
def test_facing_forward_walk_false_green_flips_to_ran(sim_cleanup) -> None:
    """(B) a forward walk + `facing(0.0, 3.2)` (always-true heading predicate) -> RAN
    / verified False / exit 2. The walk moved planar, not heading, so a facing
    predicate must grade UNCAUSED — proving the per-channel causation fix holds on the
    real gait (incl. any forward-walk yaw drift below the ~10deg threshold)."""
    r = run_cli_turn(
        "保持当前朝向",
        sim_go2=True,
        timeout_sec=_SIM_TIMEOUT_SEC,
        extra_args=["--headless", "--native-loop"],
        tool_script=_FACING_FORWARD_WALK_FALSE_GREEN,
    )
    assert r.verified is False, f"forward-walk facing no-op must NOT verify; got {r.verdict}"
    assert r.exit_code == 2, f"ran-not-verified must exit 2; got {r.exit_code}"
    assert r.evidence == "RAN", f"got evidence={r.evidence}"
    step = r.verdict["per_step"][0]
    assert step["evidence"] == "RAN"
    # The facing predicate is true (huge tol) — only actor-causation stops it.
    assert step["verify_result"] is True


# (C) STEP-13 goal-authenticity: a real CAUSED walk to the WRONG place that verifies its
# OWN landing must NOT verify — only the verify-constant-vs-parsed-goal gate stops it.
_WRONG_PLACE_FALSE_GREEN = {
    "turns": [
        {"tool_calls": [{"name": "walk", "input": {"direction": "forward", "distance": 0.4, "speed": 0.3}}]},
        {"tool_calls": [{"name": "verify", "input": {"expr": "at_position(10.0, 3.0)"}}]},
        {"tool_calls": [{"name": "finish", "input": {}}], "stop_reason": "end_turn"},
    ]
}


@pytest.mark.sim
@pytest.mark.cli_main
@pytest.mark.capability
def test_wrong_place_self_verified_landing_flips_to_ran(sim_cleanup) -> None:
    """(C, STEP-13 goal-authenticity) a REAL actor-caused walk that lands near (10,3) —
    NOT the commanded goal (11,3) — and verifies at_position(10,3) (its OWN landing) ->
    RAN / verified False / exit 2. The walk is CAUSED and the predicate is TRUE at the
    landing, so R1+R2b both pass; ONLY the goal-authenticity gate (verify constant !=
    the user's parsed coordinate goal) can reject it."""
    r = run_cli_turn(
        "走到坐标 (11.0,3.0)",
        sim_go2=True,
        timeout_sec=_SIM_TIMEOUT_SEC,
        extra_args=["--headless", "--native-loop"],
        tool_script=_WRONG_PLACE_FALSE_GREEN,
    )
    assert r.verified is False, f"verifying your own wrong landing must NOT verify; got {r.verdict}"
    assert r.exit_code == 2, f"got {r.exit_code}"
    assert r.evidence == "RAN", f"got evidence={r.evidence}"
    step = r.verdict["per_step"][0]
    assert step["evidence"] == "RAN"
    # The predicate is TRUE at the landing and the walk is a real CAUSED walk — only the
    # goal-authenticity gate (constant (10,3) != goal (11,3)) downgrades it.
    assert step["verify_result"] is True
    assert step["strategy"] == "walk"
