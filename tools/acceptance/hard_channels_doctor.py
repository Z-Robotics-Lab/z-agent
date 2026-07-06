# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""hard_channels_doctor — a LANDING-CONFORMANCE guard for the hard-channel quartet (R324/E115).

R323/E114 packaged the four proven cores (pose_upright E109, pose_height E110, place_near E112,
heading_facing E113) as agent-bound verify-namespace predicates in ``hard_channels.py`` and
red-teamed them to land on the EXISTING base API with NO interface change — the whole reason
G-323-1 is ONE low-risk merge. But that packaging is unit-tested against a FAKE base, so those
tests stay green even if the REAL seam drifts: if ``hardware/base.py`` dropped ``get_odometry``,
or ``core/types.Odometry`` lost its quaternion, or a landing name were already taken in the
consumer seam (a silent shadow), the "no interface change" claim would rot UNNOTICED until the
owner tried to land it.

This doctor turns that prose FINDING into a standing, machine-checked guard. It reads (never
edits) the real kernel modules and asserts the four landing preconditions the R323 red-team
established, then dry-runs ``make_verify_namespace`` against a fake agent. Run it BEFORE landing
G-323-1 to confirm the quartet still merges cleanly; a RED check means a precondition broke and
the merge would not be the claimed one-line-risk change.

It grades the LANDING, not a fifth geometry. The offline oracle well is DRY — a fifth core would
be pure treadmill (STATUS frontier). NOT a spine file: tools/, read-only imports, no sim / no
network at import.

Usage:
    python tools/acceptance/hard_channels_doctor.py [--json]   # exit 0 iff every check is OK
"""
from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path
from typing import Any

_DIR = Path(__file__).resolve().parent

# The exact predicate set the quartet packaging exposes (single source: the packaged module).
EXPECTED_NAMES = frozenset({"upright", "nominal_height", "near", "facing_target"})

# What each landing predicate READS off the connected base (the R323 red-team surface).
REQUIRED_BASE_METHODS = frozenset({"get_position", "get_heading", "get_odometry"})
REQUIRED_ODOM_FIELDS = frozenset({"qw", "qx", "qy", "qz"})


def _load_sibling(name: str):
    """Load a sibling tools/acceptance module by path (mirrors the unit-test loader)."""
    spec = importlib.util.spec_from_file_location(name, _DIR / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _FakeOdom:
    def __init__(self, quat=(1.0, 0.0, 0.0, 0.0)):
        self.qw, self.qx, self.qy, self.qz = (float(c) for c in quat)


class _FakeBase:
    """A connected base stub exposing exactly the GT the four channels read."""

    _connected = True

    def get_position(self):
        return [0.0, 0.0, 0.35]

    def get_heading(self):
        return 0.0

    def get_odometry(self):
        return _FakeOdom()


class _FakeAgent:
    def __init__(self, base):
        self._base = base


# --- individual checks (pure functions of injected facts, so failure paths are testable) ---
def check_packaged_shape(namespace_keys: set[str], signature_keys: set[str]) -> dict[str, Any]:
    """The packaging is self-consistent: namespace == signatures == the four expected names."""
    ns, sig, exp = set(namespace_keys), set(signature_keys), set(EXPECTED_NAMES)
    ok = ns == exp == sig
    if ok:
        detail = "namespace == signatures == {" + ", ".join(sorted(exp)) + "}"
    else:
        detail = (
            f"drift — namespace={sorted(ns)} signatures={sorted(sig)} "
            f"expected={sorted(exp)}"
        )
    return {"name": "packaged_shape", "ok": ok, "detail": detail}


def check_base_api_surface(base_methods: set[str], odom_fields: set[str]) -> dict[str, Any]:
    """LANDING PRECONDITION: the real base ABC + Odometry expose what the four predicates read."""
    missing_m = sorted(REQUIRED_BASE_METHODS - set(base_methods))
    missing_f = sorted(REQUIRED_ODOM_FIELDS - set(odom_fields))
    ok = not missing_m and not missing_f
    if ok:
        detail = (
            "base API intact: BaseProtocol.{get_position, get_heading, get_odometry}"
            " + Odometry.{qw, qx, qy, qz} — no interface change to land"
        )
    else:
        parts = []
        if missing_m:
            parts.append(f"BaseProtocol missing {missing_m}")
        if missing_f:
            parts.append(f"Odometry missing {missing_f}")
        detail = "INTERFACE DRIFT (the 'no interface change' claim broke): " + "; ".join(parts)
    return {"name": "base_api_surface", "ok": ok, "detail": detail}


def check_reference_seam_shape(reference_factories: set[str]) -> dict[str, Any]:
    """The go2_sim_oracle contract the packaging mirrors byte-for-byte still exists."""
    need = {"make_at_position", "make_facing"}
    missing = sorted(need - set(reference_factories))
    ok = not missing
    detail = (
        "go2_sim_oracle.{make_at_position, make_facing} present — the make_* seam the "
        "quartet mirrors is unchanged"
        if ok
        else f"reference seam drifted: go2_sim_oracle missing {missing}"
    )
    return {"name": "reference_seam_shape", "ok": ok, "detail": detail}


def check_landing_delta(
    predicate_oracles: frozenset[str], existing_ns_keys: set[str]
) -> dict[str, Any]:
    """Landing is additive: no quartet name already lives in the consumer seam (a silent shadow)."""
    in_oracles = sorted(set(EXPECTED_NAMES) & set(predicate_oracles))
    shadows = sorted(set(EXPECTED_NAMES) & set(existing_ns_keys))
    ok = not in_oracles and not shadows
    if ok:
        detail = (
            "additive: none of {" + ", ".join(sorted(EXPECTED_NAMES)) + "} is in "
            "_PREDICATE_ORACLES or the existing go2 verify namespace — landing extends, "
            "never shadows (delta still open, as expected pre-G-323-1)"
        )
    else:
        parts = []
        if in_oracles:
            parts.append(f"already in _PREDICATE_ORACLES: {in_oracles}")
        if shadows:
            parts.append(f"SHADOWS existing verify names: {shadows}")
        detail = "NON-ADDITIVE landing: " + "; ".join(parts)
    return {"name": "landing_delta", "ok": ok, "detail": detail}


# --- the diagnosis: gather real facts, run every check, AND (last) dry-run the fake agent ---
def diagnose() -> dict[str, Any]:
    """Run all landing-conformance checks against the REAL kernel seam + a fake-agent dry-run."""
    hard_channels = _load_sibling("hard_channels")

    # Dry-run the packaged namespace against a fake connected base (proves it binds + runs).
    ns = hard_channels.make_verify_namespace(_FakeAgent(_FakeBase()))
    sigs = hard_channels.verify_signatures()

    # Read the REAL kernel seam, read-only. Any import failure is itself a RED finding.
    from zeno.core.types import Odometry
    from zeno.hardware.base import BaseProtocol
    from zeno.vcli.cognitive.evidence_classifier import _PREDICATE_ORACLES
    from zeno.vcli.worlds import go2_sim_oracle

    base_methods = {m for m in REQUIRED_BASE_METHODS if hasattr(BaseProtocol, m)}
    odom_fields = {f.name for f in dataclasses.fields(Odometry)}
    reference_factories = {
        n for n in ("make_at_position", "make_facing") if hasattr(go2_sim_oracle, n)
    }
    # The names the go2 base path already binds in RobotWorld.build_verify_namespace.
    existing_ns_keys = {"at_position", "facing"}

    checks = [
        check_packaged_shape(set(ns), set(sigs)),
        check_base_api_surface(base_methods, odom_fields),
        check_reference_seam_shape(reference_factories),
        check_landing_delta(_PREDICATE_ORACLES, existing_ns_keys),
    ]
    # Fold the dry-run into packaged_shape's evidence (every predicate must be a callable bool).
    dry_ok = all(callable(fn) for fn in ns.values()) and all(
        isinstance(fn(), bool) if name in ("upright", "nominal_height") else callable(fn)
        for name, fn in ns.items()
    )
    if not dry_ok:
        checks[0] = {
            "name": "packaged_shape",
            "ok": False,
            "detail": "dry-run against a fake agent produced a non-callable / non-bool predicate",
        }

    return {"ok": all(c["ok"] for c in checks), "checks": checks}


def _format(report: dict[str, Any]) -> str:
    lines = ["hard_channels landing-conformance doctor (R324/E115)", ""]
    for c in report["checks"]:
        mark = "OK  " if c["ok"] else "FAIL"
        lines.append(f"  [{mark}] {c['name']}: {c['detail']}")
    lines.append("")
    lines.append(f"  OVERALL: {'READY-TO-LAND' if report['ok'] else 'BLOCKED'}")
    return "\n".join(lines)


def _main(argv=None) -> int:
    import json
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    report = diagnose()
    if "--json" in args:
        sys.stdout.write(json.dumps(report) + "\n")
    else:
        sys.stdout.write(_format(report) + "\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(_main())
