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
    from rich.text import Text

    view, _ = _make()
    view.handle_event(
        NativeEvent(kind="tool_start", label="turn", detail="(direction=left)")
    )
    running = _text(view)
    running_plain = Text.from_markup(running).plain
    assert "◇" in running_plain and "Tool · turn" in running_plain

    view.handle_event(NativeEvent(kind="tool_end", label="turn", ok=True))
    finished = _text(view)
    assert "◇" in finished and "✓" in finished
    assert "[dim #738091]Tool[/]" in finished


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


def test_final_lines_escapes_goal_markup() -> None:
    view, _ = _make()
    view.handle_event(NativeEvent(kind="tool_start", label="walk"))
    from rich.text import Text

    Text.from_markup("\n".join(view.final_lines("确认 [/tmp/x] 已生成")))  # must not raise
