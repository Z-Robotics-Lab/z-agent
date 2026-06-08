# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Sim-oracle scene predicates: ``detect_objects`` / ``describe_scene``.

These replace the engine's empty perception STUBS (``detect_objects -> []``,
``describe_scene -> ""``) WHEN the playground world is active. They source ground
truth from the connected arm's ``get_object_positions`` — restricted to the
scenario's known ``object_names`` — and return the SAME shapes the stubs use:

- ``detect_objects(query="") -> list[dict]``  (each: ``{"name", "x", "y", "z"}``)
- ``describe_scene() -> str``

This is the deterministic verify oracle, kept independent from the VLM perception
skill (ADR-008). When the arm is absent / not connected, both fail safe (empty
list / empty string) so they never raise into the GoalVerifier sandbox.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from vector_os_nano.playground.verify.arm_predicates import _get_arm

logger = logging.getLogger(__name__)


def _scene_objects(agent: Any, object_names: tuple[str, ...]) -> dict[str, list[float]]:
    """Return ground-truth positions for the scenario's known objects (fail-safe).

    Reads ``arm.get_object_positions()`` and filters to ``object_names`` so the
    oracle only reports the scene's declared graspables. Empty dict on any
    failure or when the arm is unavailable.
    """
    arm = _get_arm(agent)
    if arm is None:
        return {}
    try:
        positions = arm.get_object_positions()
    except Exception as exc:  # noqa: BLE001
        logger.debug("playground get_object_positions failed: %s", exc)
        return {}
    known = set(object_names)
    out: dict[str, list[float]] = {}
    for name, pos in positions.items():
        if known and name not in known:
            continue
        try:
            out[name] = [float(pos[0]), float(pos[1]), float(pos[2])]
        except (TypeError, ValueError, IndexError):
            continue
    return out


def make_detect_objects(
    agent: Any, object_names: tuple[str, ...]
) -> Callable[..., list[dict[str, Any]]]:
    """Build ``detect_objects(query="")`` bound to *agent* + scenario objects.

    Returns a list of ``{"name", "x", "y", "z"}`` dicts (same list-of-dict shape
    the engine stub returns, just non-empty). A non-empty ``query`` filters by
    case-insensitive substring match on the object name. Fails safe to ``[]``.
    """

    def detect_objects(query: str = "") -> list[dict[str, Any]]:
        objects = _scene_objects(agent, object_names)
        q = (query or "").strip().lower()
        result: list[dict[str, Any]] = []
        for name in sorted(objects):
            if q and q not in name.lower():
                continue
            x, y, z = objects[name]
            result.append({"name": name, "x": x, "y": y, "z": z})
        return result

    return detect_objects


def make_detect_producer(
    agent: Any, object_names: tuple[str, ...]
) -> Callable[..., dict[str, Any]]:
    """Build a detect PRODUCING-STEP callable bound to *agent* + scenario objects.

    Unlike ``detect_objects`` (a verify-namespace PREDICATE that returns a bare
    list), this is an EXECUTOR primitive: it runs the SAME deterministic
    sim-oracle detection but wraps the result as a producing step's structured
    output — ``{"objects": [...], "count": N}``. The executor captures that dict
    to the run Blackboard under the step name, so a downstream ``foreach`` whose
    ``source_step`` points at this step resolves ``source_step.objects`` to the
    REAL detected list (pure path traversal, never eval). This closes the gap
    where a foreach previously needed a fabricated detect primitive: a real
    detect-producing step now carries the objects list.

    Deterministic (sim oracle, no VLM) and fail-safe: an absent/unavailable arm
    yields ``{"objects": [], "count": 0}`` — never raises into the executor. The
    ``query`` argument (default ``""``) filters identically to ``detect_objects``.
    """

    detect = make_detect_objects(agent, object_names)

    def detect_producer(query: str = "", **_: Any) -> dict[str, Any]:
        objects = detect(query)
        return {"objects": objects, "count": len(objects)}

    return detect_producer


def make_describe_scene(
    agent: Any, object_names: tuple[str, ...]
) -> Callable[[], str]:
    """Build ``describe_scene()`` bound to *agent* + scenario objects.

    Returns a deterministic one-line summary of the objects present and their
    positions (same ``str`` shape the engine stub returns, just non-empty).
    Fails safe to ``""`` when no objects are observable.
    """

    def describe_scene() -> str:
        objects = _scene_objects(agent, object_names)
        if not objects:
            return ""
        parts = [
            f"{name} at ({x:.2f}, {y:.2f}, {z:.2f})"
            for name, (x, y, z) in sorted(objects.items())
        ]
        return "Tabletop scene: " + "; ".join(parts) + "."

    return describe_scene
