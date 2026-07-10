# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real lifecycle skill — the "启动导航栈" strategy the planner can pick.

First-REPL-contact finding (2026-07-10): stack lifecycle existed only as the
``go2w_real_bringup`` TOOL, so the VGG decomposer — which plans over SKILL
strategies — mapped "启动导航栈" to standup_skill (启动≈站立 in zh) and the
robot tried to stand with the stack down. This skill closes that gap; the
decompose few-shots in ``go2w_real_vocab.py`` pin the disambiguation.

Readiness is graded honestly: after ``nav.sh start`` returns, the driver must
actually see fresh ``/state_estimation`` odometry (the same oracle everything
else trusts) before we report success — "launched" is not "ready".
"""

from __future__ import annotations

import subprocess
import time
from typing import Any, Callable

from zeno.core.skill import skill
from zeno.core.types import SkillResult
from zeno.vcli.worlds.go2w_real_skills import nav_sh_path

#: nav.sh subcommands this skill may run (lifecycle only — motion stays with
#: the dedicated skills; explore/route overlays have their own managers).
_ACTIONS: frozenset[str] = frozenset({"start", "stop"})

#: SLAM warmup budget: nav.sh start returns after launch; readiness follows
#: in ~40-60s. The poller gets the remainder of this window.
_READY_TIMEOUT_S: float = 150.0


def _default_runner(argv: list[str], timeout: float) -> Any:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


def _default_ready_poller(hw: Any, timeout_s: float) -> bool:
    """True once the driver sees fresh odometry (stack truly up)."""
    if hw is None:
        return False
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            if not getattr(hw, "is_connected", False):
                hw.connect()
            age = hw.odom_age_s() if hasattr(hw, "odom_age_s") else None
            if age is not None and age < 2.0:
                return True
            if age is None and getattr(hw, "is_connected", False):
                # driver without an age probe: fresh position readable = up
                pos = hw.get_position()
                if pos is not None:
                    return True
        except Exception:  # noqa: BLE001 — keep polling until deadline
            pass
        time.sleep(3.0)
    return False


@skill(aliases=["bringup", "启动导航栈", "启动栈", "start_stack", "stop_stack",
                "关闭导航栈", "开机", "启动系统"], direct=True)
class RealBringupSkill:
    """Bring the nav stack up (blocking until SLAM-ready) or tear it down."""

    name = "bringup"
    description = (
        "Nav-stack lifecycle: action='start' launches the stack via nav.sh and "
        "BLOCKS until odometry flows (SLAM ready, <=150s); action='stop' tears "
        "it down. This is NOT standing up — use standup for posture. "
        "启动/关闭导航栈(非起立)。")
    requires = ()
    preconditions: list = []
    effects = {"stack": "running"}

    def __init__(self, runner: Callable[..., Any] | None = None,
                 ready_poller: Callable[[Any, float], bool] | None = None) -> None:
        self._runner = runner or _default_runner
        self._ready = ready_poller or _default_ready_poller

    def execute(self, params=None, context=None, **kw) -> SkillResult:
        action = "start"
        for src in (params if isinstance(params, dict) else {}, kw):
            if isinstance(src, dict) and src.get("action"):
                action = str(src["action"]).lower()
                break
        if action not in _ACTIONS:
            return SkillResult(
                success=False, diagnosis_code="bad_action",
                error_message=(f"unknown lifecycle action {action!r}; valid: "
                               f"{sorted(_ACTIONS)} (posture -> standup/liedown)"))
        script = nav_sh_path()
        try:
            proc = self._runner(["bash", script, action], timeout=180.0)
        except Exception as exc:  # noqa: BLE001 — honest failure, never raise
            return SkillResult(success=False, diagnosis_code="nav_sh_failed",
                               error_message=f"nav.sh {action} failed: {exc}")
        if getattr(proc, "returncode", 1) != 0:
            return SkillResult(
                success=False, diagnosis_code="nav_sh_failed",
                error_message=(f"nav.sh {action} rc={proc.returncode}: "
                               f"{(getattr(proc, 'stderr', '') or '')[-200:]}"))
        if action == "stop":
            return SkillResult(success=True, result_data={"action": "stop"})
        hw = getattr(context, "base", None) if context is not None else None
        if not self._ready(hw, _READY_TIMEOUT_S):
            return SkillResult(
                success=False, diagnosis_code="stack_not_ready",
                error_message=("stack launched but odometry never became ready "
                               f"within {_READY_TIMEOUT_S:.0f}s — check nav.sh "
                               "status / lidar power"))
        return SkillResult(success=True, result_data={
            "action": "start",
            "verify_hint": "stack_ready()",
        })
