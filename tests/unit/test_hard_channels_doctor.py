# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Unit: the LANDING-CONFORMANCE doctor for the hard-channel quartet (R324/E115).

R323/E114 packaged the four proven cores (pose_upright/height/near/facing) as agent-bound
verify-namespace predicates in tools/acceptance/hard_channels.py, red-teamed to land on the
EXISTING base API with NO interface change (the whole point: G-323-1 is ONE low-risk merge).
But test_hard_channels.py exercises that packaging against a FAKE base — so it stays green even
if the REAL hardware/base.py dropped get_odometry, or core/types.Odometry lost its quaternion,
or a name already taken in the consumer seam silently shadowed a channel. Then the "no interface
change" claim would rot UNNOTICED until the owner tried to land it.

This doctor closes that gap without touching the spine: it dry-runs make_verify_namespace against
a fake agent AND asserts, against the REAL kernel modules (read-only), the four landing
preconditions the R323 red-team established — turning a prose FINDING into a standing guard the
gate round runs before merging. It grades the LANDING, not a fifth geometry (the offline oracle
well is dry — a fifth core would be treadmill).
"""
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "hard_channels_doctor",
    Path(__file__).resolve().parents[2]
    / "tools"
    / "acceptance"
    / "hard_channels_doctor.py",
)
doctor = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(doctor)

_NAMES = {"upright", "nominal_height", "near", "facing_target"}


def _report():
    return doctor.diagnose()


def _check(report, name):
    hits = [c for c in report["checks"] if c["name"] == name]
    assert hits, f"no check named {name!r} in {[c['name'] for c in report['checks']]}"
    return hits[0]


class TestReportShape:
    def test_report_has_ok_and_checks(self):
        r = _report()
        assert isinstance(r["ok"], bool)
        assert isinstance(r["checks"], list) and r["checks"]
        for c in r["checks"]:
            assert isinstance(c["name"], str) and c["name"]
            assert isinstance(c["ok"], bool)
            assert isinstance(c["detail"], str) and c["detail"]

    def test_ok_is_and_of_every_check(self):
        r = _report()
        assert r["ok"] == all(c["ok"] for c in r["checks"])

    def test_the_four_expected_checks_are_present(self):
        r = _report()
        names = {c["name"] for c in r["checks"]}
        assert {
            "packaged_shape",
            "base_api_surface",
            "reference_seam_shape",
            "landing_delta",
        } <= names


class TestGreenOnCurrentTree:
    """On today's tree every landing precondition holds, so the doctor is GREEN."""

    def test_overall_ok(self):
        assert _report()["ok"] is True

    def test_every_check_ok(self):
        for c in _report()["checks"]:
            assert c["ok"] is True, f"{c['name']}: {c['detail']}"


class TestPackagedShape:
    def test_names_and_signature_parity(self):
        c = _check(_report(), "packaged_shape")
        # detail names the exact predicate set the packaging exposes
        assert all(n in c["detail"] for n in _NAMES)


class TestBaseApiSurface:
    """The landing precondition: the real base ABC + Odometry expose what the four read."""

    def test_detail_names_the_three_accessors_and_the_quat(self):
        c = _check(_report(), "base_api_surface")
        for token in ("get_position", "get_heading", "get_odometry", "qw"):
            assert token in c["detail"], c["detail"]


class TestLandingDelta:
    def test_quartet_not_yet_in_predicate_oracles(self):
        # Landing is genuinely additive right now (nothing pre-landed / shadowed);
        # the doctor reports it so the gate round knows the delta is still open.
        c = _check(_report(), "landing_delta")
        assert c["ok"] is True


class TestFailureDetection:
    """The guard must go RED when a precondition is actually broken — not silently pass."""

    def test_missing_base_accessor_fails(self):
        c = doctor.check_base_api_surface(
            base_methods={"get_position", "get_heading"},  # get_odometry dropped
            odom_fields={"qw", "qx", "qy", "qz"},
        )
        assert c["ok"] is False
        assert "get_odometry" in c["detail"]

    def test_missing_quat_field_fails(self):
        c = doctor.check_base_api_surface(
            base_methods={"get_position", "get_heading", "get_odometry"},
            odom_fields={"qx", "qy", "qz"},  # qw dropped
        )
        assert c["ok"] is False
        assert "qw" in c["detail"]

    def test_name_collision_shadow_fails(self):
        # A quartet name already taken by an existing consumer-seam predicate
        # would SHADOW on landing — the doctor must flag it.
        c = doctor.check_landing_delta(
            predicate_oracles=frozenset({"at_position", "facing", "near"}),
            existing_ns_keys={"at_position", "facing"},
        )
        assert c["ok"] is False
        assert "near" in c["detail"]

    def test_clean_delta_passes(self):
        c = doctor.check_landing_delta(
            predicate_oracles=frozenset({"at_position", "facing"}),
            existing_ns_keys={"at_position", "facing"},
        )
        assert c["ok"] is True
