# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit: the agent-bound verify-namespace form of the hard-channel family (R323/E114).

R318-R322 proved four deterministic hard channels as pure-math cores in tools/acceptance/
(pose_upright E109, pose_height E110, place_near E112, heading_facing E113). Each grades a
geometric fact off GROUND TRUTH the actor cannot author (Invariant 1). But a core takes raw
numbers; a verify predicate a sub-goal's ``verify`` expression can call must READ that ground
truth off the connected base itself and return a bool. This module packages three of the four
cores into exactly that GT-reading, bool-returning, fail-safe-to-False shape — byte-for-byte
the ``go2_sim_oracle.make_*`` contract — so landing them into RobotWorld.build_verify_namespace
is ONE conformant merge (a single CEO gate), not three prose gates.

Landing (mined + red-teamed R323): ALL FOUR channels land on the EXISTING base API
(hardware/base.py get_position/get_heading/get_odometry) with no interface change — upright
(root quaternion off get_odometry), nominal_height (root z), near (own pos vs a resolved target),
facing_target (own pos+yaw vs a resolved target). The quaternion for upright rides get_odometry()
-> Odometry(qw,qx,qy,qz), so no new accessor is needed. Identity ("which object is the target")
stays the VLM/D182 grounder's job; these grade geometry only.

Tested with a FAKE base (stub get_position/get_heading/get_odometry) — no sim, no network. Proves
the landing shape conforms to the real seam BEFORE the gate, so the owner reviews one small diff.
"""
import importlib.util
import math
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "hard_channels",
    Path(__file__).resolve().parents[2] / "tools" / "acceptance" / "hard_channels.py",
)
hard_channels = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(hard_channels)


class FakeOdom:
    def __init__(self, quat):
        self.qw, self.qx, self.qy, self.qz = (float(c) for c in quat)


class FakeBase:
    """Minimal stand-in for a connected base: the GT reads the four channels use."""

    def __init__(self, pos, heading=0.0, quat=(1.0, 0.0, 0.0, 0.0), connected=True):
        self._pos = list(pos)
        self._heading = float(heading)
        self._quat = tuple(quat)
        self._connected = connected

    def get_position(self):
        return list(self._pos)

    def get_heading(self):
        return self._heading

    def get_odometry(self):
        return FakeOdom(self._quat)


class FakeAgent:
    def __init__(self, base):
        self._base = base


def _ns(base):
    return hard_channels.make_verify_namespace(FakeAgent(base))


_NAMES = {"upright", "nominal_height", "near", "facing_target"}


class TestNamespaceShape:
    def test_exactly_the_four_landing_predicates(self):
        ns = _ns(FakeBase([0, 0, 0.35]))
        assert set(ns) == _NAMES
        assert all(callable(fn) for fn in ns.values())

    def test_signatures_cover_every_predicate(self):
        sigs = hard_channels.verify_signatures()
        assert set(sigs) == _NAMES
        for name, sig in sigs.items():
            assert name in sig and sig.strip() and "(" in sig


class TestUpright:
    def test_identity_quat_is_standing(self):
        assert _ns(FakeBase([0, 0, 0.35], quat=(1.0, 0.0, 0.0, 0.0)))["upright"]() is True

    def test_ninety_deg_pitch_topple_is_fallen(self):
        c = math.cos(math.pi / 4)  # +90deg about body-x: body-z now horizontal
        assert _ns(FakeBase([0, 0, 0.35], quat=(c, c, 0.0, 0.0)))["upright"]() is False

    def test_threshold_is_caller_owned(self):
        # ~53deg tilt: upright cosine ~0.6 — FALLEN under a strict 0.8, STANDING under a loose 0.3.
        half = math.radians(53) / 2
        q = (math.cos(half), math.sin(half), 0.0, 0.0)
        assert _ns(FakeBase([0, 0, 0.35], quat=q))["upright"](thresh=0.8) is False
        assert _ns(FakeBase([0, 0, 0.35], quat=q))["upright"](thresh=0.3) is True


class TestNominalHeight:
    def test_stance_height_is_nominal(self):
        assert _ns(FakeBase([0, 0, 0.35]))["nominal_height"]() is True

    def test_sunk_through_floor_is_not_nominal(self):
        assert _ns(FakeBase([0, 0, 0.05]))["nominal_height"]() is False

    def test_airborne_is_not_nominal(self):
        assert _ns(FakeBase([0, 0, 1.2]))["nominal_height"]() is False

    def test_tolerance_is_caller_owned(self):
        # z=0.5 is outside the default 0.12 band but inside a loose 0.2 band.
        assert _ns(FakeBase([0, 0, 0.5]))["nominal_height"]() is False
        assert _ns(FakeBase([0, 0, 0.5]))["nominal_height"](tol=0.2) is True


class TestNear:
    def test_close_target_is_near(self):
        assert _ns(FakeBase([0, 0, 0.35]))["near"](0.3, 0.0) is True

    def test_far_target_is_far(self):
        assert _ns(FakeBase([0, 0, 0.35]))["near"](5.0, 0.0) is False

    def test_planar_vs_full_xyz(self):
        # Target stacked 2 m directly overhead: NEAR in the xy plane, FAR in full xyz.
        base = FakeBase([0, 0, 0.35])
        assert _ns(base)["near"](0.0, 0.0) is True  # planar default
        assert _ns(base)["near"](0.0, 0.0, 2.35, planar=False) is False

    def test_radius_is_caller_owned(self):
        assert _ns(FakeBase([0, 0, 0.35]))["near"](0.8, 0.0) is False
        assert _ns(FakeBase([0, 0, 0.35]))["near"](0.8, 0.0, radius=1.0) is True


class TestFacingTarget:
    def test_target_ahead_is_facing(self):
        assert _ns(FakeBase([0, 0, 0.35], heading=0.0))["facing_target"](1.0, 0.0) is True

    def test_target_behind_is_away(self):
        # The case a single-frame VLM cannot read: target directly behind the robot.
        assert _ns(FakeBase([0, 0, 0.35], heading=0.0))["facing_target"](-1.0, 0.0) is False

    def test_turned_toward_a_behind_target_is_facing(self):
        import math

        base = FakeBase([0, 0, 0.35], heading=math.pi)  # turned around
        assert _ns(base)["facing_target"](-1.0, 0.0) is True

    def test_distance_orthogonal(self):
        # Facing depends only on orientation, not distance: same verdict near and far.
        base = FakeBase([0, 0, 0.35], heading=0.0)
        assert _ns(base)["facing_target"](0.2, 0.0) is True
        assert _ns(base)["facing_target"](50.0, 0.0) is True

    def test_cone_is_caller_owned(self):
        # 30deg off: outside a tight 15deg cone, inside a loose 45deg cone.
        import math

        base = FakeBase([0, 0, 0.35], heading=0.0)
        tx, ty = math.cos(math.radians(30)), math.sin(math.radians(30))
        assert _ns(base)["facing_target"](tx, ty, tol_deg=15) is False
        assert _ns(base)["facing_target"](tx, ty, tol_deg=45) is True


class TestFailSafe:
    """Unreadable ground truth must fail to False — never a false PASS (the moat)."""

    def test_no_base_is_false(self):
        ns = hard_channels.make_verify_namespace(FakeAgent(None))
        assert ns["upright"]() is False
        assert ns["nominal_height"]() is False
        assert ns["near"](0.0, 0.0) is False
        assert ns["facing_target"](1.0, 0.0) is False

    def test_disconnected_base_is_false(self):
        ns = _ns(FakeBase([0, 0, 0.35], connected=False))
        assert ns["upright"]() is False
        assert ns["nominal_height"]() is False
        assert ns["near"](0.0, 0.0) is False
        assert ns["facing_target"](1.0, 0.0) is False

    def test_bad_args_are_false_not_raising(self):
        ns = _ns(FakeBase([0, 0, 0.35]))
        assert ns["near"]("nan-ish", 0.0) is False
        assert ns["facing_target"](None, 0.0) is False
        assert ns["nominal_height"](tol="oops") is False

    def test_none_agent_is_false(self):
        ns = hard_channels.make_verify_namespace(None)
        assert ns["nominal_height"]() is False


class TestDispatcher:
    def test_routes_upright(self):
        assert hard_channels._main(["upright", "1", "0", "0", "0"]) == 0

    def test_routes_height(self):
        assert hard_channels._main(["height", "0.35"]) == 0

    def test_routes_near(self):
        assert hard_channels._main(["near", "0", "0", "--to", "0.3", "0"]) == 0

    def test_routes_facing(self):
        assert hard_channels._main(["facing", "--at", "0", "0", "--to", "1", "0", "--yaw", "0"]) == 0

    def test_unknown_channel_is_error(self):
        assert hard_channels._main(["bogus"]) == 2
