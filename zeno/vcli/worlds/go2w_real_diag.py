# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real motion diagnostics — tiny, dependency-free (breaks import cycles).

Field trace (2026-07-10): a latched guard silently eats motion commands; the
agent burned 10s timeouts and misdiagnosed a "rear blind spot". These helpers
turn that failure mode into an actionable message.
"""

from __future__ import annotations

import math
from typing import Any


def _latched_hint(base: Any) -> str | None:
    """Fail-fast hint when the agent's own E-stop latch is set."""
    if getattr(base, "estop_latched", False):
        return ("guard E-stop is LATCHED (agent-side record) — run "
                "resume_skill first, then retry the motion")
    return None


def wrap_angle(angle: float) -> float:
    """Wrap an angle delta into (-pi, pi] — the shortest signed rotation.

    Shared by the turn skill and the turned() verify oracle so both grade a
    heading crossing ±pi identically (the driver keeps its own copy — hardware
    modules never import vcli worlds).
    """
    return math.atan2(math.sin(angle), math.cos(angle))


def odom_fresh(base: Any, max_age_s: float = 3.0) -> bool:
    """Driver-known liveness: connected AND odometry younger than *max_age_s*.

    THE fast-status fact (field trace 2026-07-10 evening: bringup status
    blocked ~30s probing topics the driver already knew were flowing).
    Fail-safe False: no driver, not connected, no odom_age_s(), never-received
    or stale odometry, or any error — a missing oracle must never fake-pass.
    """
    if base is None:
        return False
    try:
        if not getattr(base, "is_connected", False):
            return False
        age_fn = getattr(base, "odom_age_s", None)
        age = age_fn() if callable(age_fn) else None
        return age is not None and float(age) < float(max_age_s)
    except Exception:  # noqa: BLE001 — liveness probe must never raise
        return False


def _stalled_hint(start_pos: Any, end_pos: Any) -> str:
    """Distinguish 'blocked path' from 'commands eaten by a latched guard'."""
    try:
        d = math.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1])
        if d < 0.05:
            return (" — zero displacement while commanding: guard likely "
                    "latched (estop/manual, possibly from a previous session)."
                    " Try resume_skill, then retry")
    except Exception:  # noqa: BLE001
        pass
    return ""


# ---------------------------------------------------------------------------
# Operator-facing operation log (field request 2026-07-10: "输出更详细一点的
# log我复制给你") — every skill/lifecycle event lands in one greppable file.
# ---------------------------------------------------------------------------

import datetime as _dt
import os as _os

_OPLOG_PATH = _os.path.expanduser("~/go2w-nuc/logs/zeno_agent.log")


def set_oplog_path(path: str) -> None:
    global _OPLOG_PATH
    _OPLOG_PATH = path


def oplog(kind: str, name: str, msg: str) -> None:
    """Append one timestamped line; NEVER raises (best-effort diagnostics)."""
    try:
        line = (f"{_dt.datetime.now().strftime('%m-%d %H:%M:%S')} | "
                f"{kind:<9}| {name:<14}| {msg}\n")
        with open(_OPLOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:  # noqa: BLE001 — logging must never break a skill
        pass
