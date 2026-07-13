# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P2 — unified turn footer + single-meaning evidence marks on step lines.

docs/CLI_UX_REDESIGN.md §4 P2:
- ONE footer grammar for every turn path: ``route=<r> · model=<m> ·
  in=<i> out=<o> tok · <wall>`` — unknown parts are OMITTED (never a
  fabricated 0.0s / in=0 placeholder for unmeasured values).
- The native step line's mark becomes evidence-based (one meaning per glyph):
  ✓ = GROUNDED, ○ = RAN with a passing check, ✗ = the check read false.
  The pinned substrings (`→ verify <expr>`, `(actor=…)`, the verdict line)
  are untouched — only the mark glyph carries the new single meaning.
- Measured step durations surface on the step line; unmeasured ones stay
  silent (never 0.0s).
"""
from __future__ import annotations

from zeno.vcli import cli
from zeno.vcli.turn_render import render_turn_footer

from tests.vcli.test_repl_native_cutover import (
    _FakeConsole,
    _FakeSession,
    _acted_trace,
    _stub_oracle,
)
from tests.vcli.test_chain_view_repl import _EventFakeEngine


# ---------------------------------------------------------------------------
# render_turn_footer — pure
# ---------------------------------------------------------------------------


def test_footer_full() -> None:
    line = render_turn_footer(
        route="native", model="deepseek-v4-pro", in_tokens=8214, out_tokens=612, wall_sec=14.2
    )
    assert "route=native" in line
    assert "deepseek-v4-pro" in line
    assert "in=8,214" in line and "out=612" in line
    assert "14.2s" in line


def test_footer_omits_unknowns() -> None:
    line = render_turn_footer(route="native", model="", in_tokens=0, out_tokens=0, wall_sec=0.0)
    assert "route=native" in line
    assert "in=" not in line
    assert "model=" not in line
    assert "0.0s" not in line


def test_footer_never_fabricates_zero_seconds() -> None:
    line = render_turn_footer(route="vgg", model="m", in_tokens=1, out_tokens=1, wall_sec=-1.0)
    assert "0.0s" not in line and "-1" not in line


# ---------------------------------------------------------------------------
# native wiring — footer after the verdict card
# ---------------------------------------------------------------------------


def test_native_footer_uses_finish_event_data(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True
    )
    engine = _EventFakeEngine(trace)  # emits finish {wall 1.0, in 10, out 5}
    console = _FakeConsole()
    app_state: dict = {"model": "deepseek-v4-pro"}

    assert cli._repl_attempt_native(engine, "走到坐标", _FakeSession(), app_state, console)
    assert "route=native" in console.text
    assert "deepseek-v4-pro" in console.text
    assert "in=10" in console.text and "out=5" in console.text


# ---------------------------------------------------------------------------
# native step-line marks — single meaning per glyph
# ---------------------------------------------------------------------------


def test_grounded_step_gets_check_mark(monkeypatch) -> None:
    _stub_oracle(monkeypatch)  # at_position IS a served oracle here
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True
    )
    console = _FakeConsole()
    assert cli._repl_attempt_native(
        _EventFakeEngine(trace), "走到坐标", _FakeSession(), {}, console
    )
    step_line = next(l for l in console.lines if "→ verify" in l)
    assert "✓" in step_line


def test_ran_passing_step_gets_circle_not_check(monkeypatch) -> None:
    _stub_oracle(monkeypatch)  # stack_ready NOT in the served oracle set
    trace = _acted_trace(
        "g", strategy="standup", verify="stack_ready()", verified_pose=True
    )
    console = _FakeConsole()
    assert cli._repl_attempt_native(
        _EventFakeEngine(trace), "站起来", _FakeSession(), {}, console
    )
    step_line = next(l for l in console.lines if "→ verify" in l)
    assert "○" in step_line
    assert "✓" not in step_line  # the check glyph is reserved for GROUNDED


def test_false_check_gets_cross(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=False
    )
    console = _FakeConsole()
    assert cli._repl_attempt_native(
        _EventFakeEngine(trace), "走到坐标", _FakeSession(), {}, console
    )
    step_line = next(l for l in console.lines if "→ verify" in l)
    assert "✗" in step_line


def test_pinned_substrings_survive_mark_change(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True
    )
    console = _FakeConsole()
    assert cli._repl_attempt_native(
        _EventFakeEngine(trace), "走到坐标", _FakeSession(), {}, console
    )
    assert "verify at_position(11.0, 3.0)" in console.text
    assert "actor=" in console.text
    assert "verified=True" in console.text
    assert "grounded)" in console.text
