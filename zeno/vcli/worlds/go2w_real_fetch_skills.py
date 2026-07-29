# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real fetch_and_place — the first END-TO-END COMPOSITE skill (report P5).

A composite skill = an ORDERED STAGE CHAIN, executed by a small, explicit stage
executor (NOT a general graph engine — report P5 says "一个清晰的阶段执行器即可,
不需要通用图引擎"). The chain is:

    bringup-check → goto_place(target_place) → approach(target)
                  → [GATED] grasp → goto_place(basket) → [GATED] place

Each stage has: a PRECONDITION (checked before it runs), an ENTRY condition
(the prior stage succeeded), FAIL-STOP semantics (the first failing stage halts
the chain and the skill reports HONESTLY which stage failed and why, with the
sub-skill's own recovery hint), and a per-stage VERIFY predicate reused from the
existing oracles (never invented here).

INV-1 (the moat). This skill is a PRODUCER: it composes existing skills and
returns an ExecutionTrace-shaped SkillResult. It NEVER computes ``verified`` and
NEVER invents a predicate. Every stage's verify hint is an EXISTING oracle:
navigation stages reuse the odometry ``at(...)`` hint returned by goto_place;
the approach stage reuses ``approach_ready()`` (the FSM's own phase latch). The
composite's aggregate ``verify_hint`` is the CONJUNCTION of the end-state-true
stage predicates (final position ``at(basket)`` AND the ``approach_ready()``
latch) — the honesty spine grades it; this skill only proposes the expression.

THE ARM RED LINE (absolute). grasp / place actuate the manipulator, so they are
DOUBLE-fenced:
  1. an explicit GATE — ``ZENO_ARM_ENABLE=1`` in the environment, DEFAULT OFF.
     With the gate off the two arm stages are SKIPPED (honestly reported as
     "arm disabled"); the base half (navigate + approach + drive to basket)
     still runs and still verifies.
  2. even WITH the gate on, these stages take a DRY-RUN / PLAN-ONLY path:
     validate params, log the plan, return it. They NEVER import piper/can,
     NEVER touch CAN, NEVER call an executor. There is no arm-actuation code
     path in this file at all — the gate only flips "skip" ↔ "plan+log".

DRY-RUN (whole chain). ``dry_run=True`` (or 演练/预演/dry-run in the utterance)
runs the chain as a REHEARSAL: it resolves the plan and checks preconditions but
issues NO navigation goal and NO manip task — no sub-skill ``execute`` is called,
so ZERO ROS publishes happen. It returns the plan for the operator to inspect
(``zeno -p "去厨房拿水瓶(演练)"``). A rehearsal makes no physical claim, so its
``verify_hint`` is the trivially-true ``"True"`` (nothing physical to prove).

New file, minimal blast radius: registered at the skills extension marker in
``go2w_real.py``; the sub-skills (goto_place / approach_object) are injectable so
the stage executor is hermetically testable without ROS.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from zeno.core.skill import skill
from zeno.core.types import SkillResult
from zeno.vcli.worlds.go2w_real_diag import oplog
from zeno.vcli.worlds.go2w_real_manip_skills import RealApproachObjectSkill
from zeno.vcli.worlds.go2w_real_places import RealGotoPlaceSkill
from zeno.vcli.worlds.go2w_real_skills import _base_of

#: Environment gate for the arm stages. "1" ARMS them (still plan-only). Anything
#: else (unset / "0" / "") keeps grasp+place SKIPPED — the shipped default.
ARM_ENABLE_ENV: str = "ZENO_ARM_ENABLE"

#: Utterance markers that mean "rehearse, do not move" (dry-run the whole chain).
_DRY_RUN_WORDS: frozenset[str] = frozenset(
    {"演练", "预演", "彩排", "模拟", "空跑", "dry-run", "dry run", "dryrun",
     "rehearse", "rehearsal"})


def arm_enabled() -> bool:
    """True iff the arm gate is explicitly armed (``ZENO_ARM_ENABLE=1``)."""
    return os.environ.get(ARM_ENABLE_ENV, "").strip() == "1"


@dataclass(frozen=True)
class FetchPlaceConfig:
    """Immutable defaults for the composite (additive-only, Inv-7)."""

    default_basket: str = "篮子"   # named place the operator can override
    precise_docking: bool = True   # manipulation-grade base pose at each place


CFG = FetchPlaceConfig()


@dataclass
class _StageOutcome:
    """One stage's result inside the chain (producer-side bookkeeping only)."""

    key: str
    title: str
    status: str                      # planned | ok | skipped | failed
    detail: str = ""
    verify_hint: str = ""            # an EXISTING oracle expression, or ""
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {"stage": self.key, "title": self.title, "status": self.status}
        if self.detail:
            d["detail"] = self.detail
        if self.verify_hint:
            d["verify_hint"] = self.verify_hint
        return d


def _truthy(*sources: Any, key: str) -> bool:
    for src in sources:
        if isinstance(src, dict) and key in src:
            return bool(src[key])
    return False


def _str_param(*sources: Any, key: str, default: str = "") -> str:
    for src in sources:
        if isinstance(src, dict) and src.get(key):
            return str(src[key]).strip()
    return default


@skill(aliases=["fetch_and_place", "取放", "取物放置", "拿取放置",
                "取回并放置", "fetch and place"],
       direct=True, uses=["base"])
class RealFetchAndPlaceSkill:
    """Composite: navigate → approach → [gated] grasp → drive to basket → [gated] place.

    A single skill call runs the whole chain through an explicit stage executor
    (fail-stop, honest per-stage reporting). The two arm stages are gated OFF by
    default and plan-only even when armed — the manipulator never moves from here.
    ``dry_run`` rehearses the plan with zero ROS publishes.
    """

    name = "fetch_and_place"
    description = (
        "端到端复合技能:导航到目标地点 → 视觉伺服靠近目标物 → [需显式开启手臂] "
        "抓取 → 导航到篮子 → [需显式开启手臂] 放入。一个技能调用跑完整条阶段链,"
        "失败即停并诚实汇报卡在哪一阶段、为什么。手臂阶段默认关闭(需环境变量 "
        "ZENO_ARM_ENABLE=1),且即便开启也只做 dry-run 规划(绝不触碰 CAN/piper/"
        "手臂)。dry_run=True(或说“演练/预演”)只演练计划、不发任何导航目标或 "
        "manip 任务(零 ROS 发布)。每阶段用既有 oracle 验收(导航=at();靠近="
        "approach_ready()),整体 verdict 聚合各阶段,本技能从不自评 verified。"
        "参数:target=要取的物体;target_place=去哪里找(命名地点,可选);"
        "basket=放到哪个命名地点(默认“篮子”)。需先 manip_bringup(action='start')。"
        "去<地点>拿<物体>放到<篮子>。")
    parameters = {
        "target": {"type": "string", "required": True,
                   "description": "要取的物体(按真实外观描述,如 '水瓶'/'metal bowl')"},
        "target_place": {"type": "string", "default": "", "required": False,
                         "description": "先导航到的命名地点(如 '公司厨房');"
                                        "留空则从当前位置直接搜索靠近"},
        "basket": {"type": "string", "default": "", "required": False,
                   "description": f"放置的命名地点(默认 '{CFG.default_basket}')"},
        "dry_run": {"type": "boolean", "default": False, "required": False,
                    "description": "只演练计划、不发任何导航/manip 指令(零 ROS 发布)"},
    }
    preconditions: list = []
    # base_state marks it a MOTOR skill (real-hw confirmation + capability {"base"});
    # NO arm keyword here on purpose — the arm stages are gated/plan-only, so the
    # wrapper must NOT withhold the whole skill as an arm skill.
    effects = {"base_state": "moved"}
    # verify_hint is per-call (composed from the stages) — this class default is the
    # safe fallback the schema advertises.
    verify_hint = "at(x, y, tol=1.0)"

    def __init__(self, goto: Any = None, approach: Any = None) -> None:
        # Injectable sub-skills so the stage executor is hermetically testable
        # (fakes record calls / script SkillResults) without a ROS env.
        self._goto = goto if goto is not None else RealGotoPlaceSkill()
        self._approach = approach if approach is not None else RealApproachObjectSkill()

    # -- param parsing -------------------------------------------------------

    def _parse(self, params: Any, kw: dict) -> dict[str, Any]:
        src = params if isinstance(params, dict) else {}
        target = _str_param(src, kw, key="target")
        target_place = _str_param(src, kw, key="target_place")
        basket = _str_param(src, kw, key="basket", default=CFG.default_basket)
        dry_run = _truthy(src, kw, key="dry_run")
        # Utterance fallback for the rehearsal verb (演练) when routed by alias.
        text = str(src.get("_text", "") or kw.get("_text", "") or "")
        if not dry_run and any(w in text.lower() for w in _DRY_RUN_WORDS):
            dry_run = True
        return {"target": target, "target_place": target_place,
                "basket": basket, "dry_run": dry_run}

    def _build_plan(self, p: dict[str, Any]) -> list[_StageOutcome]:
        """The ordered stage plan (status='planned'); pure, no side effects."""
        stages: list[_StageOutcome] = [
            _StageOutcome("bringup_check", "bringup 检查(感知+FSM 就绪)", "planned"),
        ]
        if p["target_place"]:
            stages.append(_StageOutcome(
                "goto_target", f"导航到「{p['target_place']}」", "planned"))
        stages.append(_StageOutcome(
            "approach", f"视觉伺服靠近「{p['target']}」", "planned"))
        stages.append(_StageOutcome(
            "grasp", f"抓取「{p['target']}」(手臂阶段)", "planned"))
        stages.append(_StageOutcome(
            "goto_basket", f"导航到篮子「{p['basket']}」", "planned"))
        stages.append(_StageOutcome(
            "place", f"放入「{p['basket']}」(手臂阶段)", "planned"))
        return stages

    # -- entry ---------------------------------------------------------------

    def execute(self, params=None, context=None, **kw) -> SkillResult:
        p = self._parse(params, kw)
        if not p["target"]:
            return SkillResult(success=False, diagnosis_code="bad_params",
                               error_message="fetch_and_place 需要 target(要取的物体)")
        plan = self._build_plan(p)
        armed = arm_enabled()
        oplog("skill", "fetch_and_place",
              f"target={p['target']!r} place={p['target_place']!r} "
              f"basket={p['basket']!r} dry_run={p['dry_run']} armed={armed}")

        if p["dry_run"]:
            return self._rehearse(p, plan, armed)
        return self._run(p, plan, armed, context)

    # -- dry-run rehearsal (zero ROS publishes) ------------------------------

    def _rehearse(self, p: dict[str, Any], plan: list[_StageOutcome],
                  armed: bool) -> SkillResult:
        """Resolve the plan WITHOUT executing any stage — no sub-skill call."""
        for st in plan:
            if st.key in ("grasp", "place"):
                st.status = "planned(arm-gated)" if armed else "would-skip(arm off)"
            else:
                st.status = "would-run"
        steps = "; ".join(f"{i+1}.{st.title}[{st.status}]"
                          for i, st in enumerate(plan))
        oplog("skill", "fetch_and_place", f"DRY-RUN plan: {steps}")
        arm_note = ("手臂已开启(仍仅 dry-run 规划,不触碰 CAN)"
                    if armed else "手臂默认关闭(抓取/放置会跳过)")
        msg = (f"[演练] fetch_and_place 计划(未发任何指令,零 ROS 发布):{steps}。"
               f"{arm_note}。去掉“演练”并确保 manip_bringup(action='start')后真正执行。")
        return SkillResult(success=True, result_data={
            "dry_run": True,
            "arm_enabled": armed,
            "target": p["target"], "target_place": p["target_place"],
            "basket": p["basket"],
            "stages": [st.to_dict() for st in plan],
            # A rehearsal makes NO physical claim — nothing to prove (Inv-1 safe).
            "verify_hint": "True",
            "message": msg})

    # -- real execution (fail-stop stage chain) ------------------------------

    def _run(self, p: dict[str, Any], plan: list[_StageOutcome], armed: bool,
             context: Any) -> SkillResult:
        base = _base_of(context)
        done: list[_StageOutcome] = []
        verify_terms: list[str] = []

        for st in plan:
            if st.key == "bringup_check":
                ok, why = self._check_bringup(base, context)
                if not ok:
                    return self._halt(st, done, why, "no_manip_stack",
                                      "manip_bringup(action='start')")
                st.status = "ok"
                st.detail = "感知+FSM seam 可达"

            elif st.key == "goto_target":
                res = self._goto.execute(
                    {"name": p["target_place"], "precise": CFG.precise_docking},
                    context)
                if not res.success:
                    return self._halt(st, done, res.error_message,
                                      res.diagnosis_code or "goto_failed",
                                      "list_places / goto_place")
                hint = str(res.result_data.get("verify_hint", "") or "")
                st.status, st.detail, st.verify_hint = "ok", "已到目标地点", hint
                st.data = dict(res.result_data)

            elif st.key == "approach":
                res = self._approach.execute({"target": p["target"]}, context)
                if not res.success:
                    return self._halt(st, done, res.error_message,
                                      res.diagnosis_code or "approach_failed",
                                      "manip_status() / manip_bringup(start_base)")
                st.status = "ok"
                st.detail = "已到 servo→grasp 交接距离(手臂未参与)"
                st.verify_hint = "approach_ready()"
                verify_terms.append("approach_ready()")
                st.data = dict(res.result_data)

            elif st.key in ("grasp", "place"):
                self._plan_arm_stage(st, p, armed)

            elif st.key == "goto_basket":
                res = self._goto.execute(
                    {"name": p["basket"], "precise": CFG.precise_docking},
                    context)
                if not res.success:
                    return self._halt(st, done, res.error_message,
                                      res.diagnosis_code or "goto_failed",
                                      "list_places / goto_place")
                hint = str(res.result_data.get("verify_hint", "") or "")
                st.status, st.detail, st.verify_hint = "ok", "已到篮子旁", hint
                st.data = dict(res.result_data)
                if hint:
                    verify_terms.append(hint)

            done.append(st)

        # Aggregate verdict = conjunction of the END-STATE-true stage predicates
        # (the honesty spine grades it; this producer only proposes it — Inv-1).
        aggregate = " and ".join(verify_terms) if verify_terms else "True"
        steps = "; ".join(f"{st.title}[{st.status}]" for st in done)
        arm_txt = ("手臂开启:抓取/放置已 dry-run 规划(未触碰 CAN)"
                   if armed else "手臂关闭:抓取/放置已跳过")
        msg = (f"fetch_and_place 完成阶段链:{steps}。{arm_txt}。"
               f"用 verify: {aggregate} 验收整体成果。")
        oplog("skill", "fetch_and_place", f"chain complete; verify={aggregate}")
        return SkillResult(success=True, result_data={
            "dry_run": False,
            "arm_enabled": armed,
            "target": p["target"], "basket": p["basket"],
            "stages": [st.to_dict() for st in done],
            "verify_hint": aggregate,
            "message": msg})

    # -- stage helpers -------------------------------------------------------

    @staticmethod
    def _check_bringup(base: Any, context: Any) -> tuple[bool, str]:
        """Read-only precondition: the manip seam is reachable (no motion)."""
        if base is None:
            return False, "无 Go2W 底盘(先 go2w_real_bringup(action='start'))"
        from zeno.vcli.worlds.go2w_real_manip_skills import _manip_of
        bridge = _manip_of(context)
        if bridge is None:
            return False, ("manip 桥不可达 — 任务图未起。先 "
                           "manip_bringup(action='start') 起感知+FSM(零运动)。")
        if not getattr(bridge, "is_connected", False):
            try:
                bridge.connect()
            except Exception:  # noqa: BLE001 — connect is best-effort
                pass
        if not getattr(bridge, "is_connected", False):
            return False, ("manip 桥未连接 — 先 manip_bringup(action='start') "
                           "并确认 manip_status() 有相位。")
        return True, ""

    @staticmethod
    def _plan_arm_stage(st: _StageOutcome, p: dict[str, Any],
                        armed: bool) -> None:
        """Arm stage: SKIP (gate off) or DRY-RUN PLAN (gate on). NEVER actuates.

        This function has NO import of piper/can and NO executor call — the arm
        red line is structural, not merely a runtime check. With the gate on it
        only validates params + logs the intended plan.
        """
        if not armed:
            st.status = "skipped"
            st.detail = (f"手臂默认关闭({ARM_ENABLE_ENV}!=1)——"
                         f"{'抓取' if st.key == 'grasp' else '放置'}未执行")
            oplog("skill", "fetch_and_place",
                  f"{st.key} SKIPPED (arm gate off)")
            return
        # Gate ARMED — still dry-run only: validate + log the plan, touch nothing.
        tgt = p["target"] if st.key == "grasp" else p["basket"]
        st.status = "planned(dry-run)"
        st.detail = (f"手臂已开启,但本阶段仅 dry-run 规划(校验目标={tgt!r},"
                     f"不触碰 CAN/piper)")
        oplog("skill", "fetch_and_place",
              f"{st.key} DRY-RUN plan target={tgt!r} (NO CAN/piper)")

    @staticmethod
    def _halt(st: _StageOutcome, done: list[_StageOutcome], why: str,
              diag: str, recovery: str) -> SkillResult:
        """Fail-stop: mark the stage failed, report which one and why, honestly."""
        st.status = "failed"
        st.detail = why
        oplog("skill", "fetch_and_place",
              f"HALT at stage={st.key}: {diag} — {why}")
        msg = (f"fetch_and_place 在阶段「{st.title}」失败:{why}"
               f"(诊断 {diag})。之前阶段:"
               + ("、".join(f"{d.title}[{d.status}]" for d in done) or "无")
               + f"。恢复建议:{recovery}。修复后可重跑(前序已完成阶段无需重复)。")
        return SkillResult(
            success=False, diagnosis_code=diag,
            result_data={
                "failed_stage": st.key,
                "stages": [d.to_dict() for d in done] + [st.to_dict()],
                "recovery": recovery,
                # No aggregate verify on failure — the chain did not reach its
                # end state; the honesty spine has nothing to grade True here.
                "verify_hint": "False",
                "message": msg},
            error_message=msg)
