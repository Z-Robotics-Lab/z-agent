# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""P1.1 ChainView — the live execution-chain tree for the native REPL turn.

Same discipline as TurnStatus (the module it replaces on the native path):
ONE live region per turn, idempotent start/stop, paused() around foreign
prints, injected live_factory so lifecycle is unit-testable without a TTY
(tests/unit/vcli/test_turn_status.py is the pattern).

Content contract (render_lines is a PURE projection of consumed events):
- the header keeps the PTY-pinned words "native" + "working" (the transient
  frames land in the raw transcript that tests/vcli/test_repl_native_cutover_pty.py
  scans);
- tool nodes render as quiet ◇ Tool entries with running/ok/fail states; a verify
  attaches to its chain node with ✓/✗;
- reasoning chunks render as a dim ┆ tail (bounded) and accumulate in full
  for the /why command (display buffer only — never the session);
- nudges surface as ⟲ lines (bounded);
- the finish event's payload is exposed for the turn footer.
"""
from __future__ import annotations

from zeno.vcli.turn_events import NativeEvent
from zeno.vcli.turn_render import ChainView


class StubLive:
    def __init__(self, renderable: object) -> None:
        self.renderable = renderable
        self.started = 0
        self.stopped = 0
        self.updates: list[object] = []

    def start(self, refresh: bool = True) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def update(self, renderable: object, refresh: bool = True) -> None:
        self.updates.append(renderable)


def _make(*, status_provider=None) -> tuple[ChainView, list[StubLive]]:  # noqa: ANN001
    lives: list[StubLive] = []

    def factory(renderable: object) -> StubLive:
        live = StubLive(renderable)
        lives.append(live)
        return live

    if status_provider is None:
        return ChainView(live_factory=factory), lives
    return ChainView(live_factory=factory, status_provider=status_provider), lives


def _text(view: ChainView) -> str:
    return "\n".join(view.render_lines())


# ---------------------------------------------------------------------------
# Lifecycle (TurnStatus discipline)
# ---------------------------------------------------------------------------


def test_one_region_per_turn_idempotent() -> None:
    view, lives = _make()
    view.start()
    view.start()
    assert len(lives) == 1 and lives[0].started == 1
    view.stop()
    view.stop()
    assert lives[0].stopped == 1


def test_paused_stops_then_restarts() -> None:
    view, lives = _make()
    view.start()
    with view.paused():
        assert lives[0].stopped == 1
    assert len(lives) == 2 and lives[1].started == 1
    view.stop()


def test_paused_noop_when_not_running() -> None:
    view, lives = _make()
    with view.paused():
        pass
    assert lives == []


# ---------------------------------------------------------------------------
# Content — pure projection of events
# ---------------------------------------------------------------------------


def test_header_keeps_pty_pinned_words() -> None:
    view, _ = _make()
    text = _text(view)
    assert "native" in text and "working" in text


def test_tool_and_verify_nodes_render_chain() -> None:
    view, _ = _make()
    view.handle_event(NativeEvent(kind="tool_start", label="turn", detail="(direction=left)"))
    assert "turn" in _text(view)
    view.handle_event(NativeEvent(kind="tool_end", label="turn", ok=True))
    view.handle_event(NativeEvent(kind="verify", label="turned(18)", ok=True))
    text = _text(view)
    assert "turned(18)" in text
    assert "✓" in text


def test_tool_nodes_use_the_quiet_activity_layer() -> None:
    # Owner-chosen 精简圆点 (2026-07-15): drop the ◇ Tool · furniture — a tool is
    # a status-colored ● node carrying just the skill name.
    from rich.text import Text

    view, _ = _make()
    view.handle_event(
        NativeEvent(kind="tool_start", label="turn", detail="(direction=left)")
    )
    running_plain = Text.from_markup(_text(view)).plain
    assert "●" in running_plain and "turn" in running_plain

    view.handle_event(NativeEvent(kind="tool_end", label="turn", ok=True))
    finished_plain = Text.from_markup(_text(view)).plain
    assert "●" in finished_plain and "✓" in finished_plain
    assert "Tool" not in finished_plain  # the old ◇ Tool · furniture is gone


def test_failed_verify_renders_cross() -> None:
    view, _ = _make()
    view.handle_event(NativeEvent(kind="tool_start", label="walk"))
    view.handle_event(NativeEvent(kind="tool_end", label="walk", ok=True))
    view.handle_event(NativeEvent(kind="verify", label="moved(2.0)", ok=False))
    assert "✗" in _text(view)


def test_reasoning_tail_bounded_and_full_buffer_kept() -> None:
    view, _ = _make()
    for i in range(50):
        view.handle_event(NativeEvent(kind="reasoning", detail=f"思考片段{i} "))
    text = _text(view)
    assert "┆" in text
    # Tail is bounded: early chunks fall out of the visible tail...
    assert "思考片段0" not in text
    assert "思考片段49" in text
    # ...but the FULL buffer is kept for /why.
    assert "思考片段0" in view.reasoning_text
    assert "思考片段49" in view.reasoning_text


def test_live_status_is_in_header_and_refreshes_each_round() -> None:
    """The operator sees the same live world truth the model plans from."""
    status = ["pose x=0.00 y=0.00 yaw=+0.0deg (+0.000rad) · odom age=0.1s"]
    view, _ = _make(status_provider=lambda: status[0])

    view.handle_event(NativeEvent(kind="round", label="1"))
    first = _text(view)
    assert "⌖" in first
    assert "x=0.00" in first and "odom age=0.1s" in first
    assert first.index("working") < first.index("⌖") < first.index("pose")

    status[0] = "pose x=2.00 y=0.00 yaw=+0.0deg (+0.000rad) · odom age=0.0s"
    view.handle_event(NativeEvent(kind="round", label="2"))
    second = _text(view)
    assert "x=2.00" in second and "x=0.00" not in second


def test_live_status_provider_failure_clears_stale_text() -> None:
    values = ["pose x=1.00", RuntimeError("driver read failed")]

    def provider() -> str:
        value = values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    view, _ = _make(status_provider=provider)
    view.handle_event(NativeEvent(kind="round", label="1"))
    assert "pose x=1.00" in _text(view)
    view.handle_event(NativeEvent(kind="round", label="2"))
    assert "pose x=1.00" not in _text(view)  # never leave stale pose on screen


def test_live_status_escapes_rich_markup() -> None:
    view, _ = _make(status_provider=lambda: "pose [bold red]spoof[/] x=0")
    view.handle_event(NativeEvent(kind="round", label="1"))

    from rich.text import Text

    rendered = Text.from_markup("\n".join(view.render_lines()))
    assert "[bold red]spoof[/]" in rendered.plain


def test_nudge_renders_and_is_bounded() -> None:
    view, _ = _make()
    for i in range(5):
        view.handle_event(NativeEvent(kind="nudge", label="verify_before_finish", detail=f"nudge{i}"))
    text = _text(view)
    assert "⟲" in text
    assert "nudge4" in text
    assert "nudge0" not in text  # bounded — only the recent ones


def test_finish_data_exposed_for_footer() -> None:
    view, _ = _make()
    view.handle_event(
        NativeEvent(kind="finish", data={"wall_sec": 14.2, "turns": 3, "in_tokens": 8214, "out_tokens": 612})
    )
    assert view.finish_data.get("wall_sec") == 14.2
    assert view.finish_data.get("in_tokens") == 8214


def test_events_update_live_region_in_place() -> None:
    view, lives = _make()
    view.start()
    view.handle_event(NativeEvent(kind="tool_start", label="walk"))
    view.handle_event(NativeEvent(kind="verify", label="moved(2.0)", ok=True))
    assert len(lives) == 1  # never a second region
    assert len(lives[0].updates) >= 2  # redrawn in place per event
    view.stop()


def test_malformed_event_never_raises() -> None:
    view, _ = _make()
    view.handle_event(NativeEvent(kind="???", label=None, detail=None))  # type: ignore[arg-type]
    view.handle_event(None)  # type: ignore[arg-type]
    assert isinstance(_text(view), str)


# ---------------------------------------------------------------------------
# P3.1 — final_lines: the PERSISTED execution tree (owner ask 2026-07-13)
# ---------------------------------------------------------------------------


def test_final_lines_tree_with_goal_rounds_and_chain() -> None:
    view, _ = _make()
    view.handle_event(NativeEvent(kind="round", label="1"))
    view.handle_event(NativeEvent(kind="tool_start", label="turn", detail="(direction=left)"))
    view.handle_event(NativeEvent(kind="tool_end", label="turn", ok=True))
    view.handle_event(NativeEvent(kind="round", label="2"))
    view.handle_event(NativeEvent(kind="verify", label="turned(18)", ok=True))
    view.handle_event(NativeEvent(kind="nudge", label="verify_before_finish", detail="先 verify 再停止"))
    lines = view.final_lines("往左转动30度")
    text = "\n".join(lines)
    assert "⌂" in text and "往左转动30度" in text  # goal header
    assert "2" in lines[0]  # rounds count on the header
    assert "turn" in text and "turned(18)" in text and "✓" in text
    assert "⟲" in text and "先 verify 再停止" in text  # nudges persist
    # No live-only furniture in the transcript tree:
    assert "working" not in text
    assert "┆" not in text  # reasoning stays live-region/-why only


def test_final_lines_empty_without_events() -> None:
    view, _ = _make()
    assert view.final_lines("g") == []


def test_tree_rails_nest_verify_under_its_tool() -> None:
    """DELTA 2 (2026-07-15): the flat chain becomes a rooted tree — a tool hangs
    off the ⌂ trunk on a ├─ elbow, and its verify nests one level UNDER it on a
    │  └─ rail, so the check visibly BELONGS to the tool instead of floating as a
    sibling at the same indent."""
    from rich.text import Text

    view, _ = _make()
    view.handle_event(NativeEvent(kind="tool_start", label="navigate", detail="(dest=home)"))
    view.handle_event(NativeEvent(kind="tool_end", label="navigate", ok=True))
    view.handle_event(NativeEvent(kind="verify", label="at_place('home')", ok=True))
    lines = view.render_lines()
    tool_line = next(l for l in lines if "●" in l and "navigate" in l)
    verify_line = next(l for l in lines if "verify" in l and "at_place" in l)
    assert Text.from_markup(tool_line).plain.lstrip().startswith("├─")  # tool on the trunk
    assert "│  └" in Text.from_markup(verify_line).plain                # verify nested deeper


def test_final_lines_closes_trailing_bare_tool_with_elbow() -> None:
    """The PERSISTED tree closes: a trailing bare tool (no verify child) is
    promoted from ├─ to a └─ elbow so the finished tree reads as closed. The
    live/sink stream never does this (append-only can't know the last child)."""
    from rich.text import Text

    view, _ = _make()
    view.handle_event(NativeEvent(kind="tool_start", label="stand"))
    view.handle_event(NativeEvent(kind="tool_end", label="stand", ok=True))
    tool_line = next(l for l in view.final_lines("站起来") if "●" in l and "stand" in l)
    assert "└─" in Text.from_markup(tool_line).plain


def test_sink_mode_streams_tree_rails() -> None:
    """The field path (sink) shows the same rooted tree: ├─ tools on the trunk,
    │  └─ verify nested under each."""
    from rich.text import Text

    view, lines, _a = _make_sink_view()
    view.begin_goal("回 home")
    view.handle_event(NativeEvent(kind="tool_start", label="navigate", detail="(dest=home)"))
    view.handle_event(NativeEvent(kind="tool_end", label="navigate", ok=True))
    view.handle_event(NativeEvent(kind="verify", label="at_place('home')", ok=True))
    plain = Text.from_markup("\n".join(lines)).plain
    assert "├─" in plain and "●" in plain  # tool on the trunk
    assert "│  └" in plain                  # verify nested under it


def test_final_lines_escapes_goal_markup() -> None:
    view, _ = _make()
    view.handle_event(NativeEvent(kind="tool_start", label="walk"))
    from rich.text import Text

    Text.from_markup("\n".join(view.final_lines("确认 [/tmp/x] 已生成")))  # must not raise


# ---------------------------------------------------------------------------
# P3.7 — transcript-sink mode (persistent composer: no Live, append-only)
# ---------------------------------------------------------------------------


def _make_sink_view():
    lines: list[str] = []
    activity: list[str] = []
    view = ChainView(
        live_factory=lambda r: (_ for _ in ()).throw(AssertionError("no Live in sink mode")),
        transcript_sink=lines.append,
        activity_sink=activity.append,
    )
    return view, lines, activity


def test_sink_mode_never_creates_a_live_region() -> None:
    view, lines, _a = _make_sink_view()
    view.start()  # must NOT call the live factory
    view.handle_event(NativeEvent(kind="tool_start", label="turn"))
    view.stop()
    assert view.start_count == 0


def test_sink_mode_streams_goal_header_and_completed_nodes_once() -> None:
    view, lines, _a = _make_sink_view()
    view.begin_goal("往左转动30度")
    view.handle_event(NativeEvent(kind="tool_start", label="turn", detail="(degrees=30)"))
    assert not [l for l in lines if "turn(" in l]  # running node not yet printed
    view.handle_event(NativeEvent(kind="tool_end", label="turn", ok=True))
    view.handle_event(NativeEvent(kind="verify", label="turned(18)", ok=True))
    view.handle_event(NativeEvent(kind="nudge", label="x", detail="先 verify"))
    text = "\n".join(lines)
    assert "⌂" in lines[0] and "往左转动30度" in lines[0]
    assert "turn(degrees=30)".replace("(degrees=30)", "") in text  # tool line landed
    assert "turned(18)" in text and "✓" in text
    assert "先 verify" in text
    # exactly once each — no duplicates on later events
    assert sum(1 for l in lines if "turned(18)" in l) == 1
    assert view.streamed_to_transcript is True


def test_sink_mode_updates_activity_for_footer() -> None:
    view, _l, activity = _make_sink_view()
    view.handle_event(NativeEvent(kind="round", label="2"))
    view.handle_event(NativeEvent(kind="reasoning", detail="想一下"))
    view.handle_event(NativeEvent(kind="tool_start", label="navigate", detail=""))
    joined = " ".join(activity)
    assert "navigate" in joined
    assert any("2" in a or "думать" not in a for a in activity)  # round visible in some form


def test_default_mode_unchanged_no_sink_flag() -> None:
    view, _lives = _make()
    view.handle_event(NativeEvent(kind="tool_start", label="walk"))
    assert view.streamed_to_transcript is False


def test_sink_mode_does_not_flood_reasoning_but_keeps_full_for_why() -> None:
    """思考刷屏 fix: sink mode must NOT stream the think process ┆-line-by-line
    into the transcript (that flooded the field REPL). The full buffer is still
    accumulated for /why + the post-turn ◌ Thinking · preview."""
    view, lines, _a = _make_sink_view()
    view.handle_event(NativeEvent(kind="reasoning", detail="用户要左转30度。"))
    view.handle_event(NativeEvent(kind="reasoning", detail="turn 技能即可，verify"))
    view.handle_event(NativeEvent(kind="reasoning", detail=" turned(18)。"))
    # No ┆ reasoning lines land in the transcript sink...
    assert not [l for l in lines if "┆" in l]
    # ...but the FULL think buffer is retained (reasoning_text feeds /why).
    assert "左转30度" in view.reasoning_text
    assert "turned(18)" in view.reasoning_text


def test_sink_mode_reasoning_respects_off() -> None:
    got: list[str] = []
    view = ChainView(transcript_sink=got.append, show_reasoning_tail=False)
    view.handle_event(NativeEvent(kind="reasoning", detail="想。"))
    assert not [l for l in got if "┆" in l]


def test_sink_mode_streams_state_machine_forward_once_per_stage() -> None:
    """DELTA 1 (2026-07-15): the persistent-composer sink path never calls
    render_lines(), so the P5 state spine used to be invisible in the field. It
    must now stream ONCE per NEW forward stage (规划→执行→验证→完成), monotonic —
    an act→verify→act loop must NOT re-emit 执行 — and the terminal state must
    persist in final_lines()."""
    view, lines, _a = _make_sink_view()
    view.begin_goal("走到 z lab 门口")
    view.handle_event(NativeEvent(kind="round", label="1"))                 # PLANNING
    view.handle_event(NativeEvent(kind="tool_start", label="goto_place"))   # ACTING
    view.handle_event(NativeEvent(kind="tool_end", label="goto_place", ok=True))
    view.handle_event(NativeEvent(kind="verify", label="at(6.46,-0.45)", ok=True))  # VERIFYING
    view.handle_event(NativeEvent(kind="tool_start", label="goto_place"))   # ACTING again (back)
    view.handle_event(NativeEvent(kind="tool_end", label="goto_place", ok=True))
    view.handle_event(NativeEvent(kind="finish"))                           # DONE

    spine = [l for l in lines if "⣿" in l or "⣀" in l]  # state-bar lines carry the braille track
    assert any("规划" in l and "2/5" in l for l in spine)
    assert any("执行" in l and "3/5" in l for l in spine)
    assert any("验证" in l and "4/5" in l for l in spine)
    assert any("完成" in l and "5/5" in l for l in spine)
    assert len(spine) == 4, (
        f"state bar streams once per forward stage (monotonic), got {len(spine)}")
    final = view.final_lines("走到 z lab 门口")
    assert any("完成" in l and "5/5" in l for l in final), "terminal state persists in the tree"
