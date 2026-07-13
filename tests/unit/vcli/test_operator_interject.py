# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""TYPED INTERJECT — operator types a new instruction WHILE a turn is executing.

Field ask 2026-07-11: "执行任务中我没法 prompt,顶层指令需要插队" — today Ctrl+C-cancel
is the only mid-turn channel. This round adds a background stdin reader that is
ACTIVE ONLY while a turn is executing; typed lines queue, and at SAFE boundaries
(native-loop iteration top; before each motor-skill dispatch inside a multi-call
turn) the kernel checks the queue: on a pending line it cancels current motion via
the SAME world ``on_operator_interrupt`` seam Ctrl+C uses, marks the remaining
tool calls cancelled-by-operator, and the REPL runs the queued line as the
immediate next turn. Ctrl+C behaviour stays byte-identical.

Hermetic BY DESIGN (the pty suite env-fails on this NUC): the reader is driven by
an ``os.pipe`` fake stdin, the native loop by ``FakeToolScriptBackend`` + the
duck-typed fake agent from test_native_loop, and the REPL seam by a fake engine.
No MuJoCo, no network, no pty.

Also pinned here: the /permissions mode (auto|manual) persists across sessions
via the existing zeno config mechanism (CLI --no-permission always wins), and the
permission prompt SUSPENDS the reader so the y/n/a answer is never stolen
(the stdin-collision fix).
"""
from __future__ import annotations

import os
import select
import time
from io import StringIO
from types import SimpleNamespace
from typing import Any

import pytest
from rich.console import Console

from tests.harness.fake_backend import FakeToolScriptBackend, tool_turn
from tests.unit.vcli.test_native_loop import _make_agent, _make_engine, _session


# ---------------------------------------------------------------------------
# Harness bits
# ---------------------------------------------------------------------------


def _pipe_stream():
    """An os.pipe wrapped as a text stream pair (write_fd, read_stream)."""
    r_fd, w_fd = os.pipe()
    return w_fd, os.fdopen(r_fd, "r")


def _wait_until(cond, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if cond():
            return True
        time.sleep(0.01)
    return False


class _StubReader:
    """Deterministic has_pending sequencing for the kernel-boundary tests."""

    def __init__(self, false_calls: int = 0, pending: bool = True) -> None:
        self.calls = 0
        self._false_calls = false_calls
        self._pending = pending

    def has_pending(self) -> bool:
        self.calls += 1
        if self.calls <= self._false_calls:
            return False
        return self._pending


class _RecordingWorld:
    """World stub exposing the SAME on_operator_interrupt seam Ctrl+C uses."""

    def __init__(self) -> None:
        self.interrupts = 0

    def on_operator_interrupt(self, agent: Any) -> str:
        self.interrupts += 1
        return "已取消当前导航目标。"


# ---------------------------------------------------------------------------
# A. InterjectReader — background stdin reader (fake stdin via os.pipe)
# ---------------------------------------------------------------------------


def test_reader_captures_typed_line_during_window():
    from zeno.vcli.interject import InterjectReader

    w_fd, stream = _pipe_stream()
    reader = InterjectReader(stream=stream, poll_interval=0.02)
    try:
        reader.start()
        assert reader.is_active()
        os.write(w_fd, "去厨房\n".encode())
        assert _wait_until(reader.has_pending)
        assert reader.pop() == "去厨房"
        assert reader.pop() is None
    finally:
        reader.stop()
        os.close(w_fd)
        stream.close()
    assert not reader.is_active()


def test_reader_fifo_order_and_push_seam():
    from zeno.vcli.interject import InterjectReader

    reader = InterjectReader(stream=StringIO())  # never started — push() only
    reader.push("first")
    reader.push("  second  ")  # stripped
    reader.push("")  # blank lines never queue
    assert reader.has_pending()
    assert reader.pop() == "first"
    assert reader.pop() == "second"
    assert reader.pop() is None
    assert not reader.has_pending()


def test_reader_inactive_outside_window_leaves_stdin_alone():
    """No window (start never called) -> typed bytes are NOT consumed."""
    from zeno.vcli.interject import InterjectReader

    w_fd, stream = _pipe_stream()
    reader = InterjectReader(stream=stream, poll_interval=0.02)
    try:
        os.write(w_fd, b"y\n")
        time.sleep(0.1)
        assert not reader.has_pending()
        # The bytes are still there for whoever reads stdin next.
        readable, _, _ = select.select([stream], [], [], 0)
        assert readable
    finally:
        os.close(w_fd)
        stream.close()


def test_reader_suspended_leaves_bytes_for_permission_prompt():
    """CRITICAL COLLISION: while a permission prompt owns stdin the reader must
    NOT consume the operator's y/n/a answer."""
    from zeno.vcli.interject import InterjectReader

    w_fd, stream = _pipe_stream()
    reader = InterjectReader(stream=stream, poll_interval=0.02)
    try:
        reader.start()
        with reader.suspended():
            os.write(w_fd, b"y\n")
            time.sleep(0.15)  # several poll intervals
            assert not reader.has_pending()
            # The prompt (the real stdin consumer) still sees the answer.
            readable, _, _ = select.select([stream], [], [], 0)
            assert readable
            assert stream.readline().strip() == "y"
        # After resume the reader works again.
        os.write(w_fd, b"next command\n")
        assert _wait_until(reader.has_pending)
        assert reader.pop() == "next command"
    finally:
        reader.stop()
        os.close(w_fd)
        stream.close()


def test_reader_stop_is_idempotent_and_restartable():
    from zeno.vcli.interject import InterjectReader

    w_fd, stream = _pipe_stream()
    reader = InterjectReader(stream=stream, poll_interval=0.02)
    try:
        reader.start()
        reader.start()  # idempotent
        reader.stop()
        reader.stop()  # idempotent
        assert not reader.is_active()
        reader.start()  # a new turn re-opens the window
        os.write(w_fd, b"again\n")
        assert _wait_until(reader.has_pending)
        assert reader.pop() == "again"
    finally:
        reader.stop()
        os.close(w_fd)
        stream.close()


# ---------------------------------------------------------------------------
# B. cancel seam — the SAME world hook Ctrl+C uses; Ctrl+C output unchanged
# ---------------------------------------------------------------------------


def test_cancel_current_motion_calls_world_hook():
    from zeno.vcli.interject import cancel_current_motion

    world = _RecordingWorld()
    msg = cancel_current_motion({"world": world, "agent": None})
    assert world.interrupts == 1
    assert msg == "已取消当前导航目标。"


def test_cancel_current_motion_without_world_never_raises():
    from zeno.vcli.interject import cancel_current_motion

    assert cancel_current_motion(None) == "已中断本轮任务。"
    assert cancel_current_motion({}) == "已中断本轮任务。"


def test_operator_interrupt_ctrl_c_output_byte_identical(monkeypatch):
    """Ctrl+C path: same seam, same 🛑 message shape as before this round."""
    from zeno.vcli import cli

    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False))
    world = _RecordingWorld()
    cli._operator_interrupt({"world": world, "agent": None})
    out = buf.getvalue()
    assert "🛑" in out
    assert "已取消当前导航目标。" in out
    assert world.interrupts == 1


# ---------------------------------------------------------------------------
# C. native-loop SAFE boundaries (kernel checks the queue)
# ---------------------------------------------------------------------------


def _native_app_state(reader: Any, world: Any) -> dict[str, Any]:
    return {"interject": reader, "world": world, "agent": None}


def test_native_loop_interject_at_loop_top_cancels_before_any_action():
    """Pending BEFORE the round-trip -> no backend call, no motion, hook fired."""
    calls: list[int] = []

    class _Recorder(FakeToolScriptBackend):
        def call(self, **kw):  # type: ignore[override]
            calls.append(1)
            return super().call(**kw)

    backend = _Recorder.from_tool_script(
        [
            tool_turn(("walk", {"distance": 2.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 5.0)"})),
            tool_turn(end=True),
        ]
    )
    agent, base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    world = _RecordingWorld()
    reader = _StubReader(false_calls=0)

    trace = eng.run_turn_native(
        "去厨房", session=_session(), app_state=_native_app_state(reader, world)
    )

    assert calls == []  # cancelled at the loop top, before any LLM round-trip
    assert base._cmd_motion == 0.0
    assert trace.steps == ()
    assert world.interrupts == 1


def test_native_loop_interject_mid_turn_marks_remaining_cancelled():
    """Pending detected before a motor dispatch -> this + remaining calls are
    cancelled-by-operator, motion cancel fires ONCE, loop ends."""
    calls: list[int] = []

    class _Recorder(FakeToolScriptBackend):
        def call(self, **kw):  # type: ignore[override]
            calls.append(1)
            return super().call(**kw)

    backend = _Recorder.from_tool_script(
        [
            tool_turn(
                ("walk", {"distance": 1.0, "speed": 0.3}),
                ("walk", {"distance": 1.0, "speed": 0.3}),
            ),
            tool_turn(("verify", {"expr": "at_position(2.0, 0.0, 1.0)"})),
            tool_turn(end=True),
        ]
    )
    agent, base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)
    world = _RecordingWorld()
    # First has_pending check (loop top) False -> the round-trip happens; the
    # SECOND check (before the first walk dispatch) True -> interject.
    reader = _StubReader(false_calls=1)
    session = _session()

    trace = eng.run_turn_native(
        "走2米", session=session, app_state=_native_app_state(reader, world)
    )

    assert calls == [1]  # exactly one round-trip, then cancelled
    assert base._cmd_motion == 0.0  # neither walk dispatched
    assert trace.steps == ()
    assert world.interrupts == 1  # motion cancel fired once, not per call
    # Both tool calls were answered cancelled-by-operator in the session.
    flat = str(session.to_messages())
    assert flat.count("cancelled-by-operator") == 2


def test_native_loop_without_reader_byte_identical():
    """No 'interject' in app_state -> the loop runs exactly as before."""
    backend = FakeToolScriptBackend.from_tool_script(
        [
            tool_turn(("walk", {"distance": 2.0, "speed": 0.3})),
            tool_turn(("verify", {"expr": "at_position(0.0, 0.0, 5.0)"})),
            tool_turn(("finish", {})),
        ]
    )
    agent, base = _make_agent(0.0, 0.0)
    eng = _make_engine(agent, backend)

    trace = eng.run_turn_native("walk then verify", session=_session(), app_state={})

    assert len(trace.steps) == 1
    assert base._cmd_motion > 0.0


# ---------------------------------------------------------------------------
# D. REPL seam — the interjected turn OWNS the turn (never legacy re-run)
# ---------------------------------------------------------------------------


class _FakeNativeEngine:
    """run_turn_native stand-in that records whether the reader window was open."""

    _vgg_agent = None

    def __init__(self, reader: Any, trace: Any = None) -> None:
        self._reader = reader
        self._trace = trace
        self.window_open_during_turn: bool | None = None

    def run_turn_native(self, user_input, agent=None, session=None, app_state=None, on_progress=None, on_event=None):
        self.window_open_during_turn = bool(self._reader.is_active())
        return self._trace


def test_repl_attempt_native_opens_window_and_owns_interjected_turn(monkeypatch, tmp_path):
    from zeno.vcli import cli
    from zeno.vcli.interject import InterjectReader

    monkeypatch.setenv("HOME", str(tmp_path))
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False)
    monkeypatch.setattr(cli, "console", test_console)

    reader = InterjectReader(stream=StringIO())
    engine = _FakeNativeEngine(reader)
    app_state = {"interject": reader, "world": _RecordingWorld(), "agent": None}

    # Simulate the operator typing mid-turn: the line is queued while the fake
    # turn runs (push happens before the call; the fake returns no-action trace).
    reader.push("换个方向,去门口")
    owned = cli._repl_attempt_native(engine, "走5米", _FakeSession(), app_state, test_console)

    # The reader window was open DURING the turn and closed after.
    assert engine.window_open_during_turn is True
    assert not reader.is_active()
    # A no-action trace would normally fall back to legacy (return False); with a
    # pending interject the turn is OWNED so legacy never re-runs the overridden goal.
    assert owned is True
    assert "插队" in buf.getvalue()
    # The queued line is still pending for the REPL to run as the next turn.
    assert reader.pop() == "换个方向,去门口"


def test_repl_attempt_native_no_interject_still_falls_back(monkeypatch, tmp_path):
    from zeno.vcli import cli
    from zeno.vcli.interject import InterjectReader

    monkeypatch.setenv("HOME", str(tmp_path))
    buf = StringIO()
    test_console = Console(file=buf, force_terminal=False)
    monkeypatch.setattr(cli, "console", test_console)

    reader = InterjectReader(stream=StringIO())
    engine = _FakeNativeEngine(reader)
    app_state = {"interject": reader, "world": _RecordingWorld(), "agent": None}

    owned = cli._repl_attempt_native(engine, "走5米", _FakeSession(), app_state, test_console)
    assert owned is False  # no interject + no action -> legacy fallback unchanged
    assert not reader.is_active()


class _FakeSession:
    def append_user(self, text: str) -> None:
        pass

    def append_assistant(self, text: str, tool_use=None) -> None:
        pass


# ---------------------------------------------------------------------------
# E. permission prompt suspends the reader (stdin-collision fix)
# ---------------------------------------------------------------------------


def test_ask_permission_suspends_active_reader(monkeypatch):
    from zeno.vcli import cli
    from zeno.vcli import interject as ij

    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False))

    reader = ij.InterjectReader(stream=StringIO())
    ij.set_current_reader(reader)
    seen: dict[str, bool] = {}

    def _fake_ask(*a, **k):
        seen["suspended_during_prompt"] = reader._suspended.is_set()
        return "y"

    monkeypatch.setattr(cli.Prompt, "ask", staticmethod(_fake_ask))
    try:
        ans = cli.ask_permission("walk", {"distance": 5})
        assert ans == "y"
        assert seen["suspended_during_prompt"] is True
        assert not reader._suspended.is_set()  # resumed after the prompt
    finally:
        ij.set_current_reader(None)


def test_ask_permission_without_reader_unchanged(monkeypatch):
    from zeno.vcli import cli
    from zeno.vcli import interject as ij

    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False))
    ij.set_current_reader(None)
    monkeypatch.setattr(cli.Prompt, "ask", staticmethod(lambda *a, **k: "n"))
    assert cli.ask_permission("walk", {}) == "n"


# ---------------------------------------------------------------------------
# F. /permissions mode persists across sessions (existing config mechanism)
# ---------------------------------------------------------------------------


def test_approval_mode_save_and_apply_roundtrip(monkeypatch, tmp_path):
    from zeno.vcli import cli
    from zeno.vcli.config import load_config
    from zeno.vcli.permissions import PermissionContext

    monkeypatch.setenv("HOME", str(tmp_path))
    cli._save_approval_mode(True)
    assert load_config().get("approval_mode") == "auto"

    perms = PermissionContext(no_permission=False)
    cli._apply_saved_approval_mode(SimpleNamespace(no_permission=False), perms)
    assert perms.no_permission is True

    cli._save_approval_mode(False)
    assert load_config().get("approval_mode") == "manual"
    perms2 = PermissionContext(no_permission=False)
    cli._apply_saved_approval_mode(SimpleNamespace(no_permission=False), perms2)
    assert perms2.no_permission is False


def test_saved_manual_never_downgrades_cli_flag(monkeypatch, tmp_path):
    from zeno.vcli import cli
    from zeno.vcli.permissions import PermissionContext

    monkeypatch.setenv("HOME", str(tmp_path))
    cli._save_approval_mode(False)  # saved: manual
    perms = PermissionContext(no_permission=True)  # --no-permission on the CLI
    cli._apply_saved_approval_mode(SimpleNamespace(no_permission=True), perms)
    assert perms.no_permission is True  # the explicit flag always wins


def test_permissions_slash_command_persists_mode(monkeypatch, tmp_path):
    from zeno.vcli import cli
    from zeno.vcli.config import load_config
    from zeno.vcli.permissions import PermissionContext

    monkeypatch.setenv("HOME", str(tmp_path))
    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False))
    perms = PermissionContext(no_permission=False)
    app_state = {"permissions": perms}

    assert cli._handle_slash_command("permissions", ["auto"], None, None, app_state)
    assert perms.no_permission is True
    assert load_config().get("approval_mode") == "auto"

    assert cli._handle_slash_command("permissions", ["manual"], None, None, app_state)
    assert perms.no_permission is False
    assert load_config().get("approval_mode") == "manual"


def test_auto_mode_warning_printed_when_auto(monkeypatch):
    from zeno.vcli import cli
    from zeno.vcli.permissions import PermissionContext

    buf = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf, force_terminal=False))
    cli._warn_if_auto_mode(PermissionContext(no_permission=True))
    assert "REAL ROBOT" in buf.getvalue()

    buf2 = StringIO()
    monkeypatch.setattr(cli, "console", Console(file=buf2, force_terminal=False))
    cli._warn_if_auto_mode(PermissionContext(no_permission=False))
    assert buf2.getvalue() == ""
