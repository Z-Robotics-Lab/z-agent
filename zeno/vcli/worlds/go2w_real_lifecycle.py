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
from zeno.vcli.worlds.go2w_real_diag import oplog
from zeno.vcli.worlds.go2w_real_skills import nav_sh_path

#: nav.sh subcommands this skill may run (lifecycle only — motion stays with
#: the dedicated skills; explore/route overlays have their own managers).
_ACTIONS: frozenset[str] = frozenset({"start", "stop"})

#: SLAM warmup budget: nav.sh start returns after launch; readiness follows
#: in ~40-60s. The poller gets the remainder of this window.
_READY_TIMEOUT_S: float = 150.0


def _default_runner(argv: list[str], timeout: float) -> Any:
    return subprocess.run(argv, capture_output=True, text=True, timeout=timeout)


def _default_ready_probe(hw: Any) -> bool:
    """Quick liveness probe: is the stack ALREADY up? (~5s budget, no side effects)."""
    return _default_ready_poller(hw, timeout_s=5.0)


def _default_ready_poller(hw: Any, timeout_s: float) -> bool:
    """True once the driver sees fresh odometry (stack truly up).

    A dying stack keeps publishing for a few seconds after nav.sh stops it —
    residue that fooled the 15:20 restart into "ready in 3s". Cold starts
    therefore wait a QUIET period first, then demand freshness TWICE 3s apart.
    """
    if hw is None:
        return False
    time.sleep(8.0)  # let any dying publisher actually die
    deadline = time.monotonic() + timeout_s
    fresh_streak = 0
    while time.monotonic() < deadline:
        try:
            if not getattr(hw, "is_connected", False):
                hw.connect()
            age = hw.odom_age_s() if hasattr(hw, "odom_age_s") else None
            if age is not None and age < 2.0:
                fresh_streak += 1
                if fresh_streak >= 2:
                    return True
                time.sleep(3.0)
                continue
            fresh_streak = 0
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
        "Nav-stack lifecycle. action='start' is IDEMPOTENT: if the stack is "
        "already running it does NOTHING — it can never rebuild a live stack. "
        "Only a cold stack is launched (blocks until odometry flows, <=150s). "
        "action='stop' tears down (ONLY on explicit operator command). There "
        "is NO restart — stack rebuilds are operator-only. NOT standing up — "
        "use standup for posture. 启动(幂等)/关闭导航栈(非起立;无重启)。")
    requires = ()
    preconditions: list = []
    effects = {"stack": "running"}

    def __init__(self, runner: Callable[..., Any] | None = None,
                 ready_poller: Callable[[Any, float], bool] | None = None,
                 ready_probe: Callable[[Any], bool] | None = None) -> None:
        self._runner = runner or _default_runner
        self._ready = ready_poller or _default_ready_poller
        self._probe = ready_probe or _default_ready_probe

    def execute(self, params=None, context=None, **kw) -> SkillResult:
        action = "start"
        for src in (params if isinstance(params, dict) else {}, kw):
            if isinstance(src, dict) and src.get("action"):
                action = str(src["action"]).lower()
                break
        if action == "restart":
            # Field trace 2026-07-10 15:20: the model restarted a HEALTHY
            # stack mid-conversation; the walk then ran on a 1-minute-old
            # SLAM map. Destructive rebuilds are operator actions.
            oplog("lifecycle", "bringup", "restart REFUSED (operator-only)")
            return SkillResult(
                success=False, diagnosis_code="restart_refused",
                error_message=("restart is OPERATOR-only (nav.sh start in a "
                               "terminal). If the stack is truly wedged, tell "
                               "the operator — do not rebuild it yourself."))
        if action not in _ACTIONS:
            return SkillResult(
                success=False, diagnosis_code="bad_action",
                error_message=(f"unknown lifecycle action {action!r}; valid: "
                               f"{sorted(_ACTIONS)} (posture -> standup/liedown)"))
        hw = getattr(context, "base", None) if context is not None else None
        if action == "start" and self._probe(hw):
            oplog("lifecycle", "bringup", "start requested — stack already "
                  "running, NOT touched (idempotent)")
            return SkillResult(success=True, result_data={
                "action": "start",
                "message": ("stack already running — not touched (use "
                            "action='restart' to force a rebuild)"),
                "verify_hint": "stack_ready()"})
        nav_action = "start" if action == "restart" else action
        script = nav_sh_path()
        oplog("lifecycle", "bringup", f"nav.sh {nav_action} launching...")
        try:
            proc = self._runner(["bash", script, nav_action], timeout=180.0)
        except Exception as exc:  # noqa: BLE001 — honest failure, never raise
            return SkillResult(success=False, diagnosis_code="nav_sh_failed",
                               error_message=f"nav.sh {action} failed: {exc}")
        if getattr(proc, "returncode", 1) != 0:
            return SkillResult(
                success=False, diagnosis_code="nav_sh_failed",
                error_message=(f"nav.sh {action} rc={proc.returncode}: "
                               f"{(getattr(proc, 'stderr', '') or '')[-200:]}"))
        if action == "stop":
            oplog("lifecycle", "bringup", "stack stopped")
            return SkillResult(success=True, result_data={"action": "stop"})
        if not self._ready(hw, _READY_TIMEOUT_S):
            oplog("lifecycle", "bringup", "launched but odometry never ready")
            return SkillResult(
                success=False, diagnosis_code="stack_not_ready",
                error_message=("stack launched but odometry never became ready "
                               f"within {_READY_TIMEOUT_S:.0f}s — check nav.sh "
                               "status / lidar power"))
        oplog("lifecycle", "bringup", f"{action}: stack ready (odometry flowing)")
        return SkillResult(success=True, result_data={
            "action": action,
            "verify_hint": "stack_ready()",
        })


@skill(aliases=["resume", "恢复", "解除急停", "release", "estop_release",
                "恢复自主", "继续"], direct=True)
class RealResumeSkill:
    """Release the guard latches (E-stop / manual) so motion flows again.

    Field trace (2026-07-10): after stop, every motion command was silently
    eaten by the latched guard and the planner had NO resume strategy — it
    could not even follow the operator's explicit "要 release" instruction.
    Deliberately a HUMAN-VISIBLE step: the agent never auto-releases an
    E-stop inside a motion skill; resuming is always its own planned action.
    """

    name = "resume"
    description = ("Release the software E-stop / manual latch (estop_release) "
                   "so autonomy can move again. REQUIRED after stop before any "
                   "motion. 解除急停/遥控接管,恢复自主。")
    requires = ()
    preconditions: list = []
    effects = {"base_state": "resumed"}

    def execute(self, params=None, context=None, **kw) -> SkillResult:
        base = getattr(context, "base", None) if context is not None else None
        if base is None:
            return SkillResult(success=False, diagnosis_code="no_base",
                               error_message="No Go2W hardware base")
        try:
            ok = bool(base.estop_release())
        except Exception as exc:  # noqa: BLE001 — honest failure
            return SkillResult(success=False, diagnosis_code="resume_failed",
                               error_message=f"estop_release failed: {exc}")
        oplog("lifecycle", "resume",
              "guard released" if ok else "estop_release FAILED")
        return SkillResult(
            success=ok,
            result_data={"message": "guard released — motion enabled"},
            error_message="" if ok else "/estop_release did not succeed")
