# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""turn_render — display-only renderers for the REPL turn block.

P1.3 of the CLI UX redesign (docs/CLI_UX_REDESIGN.md): the verdict card that
unfolds ``VerdictReport.per_step`` (evidence class, actor annotation, honest
timing, diagnosis) plus a human explanation for every step that carries no
grounded evidence — so ``verified=False`` is never mute jargon.

HONESTY BY CONSTRUCTION (CLAUDE.md Inv-1 — verify is the moat):
- Everything here is a PURE PROJECTION of ``VerdictReport`` / ``ExecutionTrace``
  fields. This module NEVER calls the classifier, NEVER re-derives ``verified``,
  and never renders the word ``verified=`` (that belongs to the pinned verdict
  line in cli.py, which acceptance tools parse — see tools/acceptance/*).
- Explanations are a static lookup over the 2026-07-13 predicate-role-map
  semantics enumeration (docs/VERIFY.md "Grounding semantics"); they describe
  the classifier's decision, they never second-guess it.
- Honest timing (P1.4): an unmeasured duration (<= 0, e.g. a legacy trace)
  renders as an em dash — a fabricated "0.0s" is worse than nothing.

Output is a list of Rich-markup strings (the repo's dominant console idiom),
so the REPL prints them line by line and tests capture them as plain text.
"""
from __future__ import annotations

from typing import Any

# Evidence classes (mirrors zeno.vcli.verdict constants; strings on purpose —
# this module renders report fields verbatim and must not import spine logic).
_GROUNDED = "GROUNDED"
_RAN = "RAN"
_FAILED = "FAILED"

_EVIDENCE_COLOR = {_GROUNDED: "green", _RAN: "yellow", _FAILED: "red"}

# W2.4 typed failure classes -> short human diagnosis (informational only).
_DIAGNOSIS_HUMAN = {
    "timeout": "超时",
    "verify_fail": "验证失败",
    "ik_fail": "目标不可达(IK)",
    "tool_error": "工具错误",
    "exec_error": "执行错误",
}


def fmt_duration(sec: float) -> str:
    """Honest duration display: unmeasured -> em dash, tiny-but-real -> '<0.1s'."""
    try:
        sec = float(sec)
    except (TypeError, ValueError):
        return "—"
    if sec <= 0.0:
        return "—"
    if sec < 0.1:
        return "<0.1s"
    return f"{sec:.1f}s"


def explain_step(
    evidence: str,
    actor: str,
    verify_result: bool,
    strategy: str,
    diagnosis: str = "",
) -> str:
    """One honest sentence for a (evidence, actor, verify_result) combo.

    Static lookup over the reachable-combo enumeration (2026-07-13 grounding
    semantics). Display-only: describes what the classifier decided, never
    recomputes it. Always returns a non-empty string (fail-safe generic line
    for an unforeseen combo — an empty cell would read as "nothing to say").
    """
    acted = bool((strategy or "").strip())
    if evidence == _FAILED:
        diag = _DIAGNOSIS_HUMAN.get((diagnosis or "").strip(), (diagnosis or "").strip())
        return f"步骤执行失败{f'（{diag}）' if diag else ''}。"
    if evidence == _GROUNDED:
        if actor == "CAUSED":
            return "机器人下发了动作，世界真值确认目标达成——完全验证。"
        if actor == "UNCAUSED" and not acted:
            return "纯观察步：未下发动作，真值读数为真——按 grounded 观察计。"
        return "世界真值确认目标达成；该谓词类型不做因果评级，按目标状态真值通过。"
    # evidence == RAN (or anything unforeseen — fall through stays honest)
    if not verify_result:
        if actor == "CAUSED":
            return "机器人动了，但世界真值未确认目标（未达阈值或未到位）——不作为证据。"
        return "检查执行了但结果为假——目标状态未达成。"
    if actor == "UNCAUSED" and acted:
        return "谓词为真，但下发的动作并未导致该状态（基线已满足或非指令位移）——降级，不作为证据。"
    if actor == "CAUSED":
        return "动作执行且有检查通过，但检查的是落点而非指令目标（坐标不符）——不作为证据。"
    return "检查为真但不构成落地证据（谓词未注册为世界真值、状态量裸调、恒真式或仅视觉判定）——不计入 grounded。"


def _step_meta(trace: Any) -> dict[str, Any]:
    """Map sub_goal_name -> StepRecord for actor/duration lookup (best-effort)."""
    steps = getattr(trace, "steps", None) or ()
    out: dict[str, Any] = {}
    for s in steps:
        name = getattr(s, "sub_goal_name", None)
        if name:
            out[name] = s
    return out


def render_verdict_card(report: Any, trace: Any = None, *, max_verify_len: int = 36) -> list[str]:
    """Render ``VerdictReport.per_step`` as indented card rows + ⓘ explanations.

    Pure projection: evidence/verify_result come from the report verbatim;
    actor and duration come from the matching ``trace.steps`` records when a
    trace is available (they are not part of the ZENO_VERDICT schema), else
    degrade to em dashes. Returns [] when there is nothing to show.
    """
    per_step = tuple(getattr(report, "per_step", ()) or ())
    if not per_step:
        return []
    meta = _step_meta(trace) if trace is not None else {}

    lines: list[str] = []
    explanations: list[tuple[int, str]] = []
    for i, s in enumerate(per_step, 1):
        rec = meta.get(s.name)
        actor = getattr(getattr(rec, "actor_caused", None), "value", "—") if rec else "—"
        dur = fmt_duration(getattr(rec, "duration_sec", 0.0)) if rec else "—"
        color = _EVIDENCE_COLOR.get(s.evidence, "white")
        mark = "✓" if s.verify_result else "✗"
        mark_color = "green" if s.verify_result else "red"
        verify = (s.verify or "").strip() or "—"
        if len(verify) > max_verify_len:
            verify = verify[: max_verify_len - 1] + "…"
        action = (s.strategy or "").strip() or "(观察)"
        diag = (s.diagnosis or "").strip()
        diag_part = f" [dim]{diag}[/]" if diag else ""
        lines.append(
            f"    [dim]{i}[/]  {action}  [dim]verify[/] {verify} "
            f"[{mark_color}]{mark}[/]  [{color}]{s.evidence}[/] "
            f"[dim]actor={actor} · {dur}[/]{diag_part}"
        )
        if s.evidence != _GROUNDED:
            explanations.append(
                (i, explain_step(s.evidence, actor, bool(s.verify_result), s.strategy, diag))
            )

    for i, text in explanations:
        lines.append(f"    [yellow]ⓘ[/] [dim]第{i}步：{text}[/]")
    if not explanations and not bool(getattr(report, "verified", False)):
        # Every step grounded yet the turn is unverified: a turn-level gate
        # (e.g. STEP-15 coordinate gate / D17 object gate) rejected it. Explain
        # at the turn level; never second-guess the report.
        lines.append(
            "    [yellow]ⓘ[/] [dim]各步均有落地证据，但回合级门槛未通过"
            "（如坐标与指令目标不符/对象门槛）——以 verdict 行为准。[/]"
        )
    return lines
