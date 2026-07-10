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
