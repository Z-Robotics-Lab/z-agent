# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w — first-class BYO world driving a Unitree Go2W in an Isaac Sim warehouse.

Migrated from the go2W_Sim repo's ``scripts/vector_os/isaac_go2w_world.py`` (the
plugin that was validated end-to-end in P2). Now a first-class world shipped in
the kernel's ``worlds`` package: it is registered as a BUILT-IN (lazy factory in
worlds/registry.py), so ``--world go2w`` resolves it WITHOUT VECTOR_WORLD_PLUGINS.

It still implements the World Protocol structurally (duck-typed) — nothing in the
kernel is subclassed. Invariant 4 holds: this module is imported ONLY on
resolution (the registry's factory imports it lazily), never at kernel/CLI load.

链路：agent 工具 -> HTTP 桥(127.0.0.1:8042, scripts/nav/agent_bridge.py) ->
DDS 域 42 -> CMU 导航栈 -> RL locomotion -> Isaac 仓库里的 Go2W。
verify 谓词 go2w_at 读 /gt（SIM 地面真值，执行者无法伪造——"Verify is the moat"）。
"""
from __future__ import annotations

import json
import math
import os
import urllib.request
from typing import Any

from vector_os_nano.vcli.tools.base import ToolContext, ToolResult, tool
from vector_os_nano.vcli.worlds.base import DecomposeVocab

# The nav bridge endpoint. Overridable via GO2W_BRIDGE so a differently-hosted
# bridge (a remote sim, a non-default port) needs no code edit — read lazily so
# the env var can be set after import but before the first request.
_DEFAULT_BRIDGE = "http://127.0.0.1:8042"


def _bridge() -> str:
    """Return the nav-bridge base URL (env GO2W_BRIDGE overrides the default)."""
    return os.environ.get("GO2W_BRIDGE", "").strip() or _DEFAULT_BRIDGE


# Back-compat module constant: the original plugin exposed ``BRIDGE`` as a plain
# string. Kept so any importer reading ``go2w.BRIDGE`` still works; the live
# request path uses ``_bridge()`` so GO2W_BRIDGE is honoured at call time.
BRIDGE = _DEFAULT_BRIDGE


def _get(path: str) -> dict:
    with urllib.request.urlopen(f"{_bridge()}/{path}", timeout=5) as r:
        return json.loads(r.read())


def _post(path: str, obj: dict) -> dict:
    req = urllib.request.Request(
        f"{_bridge()}/{path}", data=json.dumps(obj).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())


@tool(
    name="go2w_navigate",
    description=(
        "Send the Go2W robot dog to a target position (x, y) in the SLAM map frame. "
        "The navigation stack plans around obstacles and drives the robot there. "
        "Non-blocking: returns immediately; use go2w_where to track progress. "
        "让 Go2W 机器狗导航到地图坐标 (x, y)。"
    ),
    read_only=False,
    permission="allow",
)
class Go2WNavigateTool:
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "x": {"type": "number", "description": "target x (map frame, meters)"},
            "y": {"type": "number", "description": "target y (map frame, meters)"},
        },
        "required": ["x", "y"],
    }

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            res = _post("waypoint", {"x": params["x"], "y": params["y"]})
            return ToolResult(content=json.dumps({"sent": res}))
        except Exception as e:  # noqa: BLE001 — 桥边界
            return ToolResult(content=f"bridge error: {e}", is_error=True)


@tool(
    name="go2w_where",
    description=(
        "Get the Go2W robot's current SLAM pose {x, y, z, stamp} in the map frame. "
        "查询 Go2W 当前位姿。"
    ),
    read_only=True,
    permission="allow",
)
class Go2WWhereTool:
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            return ToolResult(content=json.dumps(_get("pose")))
        except Exception as e:  # noqa: BLE001
            return ToolResult(content=f"bridge error: {e}", is_error=True)


def explored_volume() -> float:
    """独立裁判读数：已探索体积（m³），来自导航栈 visualization_tools 对真实
    LiDAR 回波的体素化累积（/explored_volume 经桥 /explore_progress 转发）。

    执行者（TARE/agent）无法伪造——它由独立节点从 /registered_scan 计算。
    verify 惯用法：``explored_volume() > <探索前基线 + 增益阈值>``（state-oracle
    对常数比较，可 GROUND）。fail-safe：桥不可达/无数据返回 0.0，绝不 raise
    进 verifier 沙箱。"""
    try:
        v = _get("explore_progress").get("explored_volume")
        return float(v) if v is not None else 0.0
    except Exception:  # noqa: BLE001 — verifier 沙箱边界，fail-safe
        return 0.0


def go2w_at(x: float, y: float, tol: float = 0.8) -> bool:
    """GT 谓词：机器人（SIM 地面真值）是否在 (x, y) 的 tol 米内。

    真值经 SLAM 原点补偿到 map 系：桥同时提供 /gt 与 /pose，用两者的当前差
    作为原点偏移的近似（静止时精确；行驶中误差 = SLAM 瞬时漂移，可接受）。
    """
    gt = _get("gt")
    pose = _get("pose")
    off_x, off_y = gt["x"] - pose["x"], gt["y"] - pose["y"]
    gx, gy = x + off_x, y + off_y  # 目标从 map 系换到 GT 系
    return math.hypot(gt["x"] - gx, gt["y"] - gy) < tol


# ---- 技能层（VGG MOTION skill 正门）+ embodiment ------------------------------
import time as _time

from vector_os_nano.core.skill import SkillRegistry, skill
from vector_os_nano.core.types import SkillResult


@skill(aliases=["navigate", "nav_to_pos", "nav", "go to", "导航", "去", "开到", "走到"])
class Go2WNavigateSkill:
    """阻塞式导航技能：发 waypoint 并轮询直到到达（SLAM 系）或超时。"""

    name = "navigate"
    description = ("Navigate the Go2W robot to map coordinates (x, y). "
                   "Blocks until arrival (tolerance ~0.7m) or 300s timeout.")

    def _target(self, context, kw):
        for src in (kw, getattr(context, "params", None) or {},
                    getattr(context, "args", None) or {}):
            if isinstance(src, dict) and "x" in src and "y" in src:
                return float(src["x"]), float(src["y"])
        text = str(getattr(context, "instruction", "") or getattr(context, "text", "") or kw)
        import re
        m = re.search(r"\(?\s*(-?\d+\.?\d*)\s*[,，]\s*(-?\d+\.?\d*)\s*\)?", text)
        if m:
            return float(m.group(1)), float(m.group(2))
        raise ValueError(f"no (x, y) target in skill call: {text[:120]}")

    def execute(self, context=None, **kw):
        import sys
        try:
            x, y = self._target(context, kw)
        except ValueError as e:
            print(f"[SKILL] target parse FAIL: {e}", file=sys.stderr, flush=True)
            return SkillResult(success=False, error_message=str(e))
        print(f"[SKILL] navigate -> ({x},{y}) ctx={str(getattr(context,'params',None))[:80]} kw={str(kw)[:80]}",
              file=sys.stderr, flush=True)
        _post("waypoint", {"x": x, "y": y})
        t0 = _time.time()
        while _time.time() - t0 < 300:
            _time.sleep(5)
            _post("waypoint", {"x": x, "y": y})  # 周期重发（栈只认最新）
            p = _get("pose")
            # 到达（0.45m）后冻结：waypoint 改发当前位置让 pathFollower 停追，
            # 停稳复核（0.7m）后返回——verify（0.8m）才有余量且不再漂移触发重试
            if math.hypot(p["x"] - x, p["y"] - y) < 0.45:
                _post("waypoint", {"x": p["x"], "y": p["y"]})
                _time.sleep(6)
                p = _get("pose")
                d2 = math.hypot(p["x"] - x, p["y"] - y)
                print(f"[SKILL] held check d={d2:.2f} at ({p['x']:.2f},{p['y']:.2f})",
                      file=sys.stderr, flush=True)
                if d2 < 0.7:
                    return SkillResult(success=True, result_data={
                        "message": f"arrived+held ({p['x']:.2f},{p['y']:.2f})"})
        p = _get("pose")
        return SkillResult(success=False,
                           error_message=f"timeout at ({p['x']:.2f},{p['y']:.2f})")


@skill(aliases=["explore", "探索", "自主探索", "建图", "去探索"])
class Go2WExploreSkill:
    """阻塞式自主探索：触发 TARE，轮询独立裁判（explored_volume）直到
    增益达标 / TARE 报完成 / 预算耗尽。

    需要导航栈以 NAV_MODE=explore 拉起（TARE 在 launch 里）；waypoint 模式下
    POST /explore 虽 200 但无人订阅 /start_exploration——增益不会来，按超时失败
    并在 message 里给出提示。已知：TARE 无软停（源码只认 start=true），技能
    返回后机器人会继续探索；硬停 = NAV_MODE=waypoint 重启链（bringup.sh）。
    """

    name = "explore"
    description = (
        "Autonomously explore and map the environment (TARE planner). Blocks "
        "until explored volume grows by at least min_gain_m3 (default 120), "
        "TARE reports finished, or budget_s (default 300s wall) runs out. "
        "Returns the before/after explored_volume readings.")
    parameters = {
        "budget_s": {"type": "number", "default": 300,
                     "description": "wall-clock budget seconds", "required": False},
        "min_gain_m3": {"type": "number", "default": 120,
                        "description": "success threshold on volume gain", "required": False},
    }
    preconditions: list = []          # 无 arm/gripper——armless 也可探索
    effects = {"base_state": "exploring"}  # 'base' 关键字 -> motor 技能（正确归类）

    def execute(self, params=None, context=None, **kw):
        import sys
        p = params if isinstance(params, dict) else {}
        budget = float(p.get("budget_s") or kw.get("budget_s") or 300)
        min_gain = float(p.get("min_gain_m3") or kw.get("min_gain_m3") or 120)
        try:
            before = explored_volume()
            _post("explore", {})
        except Exception as e:  # noqa: BLE001 — 409（goto 冷却）或桥错误
            return SkillResult(success=False,
                               error_message=f"explore start refused: {e}")
        print(f"[SKILL] explore start volume_before={before:.0f}m3 "
              f"budget={budget}s min_gain={min_gain}", file=sys.stderr, flush=True)
        t0 = _time.time()
        vol, finished = before, False
        while _time.time() - t0 < budget:
            _time.sleep(10)
            try:
                prog = _get("explore_progress")
                vol = float(prog.get("explored_volume") or vol)
                finished = bool(prog.get("finished"))
            except Exception:  # noqa: BLE001 — 瞬断容忍，下一拍再读
                continue
            gain = vol - before
            if finished or gain >= min_gain:
                msg = (f"explored volume {before:.0f} -> {vol:.0f} m3 "
                       f"(gain {gain:.0f}{', TARE finished' if finished else ''}). "
                       f"Verify with: explored_volume() > {before + min_gain * 0.5:.0f}")
                print(f"[SKILL] explore OK: {msg}", file=sys.stderr, flush=True)
                return SkillResult(success=True, result_data={
                    "message": msg, "volume_before": round(before, 1),
                    "volume_after": round(vol, 1), "gain_m3": round(gain, 1),
                    "finished": finished})
        gain = vol - before
        return SkillResult(success=False, error_message=(
            f"explore budget exhausted: volume {before:.0f} -> {vol:.0f} m3 "
            f"(gain {gain:.0f} < {min_gain}). If gain stayed ~0 the stack is "
            f"likely in waypoint mode (needs NAV_MODE=explore bringup)."))


class IsaacGo2WEmbodiment:
    """最小 embodiment：VGG 就绪判据（_base 非 None）+ 技能注册表 + 状态读取。

    状态方法全部读真实数据（桥），供内核 verifier 绑定使用。
    """

    def __init__(self) -> None:
        self._base = self
        self._arm = None
        self._skill_registry = SkillRegistry()
        self._skill_registry.register(Go2WNavigateSkill())
        self._skill_registry.register(Go2WExploreSkill())

    def _build_context(self):
        """SkillWrapperTool 合同：技能执行上下文（本 embodiment 即 base）。"""
        from vector_os_nano.core.skill import SkillContext
        return SkillContext(bases={"go2w": self})

    def _sync_robot_state(self) -> None:
        """SkillWrapperTool 合同：状态全部经桥实时读取，无需同步——no-op。"""
        return None

    def navigate_to(self, x: float, y: float, timeout: float = 240.0) -> bool:
        """native_loop 的 base 合同：阻塞导航，到达返回 True。

        到达（0.45m）后 waypoint 冻结在当前位置（pathFollower 停追不再漂），
        停稳复核 0.7m —— verify 的 go2w_at（0.8m）留有余量。
        """
        import sys
        import time as _t
        x, y = float(x), float(y)
        # 慢动作 sim（约 0.3-0.5x 实时）里导航需 100-300s 墙钟；调用方的 60s 默认
        # 超时会制造假失败步毒化判决——基座最了解自身动力学，下限钳 240s
        timeout = max(float(timeout), 240.0)
        print(f"[BASE] navigate_to ({x},{y}) timeout={timeout}", file=sys.stderr, flush=True)
        _post("waypoint", {"x": x, "y": y})
        t0 = _t.time()
        while _t.time() - t0 < timeout:
            _t.sleep(5)
            _post("waypoint", {"x": x, "y": y})
            p = _get("pose")
            if math.hypot(p["x"] - x, p["y"] - y) < 0.45:
                _post("waypoint", {"x": p["x"], "y": p["y"]})  # 冻结
                _t.sleep(6)
                p = _get("pose")
                d = math.hypot(p["x"] - x, p["y"] - y)
                print(f"[BASE] arrived+held d={d:.2f}", file=sys.stderr, flush=True)
                return d < 0.7
        print("[BASE] navigate_to timeout", file=sys.stderr, flush=True)
        return False

    def get_position(self):
        p = _get("pose")
        return (p["x"], p["y"])

    def get_heading(self):
        return float(_get("pose").get("yaw", 0.0))

    def get_pose(self):
        p = _get("pose")
        return (p["x"], p["y"], p.get("yaw", 0.0))


class IsaacGo2WWorld:
    """World Protocol 的鸭子类型实现（不继承任何内核类）。"""

    name = "isaac-go2w"

    def is_robot(self) -> bool:
        return True

    def persona_blocks(self) -> tuple[str, str]:
        return (
            "You operate a Unitree Go2W robot dog (with a PiPER arm) inside an "
            "Isaac Sim warehouse. It navigates via a SLAM + planner stack.",
            "Use go2w_navigate(x, y) to send it somewhere; use go2w_where() to "
            "check progress. Navigation takes tens of seconds of sim time — "
            "poll go2w_where between checks. Verify arrival with "
            "go2w_at(x, y) == True. To explore/map the environment autonomously, "
            "call the explore skill (blocking; it reports explored_volume before/"
            "after); verify exploration progress with "
            "explored_volume() > <the before reading + ~60> using the numbers the "
            "skill returned.",
        )

    def register_tools(self, registry: Any, agent: Any) -> None:
        registry.register(Go2WNavigateTool(), category="go2w")
        registry.register(Go2WWhereTool(), category="go2w")

    def build_verify_namespace(self, agent: Any) -> dict[str, Any]:
        return {"go2w_at": go2w_at, "explored_volume": explored_volume}

    def register_capabilities(self, registry: Any, agent: Any, backend: Any) -> None:
        return None

    def build_embodiment(self) -> "IsaacGo2WEmbodiment":
        """BYO front door: the agent this world drives (no --sim needed).

        Returns a fresh IsaacGo2WEmbodiment so ``vector-cli --world go2w`` gets a
        connected, navigation-capable agent that talks to the Isaac stack over the
        HTTP bridge — the same object a --sim run would fill the agent slot with.
        """
        return IsaacGo2WEmbodiment()

    def decompose_vocab(self) -> DecomposeVocab | None:
        return DecomposeVocab(
            planner_intro=(
                "Drive a Go2W robot dog in a warehouse. Navigation goals are "
                "map-frame (x, y) positions; autonomous exploration is graded by "
                "explored_volume() growth."
            ),
            verify_functions=frozenset({"go2w_at", "explored_volume"}),
        )

    def derive_vocab_from_registry(self) -> bool:
        return False


# Canonical world id + back-compat alias. ``go2w`` is the first-class id used by
# ``--world go2w``; ``isaac-go2w`` is the original plugin id, kept so anything that
# referenced it (P2 acceptance rows, docs) still resolves.
GO2W_WORLD = "go2w"
GO2W_WORLD_ALIAS = "isaac-go2w"


def register() -> None:
    """Register this world under both ids (idempotent; replace=True).

    Runs on import (module-level call below) so importing ``worlds.go2w`` — as the
    registry's lazy built-in factory does on ``--world go2w`` resolution — makes
    both ids resolvable. Also importable directly / via VECTOR_WORLD_PLUGINS.
    """
    from vector_os_nano.vcli.worlds.registry import get_world_registry

    reg = get_world_registry()
    reg.register(GO2W_WORLD, IsaacGo2WWorld, replace=True)
    reg.register(GO2W_WORLD_ALIAS, IsaacGo2WWorld, replace=True)


register()
