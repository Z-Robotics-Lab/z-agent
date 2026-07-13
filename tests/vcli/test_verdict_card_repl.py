# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P1.3 wiring — the REPL native path renders the verdict card AFTER the pinned
verdict line (docs/CLI_UX_REDESIGN.md §4 P1.3).

Additive-only contract: every pre-existing pinned line survives byte-compatible
(`▸ {chain} → verify {expr} {mark} (actor=…)`, `verdict {EV} verified={bool}
(n/m grounded)` — acceptance tools sync on the `grounded)` tail), and the card
appends per-step evidence rows + explanations for non-GROUNDED steps. The card
is display-only and best-effort: a rendering error must never break the turn.
"""
from __future__ import annotations

from zeno.vcli import cli

from tests.vcli.test_repl_native_cutover import (
    _FakeConsole,
    _FakeEngine,
    _FakeSession,
    _acted_trace,
    _stub_oracle,
)


def test_card_renders_after_verdict_line_with_evidence(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True
    )
    engine = _FakeEngine(trace)
    console = _FakeConsole()

    acted = cli._repl_attempt_native(engine, "走到坐标 (11,3)", _FakeSession(), {}, console)

    assert acted is True
    # Pinned lines intact.
    assert "verify at_position(11.0, 3.0)" in console.text
    assert "verified=True" in console.text
    assert "grounded)" in console.text
    # Card rows: evidence class + actor surfaced per step.
    assert "GROUNDED" in console.text
    assert "CAUSED" in console.text
    # Order: the card row comes after the verdict line (append, never interleave).
    verdict_idx = next(i for i, l in enumerate(console.lines) if "verified=True" in l)
    card_idx = next(
        i for i, l in enumerate(console.lines) if "GROUNDED" in l and i > verdict_idx
    )
    assert card_idx > verdict_idx


def test_unverified_turn_card_explains_why(monkeypatch) -> None:
    # verified_pose=False -> the step's verify read False -> evidence RAN; the
    # card must carry an ⓘ explanation instead of leaving verified=False mute.
    _stub_oracle(monkeypatch)
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=False
    )
    engine = _FakeEngine(trace)
    console = _FakeConsole()

    acted = cli._repl_attempt_native(engine, "走到坐标 (11,3)", _FakeSession(), {}, console)

    assert acted is True
    assert "verified=False" in console.text  # pinned line intact
    assert "ⓘ" in console.text


def test_card_render_failure_never_breaks_the_turn(monkeypatch) -> None:
    _stub_oracle(monkeypatch)
    monkeypatch.setattr(
        cli, "render_verdict_card", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    trace = _acted_trace(
        "g", strategy="walk", verify="at_position(11.0, 3.0)", verified_pose=True
    )
    engine = _FakeEngine(trace)
    console = _FakeConsole()
    session = _FakeSession()

    acted = cli._repl_attempt_native(engine, "走到坐标 (11,3)", session, {}, console)

    assert acted is True
    assert "verified=True" in console.text  # verdict line still rendered
    assert session.user == ["走到坐标 (11,3)"]  # session record still appended
