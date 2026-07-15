# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P5 layer-0 — execution state machine + control-authority badge (display-only).

Owner ask (2026-07-14): 'CLI 能显示 behaviour tree / state machine'. Layer 0
renders the EXISTING implicit native ReAct execution as an explicit state-machine
view + a control-authority badge, derived purely from the NativeEvent stream and
the live_status line. It NEVER changes execution/verify — it just makes the
already-happening states visible. (Making them editable is layer 1, CEO-gated.)
"""
from __future__ import annotations

import pytest

from zeno.vcli.turn_render import (
    STATE_ACTING,
    STATE_DONE,
    STATE_IDLE,
    STATE_PLANNING,
    STATE_VERIFYING,
    STATE_YIELDED,
    derive_authority,
    derive_turn_state,
    spinner_frame,
    render_authority,
    render_state_machine,
)


# ---------------------------------------------------------------------------
# derive_turn_state — NativeEvent kind -> state
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind,expected", [
    ("round", STATE_PLANNING),
    ("reasoning", STATE_PLANNING),
    ("text", STATE_PLANNING),
    ("tool_start", STATE_ACTING),
    ("tool_end", STATE_ACTING),
    ("verify", STATE_VERIFYING),
    ("finish", STATE_DONE),
    ("interject", STATE_YIELDED),
])
def test_event_kind_maps_to_state(kind, expected) -> None:
    assert derive_turn_state(kind, STATE_IDLE) == expected


def test_nudge_is_recovering_branch() -> None:
    # A nudge is a recovery branch, not a main-line state.
    assert derive_turn_state("nudge", STATE_ACTING) == "RECOVERING"


def test_unknown_kind_keeps_prev_state() -> None:
    assert derive_turn_state("???", STATE_ACTING) == STATE_ACTING


# ---------------------------------------------------------------------------
# render_state_machine — main line with current highlighted
# ---------------------------------------------------------------------------


def test_state_machine_shows_current_stage_and_count() -> None:
    # Owner-chosen braille loading bar (2026-07-15): names the CURRENT stage + an
    # honest N/5 position in the fixed 5-phase machine (not all 5 labels, no
    # arrows). ACTING is the 3rd phase → 3/5.
    from rich.text import Text

    plain = Text.from_markup(render_state_machine(STATE_ACTING)).plain
    assert "执行" in plain          # current stage named
    assert "3/5" in plain           # honest position in the known 5-phase machine
    assert "⣿" in plain and "⣀" in plain  # braille loading bar: filled + empty cells


def test_state_machine_bar_fills_as_stage_advances() -> None:
    from rich.text import Text

    acting = Text.from_markup(render_state_machine(STATE_ACTING)).plain
    verifying = Text.from_markup(render_state_machine(STATE_VERIFYING)).plain
    assert acting != verifying                       # bar/label/count advance
    assert "执行" in acting and "验证" in verifying
    assert verifying.count("⣿") > acting.count("⣿")  # more filled at the later stage


def test_state_machine_branch_state_annotated() -> None:
    from rich.text import Text

    plain = Text.from_markup(render_state_machine("RECOVERING")).plain
    assert "恢复" in plain


def test_state_machine_terminal_is_fully_filled() -> None:
    from rich.text import Text

    done = Text.from_markup(render_state_machine(STATE_DONE)).plain
    assert "完成" in done and "5/5" in done
    assert "⣿" in done and "⣀" not in done  # terminal: the whole bar is filled


def test_state_machine_branch_freezes_at_reached_rank() -> None:
    """A branch (恢复/让位) is OFF the main line, so it FREEZES the fill/count at
    the last real stage reached — it must never fake-advance toward 完成; the
    amber ⑂ tag hangs on the right."""
    from rich.text import Text

    # reached VERIFYING(rank 3) then branched to RECOVERING
    plain = Text.from_markup(render_state_machine("RECOVERING", reached_rank=3)).plain
    assert "验证" in plain       # frozen at the last real stage
    assert "4/5" in plain        # count frozen — never fake-advances to 5/5
    assert "⣀" in plain          # bar not full (didn't reach 完成)
    assert "⑂ 恢复" in plain


# ---------------------------------------------------------------------------
# derive_authority + render — AGENT / OPERATOR / ESTOP
# ---------------------------------------------------------------------------


def test_authority_agent_by_default() -> None:
    icon, label, _style = derive_authority("pose x=1 y=2 · odom age 0.1s")
    assert label == "AGENT"


def test_authority_operator_when_rviz_manual_goal() -> None:
    icon, label, _style = derive_authority(
        "pose x=1 · odom age 0.0s · RViz手动目标 (2.80, 1.78) 0s前")
    assert label == "OPERATOR"


def test_authority_estop_wins() -> None:
    _i, label, _s = derive_authority("pose x=1 · 急停", estopped=True)
    assert label == "ESTOP"
    _i2, label2, _s2 = derive_authority("pose · estop latched")
    assert label2 == "ESTOP"


def test_render_authority_renders_only_the_fixed_label() -> None:
    from rich.text import Text

    # render_authority emits only the FIXED label (AGENT/OPERATOR/ESTOP), never
    # the raw live_status — so a spoofed status can inject NOTHING here.
    line = render_authority(derive_authority("pose [bold]x[/] · RViz手动目标 (0,0)"))
    plain = Text.from_markup(line).plain
    assert plain.strip() == "OPERATOR"  # text-only badge, no emoji/marker
    assert "[bold]" not in plain  # live_status text never reaches the badge


def test_spinner_frame_rotates_and_is_braille() -> None:
    from zeno.vcli.turn_render import _SPINNER_FRAMES

    frames = {spinner_frame(t / 10.0) for t in range(20)}
    assert len(frames) > 1  # it actually rotates over time
    assert frames <= set(_SPINNER_FRAMES)  # only braille spinner glyphs
    assert spinner_frame(float("nan")) in _SPINNER_FRAMES  # never raises
