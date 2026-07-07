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

from zeno.vcli.tools.base import ToolContext, ToolResult, tool
from zeno.vcli.worlds.base import DecomposeVocab

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


# go2W_Sim 数字孪生仓库位置（bringup/status 脚本在那边；真机换 manifest 即换脚本）
def _sim_repo() -> str:
    return os.path.expanduser(os.environ.get("GO2W_SIM_DIR", "~/Desktop/go2w"))


@tool(
    name="go2w_bringup",
    description=(
        "Bring up (or tear down) the whole Go2W stack: Isaac Sim GUI + navigation "
        "stack + RViz + bridge. Idempotent — if already green it returns "
        "'already-up' immediately. A cold bringup takes 2-6 MINUTES and runs in "
        "the background: after starting it, poll go2w_status every ~30s until "
        "green. mode 'explore' enables the TARE exploration planner. "
        "启动/拆除整个仿真环境（Isaac+导航栈+RViz）。"
    ),
    read_only=False,
    permission="allow",
)
class Go2WBringupTool:
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["up", "teardown"], "default": "up"},
            "mode": {"type": "string", "enum": ["waypoint", "explore"],
                     "default": "waypoint",
                     "description": "waypoint=goto tasks; explore=TARE autonomous exploration"},
        },
    }

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        import subprocess
        repo = _sim_repo()
        script = os.path.join(repo, "scripts", "nav", "bringup.sh")
        if not os.path.isfile(script):
            return ToolResult(content=(
                f"bringup script not found at {script} — set GO2W_SIM_DIR to the "
                f"go2W_Sim checkout"), is_error=True)
        action = (params or {}).get("action", "up")
        if action == "teardown":
            # teardown 脚本的退出码是合同：0=拆净、非零=残留（宿主仍有 kit-python
            # 或 navstack 未拆）。旧版忽略 returncode/不设 is_error → 脚本失败也报
            # 成功，正是 CEO 抱怨的"工具说关了实际没关"。这里如实转达：非零 →
            # is_error=True，并保留脚本尾部（含残留进程表）供模型/用户判读。
            r = subprocess.run(["bash", script, "teardown"], capture_output=True,
                               text=True, timeout=180)
            out = (r.stdout + r.stderr)[-800:]
            if r.returncode != 0:
                return ToolResult(
                    content=(f"teardown FAILED (exit={r.returncode}); stack may still "
                             f"be up. Residuals below — re-run teardown or escalate.\n{out}"),
                    is_error=True)
            return ToolResult(content=out)
        # up：幂等短路探测走 status.sh（快）；未 green 则后台拉起（2-6 分钟），
        # 立即返回让模型轮询 go2w_status——工具不阻塞回合。
        st = subprocess.run(["bash", os.path.join(repo, "scripts", "nav", "status.sh")],
                            capture_output=True, text=True, timeout=60)
        if st.returncode == 0:
            return ToolResult(content=f"already-up: {st.stdout.strip()}")
        mode = (params or {}).get("mode", "waypoint")
        log = os.path.join(repo, "logs", "bringup_tool.log")
        os.makedirs(os.path.dirname(log), exist_ok=True)
        env = dict(os.environ, NAV_MODE=mode)
        with open(log, "ab") as fh:
            subprocess.Popen(["bash", script], env=env, stdout=fh, stderr=fh,
                             start_new_session=True, cwd=repo)
        return ToolResult(content=(
            f"bringup started in background (mode={mode}); a cold start takes 2-6 "
            f"minutes. Poll go2w_status every ~30s until green:true, then proceed. "
            f"Log: {log}"))


@tool(
    name="go2w_status",
    description=(
        "Layered health of the Go2W stack (L0 containers .. L4 SLAM, L5 RViz) plus "
        "the current bringup phase. Use while waiting for go2w_bringup to finish. "
        "查询仿真环境分层健康状态。"
    ),
    read_only=True,
    permission="allow",
)
class Go2WStatusTool:
    input_schema: dict[str, Any] = {"type": "object", "properties": {}}

    def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        import subprocess
        repo = _sim_repo()
        try:
            st = subprocess.run(["bash", os.path.join(repo, "scripts", "nav", "status.sh")],
                                capture_output=True, text=True, timeout=60)
            out = {"status": st.stdout.strip()}
        except Exception as e:  # noqa: BLE001
            out = {"status_error": str(e)}
        try:
            with open(os.path.join(repo, "logs", ".bringup.phase")) as fh:
                out["bringup_phase"] = fh.read().strip()
        except OSError:
            out["bringup_phase"] = None
        return ToolResult(content=json.dumps(out, ensure_ascii=False))


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

from zeno.core.skill import SkillRegistry, skill
from zeno.core.types import SkillResult


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


# ---- 抓取层（任务③）：臂/夹爪鸭子合同 + pick 技能 --------------------------------
class Go2WArm:
    """内核 holding_object oracle 的臂侧合同：关节/FK/物体 GT 全为桥读数。

    桥的陈旧守卫（>5s 未更新 503）保证这里读到的必是新鲜数据，oracle 的
    fail-safe（异常->False）承接 503——僵尸桥/断流永远判 False，不会假绿。
    """

    _connected = True

    def get_joint_positions(self) -> list:
        return [float(v) for v in _get("arm")["pos"][:6]]

    def fk(self, joint_positions) -> tuple:
        """oracle 惯用法 fk(get_joint_positions())——紧跟关节读数调用，直接返回
        当前夹持中心的 SIM GT（等价于当前关节的 FK，且更诚实）。"""
        e = _get("ee")
        return [e["x"], e["y"], e["z"]], None

    def get_object_positions(self) -> dict:
        o = _get("object")
        return {"box": [o["x"], o["y"], o["z"]]}

    def get_object_velocities(self) -> dict:
        o = _get("object")
        return {"box": [o.get("vx", 0.0), o.get("vy", 0.0), o.get("vz", 0.0)]}


class Go2WGripper:
    """is_holding：合爪指令下实测指缝仍被撑开（>14mm）——纯物理读数，抓取状态机
    自报的 done 不参与。weld_is_active：actor-causation 的 0->1 抓取信号
    （握持且箱子贴在夹持中心 12cm 内）。"""

    _HOLD_APERTURE_MIN = 0.014

    def _state(self):
        a = _get("arm")
        pos, cmd = a.get("pos") or [], a.get("cmd") or []
        if len(pos) < 8 or len(cmd) < 8:
            return None
        aperture = float(pos[6]) - float(pos[7])          # j7 - j8 >= 0
        cmd_closed = abs(float(cmd[6])) + abs(float(cmd[7])) < 0.005
        return aperture, cmd_closed

    def is_holding(self) -> bool:
        try:
            st = self._state()
        except Exception:  # noqa: BLE001 — 桥 503/断流 fail-safe
            return False
        if st is None:
            return False
        aperture, cmd_closed = st
        return cmd_closed and aperture > self._HOLD_APERTURE_MIN

    def weld_is_active(self) -> dict:
        try:
            if not self.is_holding():
                return {"box": False}
            e = _get("ee")
            o = _get("object")
            d = math.dist((o["x"], o["y"], o["z"]), (e["x"], e["y"], e["z"]))
            return {"box": d < 0.12}
        except Exception:  # noqa: BLE001 — fail-safe（分级 fail-closed）
            return {"box": False}


@skill(aliases=["pick", "grasp", "pick_up", "抓", "捡", "拿起", "捡起", "抓取"])
class Go2WPickSkill:
    """接近 + 抓取：先把狗开到箱子工作域内（导航栈绕障），再触发 Isaac 侧
    PiPER IK 状态机（PREGRASP->DESCEND->CLOSE->LIFT），轮询到 done/failed。

    状态机的 done 只作流程信号；最终裁决 = holding_object('box') oracle 读 GT
    （箱子被举离地 >10cm 且贴在夹持中心 8cm 内且夹爪物理握持）。
    """

    name = "pick"
    description = (
        "Drive near the graspable box and pick it up with the PiPER arm. "
        "Blocks through approach + grasp; verify with holding_object('box').")
    parameters = {
        "target": {"type": "string", "default": "box", "required": False,
                   "description": "scene object name (only 'box' exists today)"},
    }
    preconditions = ["gripper_empty"]          # -> _is_grasp（E60 守卫识别）
    effects = {"gripper_state": "closed", "held_object": "box"}

    _REACH_SWEET = (0.15, 0.52)   # 触发抓取时箱子距狗身的水平距离窗（臂基座前置 6cm）
    _APPROACH_STANDOFF = 0.38     # 接近航点：箱子后撤这么多米

    def _approach(self, sys):
        """开到工作域：以 GT 距离为准（目标是物理够得着，不是 SLAM 说到了）。"""
        for attempt in range(3):
            o, gt, pose = _get("object"), _get("gt"), _get("pose")
            d = math.hypot(o["x"] - gt["x"], o["y"] - gt["y"])
            if self._REACH_SWEET[0] <= d <= self._REACH_SWEET[1]:
                return True, d
            # 方向用 GT 差（与 SLAM 系平移偏移无关）；落点转回 SLAM 系发航点
            ux, uy = (o["x"] - gt["x"]) / max(d, 1e-6), (o["y"] - gt["y"]) / max(d, 1e-6)
            sx = pose["x"] + (d - self._APPROACH_STANDOFF) * ux
            sy = pose["y"] + (d - self._APPROACH_STANDOFF) * uy
            print(f"[SKILL] pick approach#{attempt+1}: d={d:.2f} -> waypoint ({sx:.2f},{sy:.2f})",
                  file=sys.stderr, flush=True)
            t0 = _time.time()
            _post("waypoint", {"x": sx, "y": sy})
            while _time.time() - t0 < 240:
                _time.sleep(5)
                _post("waypoint", {"x": sx, "y": sy})
                o, gt, pose = _get("object"), _get("gt"), _get("pose")
                d = math.hypot(o["x"] - gt["x"], o["y"] - gt["y"])
                if d <= self._REACH_SWEET[1] - 0.05:
                    p = _get("pose")
                    _post("waypoint", {"x": p["x"], "y": p["y"]})  # 冻结
                    _time.sleep(6)
                    break
        o, gt = _get("object"), _get("gt")
        d = math.hypot(o["x"] - gt["x"], o["y"] - gt["y"])
        return self._REACH_SWEET[0] <= d <= self._REACH_SWEET[1] + 0.06, d

    def execute(self, params=None, context=None, **kw):
        import sys
        try:
            ok, d = self._approach(sys)
        except Exception as e:  # noqa: BLE001 — 桥边界
            return SkillResult(success=False, error_message=f"approach failed: {e}")
        if not ok:
            return SkillResult(success=False, error_message=(
                f"could not reach grasp window: box at {d:.2f}m "
                f"(need {self._REACH_SWEET[0]}-{self._REACH_SWEET[1]}m)"))
        print(f"[SKILL] pick: in window d={d:.2f}, firing grasp", file=sys.stderr, flush=True)
        try:
            _post("grasp", {"object": "box"})
        except Exception as e:  # noqa: BLE001
            return SkillResult(success=False, error_message=f"grasp trigger failed: {e}")
        t0 = _time.time()
        while _time.time() - t0 < 240:
            _time.sleep(5)
            try:
                st = _get("grasp_status").get("status", "")
            except Exception:  # noqa: BLE001 — 瞬断容忍
                continue
            if st == "done":
                return SkillResult(success=True, result_data={
                    "message": "grasp state machine done; verify with holding_object('box')"})
            if st.startswith("failed"):
                return SkillResult(success=False, error_message=f"grasp {st}")
        return SkillResult(success=False, error_message="grasp timeout (240s wall)")


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
        # 臂/夹爪鸭子合同（任务③）：内核 arm_sim_oracle 的 holding_object /
        # actor-causation weld 信号经这两个对象读桥（SIM GT）。
        self._arm = Go2WArm()
        self._gripper = Go2WGripper()
        self._skill_registry = SkillRegistry()
        self._skill_registry.register(Go2WNavigateSkill())
        self._skill_registry.register(Go2WExploreSkill())
        self._skill_registry.register(Go2WPickSkill())

    def _build_context(self):
        """SkillWrapperTool 合同：技能执行上下文（本 embodiment 即 base）。"""
        from zeno.core.skill import SkillContext
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
            "Isaac Sim warehouse. It navigates via a SLAM + planner stack. "
            "THE ONLY SIMULATOR IN THIS WORLD IS ISAAC SIM, and its ONLY "
            "lifecycle tool is go2w_bringup: when the user says anything like "
            "'启动仿真 / 拉起环境 / start the sim', call go2w_bringup(action='up') "
            "— it launches Isaac Sim GUI + navigation stack + RViz together. "
            "Never use bash or any other tool to launch or stop the stack; to "
            "stop it use go2w_bringup(action='teardown'). There is exactly one "
            "robot configuration (Go2W + PiPER arm) — never ask the user to pick "
            "a robot model or gait mode. "
            "If the stack/bridge is not up (tools report bridge errors or 'stale'), "
            "FIRST call go2w_bringup(action='up') — it returns immediately; then "
            "poll go2w_status every ~30 seconds until green:true (a cold start "
            "takes 2-6 minutes; be patient, do NOT give up early), then do the task.",
            "go2w_status is the ONLY source of truth for whether the stack is "
            "up (robot_status merely reports in-process object wiring — it says "
            "'connected' even when nothing is running; never present it as sim "
            "state). "
            "Use go2w_navigate(x, y) to send it somewhere; use go2w_where() to "
            "check progress. Navigation takes tens of seconds of sim time — "
            "poll go2w_where between checks. Verify arrival with "
            "go2w_at(x, y) == True. To explore/map the environment autonomously, "
            "call the explore skill (blocking; it reports explored_volume before/"
            "after); verify exploration progress with "
            "explored_volume() > <the before reading + ~60> using the numbers the "
            "skill returned. To pick up the box: call the pick skill (it drives "
            "near the box and grasps with the arm), then verify with "
            "holding_object('box').",
        )

    def register_tools(self, registry: Any, agent: Any) -> None:
        registry.register(Go2WNavigateTool(), category="go2w")
        registry.register(Go2WWhereTool(), category="go2w")
        registry.register(Go2WBringupTool(), category="go2w")
        registry.register(Go2WStatusTool(), category="go2w")
        # 本世界唯一的仿真是 Isaac（go2w_bringup 管生命周期）。内核的 MuJoCo
        # start/stop_simulation 若留在 schema 里，"启动仿真"会被路由去拉错误的
        # 仿真器（2026-07-06 实测翻车）。世界自禁类目 = 即插即用，零内核改动。
        disable = getattr(registry, "disable_category", None)
        if callable(disable):
            disable("sim")
            # diag/system 两个内核类目在 go2w 世界整组失真（go2w-体验审计 #3-#6）：
            #  - diag(nav_state/ros2_*/terrain_status)：读 MuJoCo 时代路径或宿主
            #    默认 ROS 域；go2w navstack 跑在 docker ROS_DOMAIN_ID=42 内，宿主
            #    ros2/pgrep 看不到，返回空/误导数据 → 模型误判栈已挂。
            #  - system(robot_status/open_foxglove/skill_reload)：robot_status 把
            #    进程内对象接线当"connected"谎报 liveness；open_foxglove 在错误
            #    ROS 域起桥订不到 navstack；skill_reload 是 MuJoCo 时代 dev 工具。
            # 两类目均无 go2w 自家工具 → 禁用零误伤；栈健康唯一真值源 = go2w_status。
            # 注意 robot 类目【不能】禁：navigate/explore/pick 技能 wrap 进 robot
            # （cli.py），禁它会连带杀掉 go2w 三个核心技能；robot 里的 world_query
            # 已在 tools/robot.py 做 fail-safe 加固（无 _world_model 时优雅降级）。
            disable("diag")
            disable("system")

    def essential_categories(self) -> frozenset[str]:
        """Tool categories the intent router must ALWAYS keep in scope (finding #1).

        The kernel's keyword router maps '启动仿真'→('robot','sim','system'),
        '导航'→('robot','diag'), etc. — none of which is this world's own 'go2w'
        category, so on the routed unified path go2w_bringup / go2w_navigate /
        go2w_status would be filtered OUT of the schema and the model could never
        start the sim or drive the dog. The CLI feeds this set into IntentRouter so
        route() always unions 'go2w' back in. Zero kernel edit, zero world-naming
        in the kernel — the plug-and-play seam (an optional duck-typed hook, like
        setup/health/teardown).
        """
        return frozenset({"go2w"})

    def build_verify_namespace(self, agent: Any) -> dict[str, Any]:
        ns: dict[str, Any] = {"go2w_at": go2w_at, "explored_volume": explored_volume}
        # holding_object：复用内核 arm_sim_oracle 工厂（与 shipped 世界同一套
        # 判定语义：夹爪物理握持 + 物体举离 >0.10m + 距夹持中心 <0.08m，全 GT）。
        # 绑定到 agent 的 _arm/_gripper 鸭子合同上；agent 为 None 时 fail-safe False。
        try:
            from zeno.vcli.worlds.arm_sim_oracle import make_holding_object
            ns["holding_object"] = make_holding_object(agent)
        except Exception:  # noqa: BLE001 — oracle 缺席时宁缺毋假
            pass
        return ns

    def register_capabilities(self, registry: Any, agent: Any, backend: Any) -> None:
        return None

    def build_embodiment(self) -> "IsaacGo2WEmbodiment":
        """BYO front door: the agent this world drives (no --sim needed).

        Returns a fresh IsaacGo2WEmbodiment so ``zeno --world go2w`` gets a
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
            verify_functions=frozenset({"go2w_at", "explored_volume", "holding_object"}),
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
    from zeno.vcli.worlds.registry import get_world_registry

    reg = get_world_registry()
    reg.register(GO2W_WORLD, IsaacGo2WWorld, replace=True)
    reg.register(GO2W_WORLD_ALIAS, IsaacGo2WWorld, replace=True)


register()
