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

from collections import deque
from contextlib import contextmanager
from typing import Any, Callable, Iterator

_TEAL = "#00b4b4"  # display-only brand constant (mirrors cli.TEAL)

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


def render_turn_footer(
    *,
    route: str,
    model: str = "",
    in_tokens: int = 0,
    out_tokens: int = 0,
    wall_sec: float = 0.0,
) -> str:
    """ONE footer grammar for every turn path (P2).

    ``route=<r> · model=<m> · in=<i> out=<o> tok · <wall>`` — every unknown
    part is OMITTED. Honest by construction: an unmeasured wall clock or a
    zero token count never renders as a fabricated placeholder.
    """
    parts: list[str] = []
    if route:
        parts.append(f"route={route}")
    if model:
        parts.append(f"model={_escape_markup(model)}")
    if in_tokens or out_tokens:
        parts.append(f"in={int(in_tokens):,} out={int(out_tokens):,} tok")
    dur = fmt_duration(wall_sec)
    if dur != "—":
        parts.append(dur)
    return "  [dim]" + " · ".join(parts) + "[/]"


def render_trace_detail(trace: Any) -> list[str]:
    """Full-detail view of ONE stored ExecutionTrace (P1.5 /trace replay).

    Pure projection of what the trace RECORDS: per-step strategy, verify expr,
    PASS/FAIL (the stored verify_result), honest duration, actor annotation,
    failure_class/diagnosis, result_data extras, validation notes. It NEVER
    re-derives evidence/verified — that requires the live oracle namespace and
    belongs to turn-time classification (the verdict line + card).
    """
    lines: list[str] = []
    goal = str(getattr(getattr(trace, "goal_tree", None), "goal", "") or "")
    lines.append(f"  [bold]Goal:[/] {_escape_markup(goal)}")
    sub_by_name = {
        sg.name: sg for sg in getattr(getattr(trace, "goal_tree", None), "sub_goals", ()) or ()
    }
    for i, s in enumerate(getattr(trace, "steps", ()) or (), 1):
        sg = sub_by_name.get(getattr(s, "sub_goal_name", ""))
        verify = _escape_markup(getattr(sg, "verify", "") or "") if sg else ""
        ok = bool(getattr(s, "verify_result", False))
        word = "[green]PASS[/]" if ok else "[red]FAIL[/]"
        strategy = _escape_markup((getattr(s, "strategy", "") or "").strip() or "(观察)")
        actor = getattr(getattr(s, "actor_caused", None), "value", "—")
        dur = fmt_duration(getattr(s, "duration_sec", 0.0))
        line = (
            f"  [dim]{i}[/]  {strategy}  [dim]verify[/] {verify} {word} "
            f"[dim]actor={actor} · {dur}[/]"
        )
        fc = (getattr(s, "failure_class", "") or "").strip()
        if fc:
            line += f" [red]{_escape_markup(fc)}[/]"
        err = (getattr(s, "error", "") or "").strip()
        if err:
            line += f" [dim]{_escape_markup(err[:60])}[/]"
        lines.append(line)
        rd = getattr(s, "result_data", None)
        if isinstance(rd, dict):
            extras = {
                k: v for k, v in rd.items() if k != "output" and v not in ("", None, {})
            }
            if extras:
                pairs = ", ".join(f"{k}={str(v)[:24]}" for k, v in list(extras.items())[:4])
                lines.append(f"       [dim]{_escape_markup(pairs)}[/]")
    notes = getattr(getattr(trace, "goal_tree", None), "validation_notes", ()) or ()
    for note in notes:
        lines.append(f"  [yellow]ⓘ[/] [dim]{_escape_markup(str(note))}[/]")
    n = len(getattr(trace, "steps", ()) or ())
    outcome = "[green]ok[/]" if bool(getattr(trace, "success", False)) else "[red]not ok[/]"
    total = fmt_duration(getattr(trace, "total_duration_sec", 0.0))
    lines.append(f"  [dim]Outcome:[/] {outcome} [dim]· {n} steps · total {total}[/]")
    return lines


# ---------------------------------------------------------------------------
# ChainView — the live execution-chain tree for the native REPL turn (P1.1)
# ---------------------------------------------------------------------------


def _escape_markup(text: str) -> str:
    """Escape Rich markup brackets in model-authored text (display safety)."""
    return str(text).replace("[", r"\[")


class ChainView:
    """Single live region rendering the native turn's execution chain.

    Consumes ``NativeEvent``s (zeno.vcli.turn_events) and renders a live tree:
    header (keeps the PTY-pinned words "native working") → dim ┆ reasoning
    tail → chain nodes (● tool / └─ verify ✓|✗) → ⟲ nudges → narration tail.

    Lifecycle discipline is TurnStatus's (one region per turn, idempotent
    start/stop, ``paused()`` around foreign prints — see turn_status.py for
    WHY: printing into an active Live stacks box frames). ``live_factory`` is
    injected so lifecycle + content are unit-testable without a TTY.

    Display-only: the full reasoning buffer is exposed for /why but NEVER
    written to the session or the trace.
    """

    def __init__(
        self,
        live_factory: Callable[[Any], Any] | None = None,
        *,
        reasoning_tail_chars: int = 160,
        max_nudges: int = 3,
        show_reasoning_tail: bool = True,
    ) -> None:
        self._live_factory = live_factory
        self._live: Any = None
        self._running = False
        self.start_count = 0
        self.stop_count = 0

        self._round = ""
        self._nodes: list[dict[str, Any]] = []
        self._reasoning: list[str] = []
        self._reasoning_tail_chars = int(reasoning_tail_chars)
        self._show_reasoning_tail = bool(show_reasoning_tail)
        self._nudges: deque[str] = deque(maxlen=max(1, int(max_nudges)))
        self._text_tail = ""
        self.finish_data: dict[str, Any] = {}

    # -- lifecycle ------------------------------------------------------

    @property
    def running(self) -> bool:
        return self._running

    @property
    def reasoning_text(self) -> str:
        """The FULL reasoning buffer of this turn (for /why). Display-only."""
        return "".join(self._reasoning)

    def start(self) -> None:
        if self._running or self._live_factory is None:
            return
        # Display is best-effort: a console that cannot host a live region
        # (e.g. a non-rich test double, a dumb pipe) degrades to NO live view —
        # events still accumulate and every post-turn line prints as normal.
        try:
            self._live = self._live_factory(self._renderable())
            self._live.start()
        except Exception:  # noqa: BLE001
            self._live = None
            return
        self._running = True
        self.start_count += 1

    def stop(self) -> None:
        if not self._running:
            return
        live = self._live
        self._live = None
        self._running = False
        self.stop_count += 1
        if live is not None:
            live.stop()

    def pause(self) -> bool:
        if not self._running:
            return False
        self.stop()
        return True

    def resume(self) -> None:
        self.start()

    @contextmanager
    def paused(self) -> Iterator[None]:
        was_running = self.pause()
        try:
            yield
        finally:
            if was_running:
                self.resume()

    # -- event intake ---------------------------------------------------

    def handle_event(self, event: Any) -> None:
        """Consume one NativeEvent; never raises (display is best-effort)."""
        try:
            self._consume(event)
        except Exception:  # noqa: BLE001 — a display bug must never leak upward
            return
        if self._running and self._live is not None:
            try:
                self._live.update(self._renderable())
            except Exception:  # noqa: BLE001
                pass

    def _consume(self, event: Any) -> None:
        kind = getattr(event, "kind", None)
        if not kind:
            return
        label = str(getattr(event, "label", "") or "")
        detail = str(getattr(event, "detail", "") or "")
        ok = getattr(event, "ok", None)
        if kind == "round":
            self._round = label
        elif kind == "reasoning":
            self._reasoning.append(detail)
        elif kind == "text":
            self._text_tail = (self._text_tail + detail)[-72:]
        elif kind == "tool_start":
            self._nodes.append({"kind": "tool", "label": label, "detail": detail, "ok": None})
        elif kind == "tool_end":
            for node in reversed(self._nodes):
                if node["kind"] == "tool" and node["label"] == label and node["ok"] is None:
                    node["ok"] = bool(ok)
                    node["err"] = detail if ok is False else ""
                    break
        elif kind == "verify":
            self._nodes.append({"kind": "verify", "label": label, "detail": detail, "ok": ok})
        elif kind == "nudge":
            self._nudges.append(detail or label)
        elif kind == "interject":
            self._nudges.append("操作员插队 — 取消剩余步骤")
        elif kind == "finish":
            self.finish_data = dict(getattr(event, "data", None) or {})

    # -- rendering ------------------------------------------------------

    def render_lines(self) -> list[str]:
        """Pure projection of the consumed events into Rich-markup lines."""
        round_part = f" [dim]round {self._round}[/]" if self._round else ""
        lines = [
            f"  [bold {_TEAL}]native[/] working…{round_part}  [dim](Ctrl+C 安全中断)[/dim]"
        ]
        if self._show_reasoning_tail and self._reasoning:
            joined = "".join(self._reasoning).replace("\n", " ")
            tail = joined[-self._reasoning_tail_chars :].strip()
            if tail:
                lines.append(f"  [dim italic]┆ {_escape_markup(tail)}[/]")
        for node in self._nodes:
            label = _escape_markup(node.get("label", ""))
            if node["kind"] == "tool":
                detail = _escape_markup(node.get("detail", ""))
                ok = node.get("ok")
                if ok is None:
                    mark = f"[{_TEAL}]●[/]"
                elif ok:
                    mark = "[green]●[/]"
                else:
                    mark = "[red]●[/]"
                err = node.get("err") or ""
                err_part = f"  [red]{_escape_markup(err)}[/]" if err else ""
                lines.append(f"  {mark} {label}{detail}{err_part}")
            else:  # verify
                ok = node.get("ok")
                if ok is None:
                    mark = "[yellow]rejected[/]"
                elif ok:
                    mark = "[green]✓[/]"
                else:
                    mark = "[red]✗[/]"
                lines.append(f"  [dim]└─ verify[/] {label} {mark}")
        for nudge in self._nudges:
            lines.append(f"  [yellow]⟲[/] {_escape_markup(nudge)}")
        if self._text_tail.strip():
            lines.append(f"  [dim]{_escape_markup(self._text_tail.strip())}[/]")
        return lines

    def _renderable(self) -> Any:
        try:
            from rich.text import Text

            return Text.from_markup("\n".join(self.render_lines()))
        except Exception:  # noqa: BLE001 — degrade to plain text, never crash
            import re

            plain = re.sub(r"\[[^\]]*\]", "", "\n".join(self.render_lines()))
            return plain
