# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""TYPED INTERJECT — queue operator instructions typed WHILE a turn is executing.

Field ask 2026-07-11 ("执行任务中我没法 prompt,顶层指令需要插队"): during a blocking
turn (a 5 m walk, a multi-step native plan) the REPL prompt is gone and Ctrl+C-cancel
is the operator's ONLY channel. This module adds the second channel:

- ``InterjectReader`` — a background stdin reader ACTIVE ONLY while a turn is
  executing (the REPL opens the window around each blocking turn and closes it
  before the prompt returns, so it can never fight prompt_toolkit). Typed lines
  queue FIFO; the kernel checks the queue at SAFE boundaries (native-loop
  iteration top + before each motor-skill dispatch) and the REPL runs the queued
  line as the immediate next turn.

- ``cancel_current_motion`` — the SINGLE cancel seam. Extracted from
  ``cli._operator_interrupt`` so the typed interject cancels motion through the
  SAME world ``on_operator_interrupt`` hook Ctrl+C uses (go2w_real: nav-goal
  cancel, NOT an E-stop). Ctrl+C behaviour stays byte-identical — cli's handler
  now delegates here and prints the same 🛑 line.

STDIN-COLLISION RULE (field trace 2026-07-13: permission prompts and streamed
boxes garble each other): the interactive permission prompt also reads stdin, so
the reader MUST NOT consume the operator's y/n/a answer. ``suspended()`` parks
the reader (it stops select()ing entirely, leaving the bytes in the tty buffer
for ``Prompt.ask``); ``cli.ask_permission`` wraps its prompt in
``reader_suspended()`` via the module-level current-reader registration.

Implementation notes: the reader polls ``select.select`` with a short timeout
instead of a blocking ``readline`` so stop()/suspend() take effect within one
poll interval and the thread can never wedge holding stdin. A stream that cannot
be select()ed (no usable fileno) simply disarms the reader — the REPL then
behaves exactly as before this module existed (typed lines become prompt
typeahead). Everything here is fail-safe: no code path may raise into the REPL
or the kernel loop.
"""
from __future__ import annotations

import logging
import select
import sys
import threading
import time
from collections import deque
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# Default poll interval (seconds): how quickly stop()/suspend() take effect and
# the upper bound the reader holds stdin after its window closes.
_POLL_INTERVAL_S = 0.05


class InterjectReader:
    """Background stdin reader + FIFO queue for operator interjects.

    Lifecycle: ``start()`` opens the window (spawns a daemon poll thread);
    ``stop()`` closes it (the thread exits within one poll interval). Both are
    idempotent and a stopped reader can be started again for the next turn.
    ``push()`` is the programmatic/test seam — the queue works without a thread.
    """

    def __init__(self, stream: Any = None, poll_interval: float = _POLL_INTERVAL_S) -> None:
        # None -> resolve sys.stdin lazily at thread start (tests/pty harnesses
        # that swap sys.stdin after construction still get the live stream).
        self._stream = stream
        self._interval = float(poll_interval)
        self._active = threading.Event()
        self._suspended = threading.Event()
        self._lock = threading.Lock()
        self._queue: deque[str] = deque()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Window lifecycle (the REPL opens/closes this around blocking turns)
    # ------------------------------------------------------------------

    def is_active(self) -> bool:
        return self._active.is_set()

    def start(self) -> None:
        """Open the interject window. Idempotent; never raises into the REPL."""
        if self._active.is_set():
            return
        self._active.set()
        try:
            t = threading.Thread(
                target=self._run, name="zeno-interject-reader", daemon=True
            )
            self._thread = t
            t.start()
        except Exception as exc:  # noqa: BLE001 — a reader that cannot start disarms
            logger.debug("interject: reader thread failed to start: %s", exc)
            self._active.clear()
            self._thread = None

    def stop(self) -> None:
        """Close the window. The thread exits within ~one poll interval."""
        self._active.clear()
        t = self._thread
        if t is not None:
            try:
                t.join(timeout=max(0.5, self._interval * 4))
            except Exception:  # noqa: BLE001
                pass
            self._thread = None

    # ------------------------------------------------------------------
    # Permission-prompt suspension (the stdin-collision fix)
    # ------------------------------------------------------------------

    def suspend(self) -> None:
        self._suspended.set()

    def resume(self) -> None:
        self._suspended.clear()

    @contextmanager
    def suspended(self) -> Iterator[None]:
        """While held, the reader does not touch stdin — the prompt owns it."""
        self.suspend()
        try:
            yield
        finally:
            self.resume()

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------

    def push(self, line: str) -> None:
        """Queue one interject line (stripped; blank lines never queue)."""
        line = (line or "").strip()
        if line:
            with self._lock:
                self._queue.append(line)

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._queue)

    def pop(self) -> str | None:
        """Dequeue the oldest interject line, or None when empty."""
        with self._lock:
            return self._queue.popleft() if self._queue else None

    # ------------------------------------------------------------------
    # Poll thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        try:
            stream = self._stream if self._stream is not None else sys.stdin
        except Exception:  # noqa: BLE001
            return
        while self._active.is_set():
            if self._suspended.is_set():
                # A permission prompt owns stdin: do not even select() — any
                # buffered bytes must reach Prompt.ask untouched.
                time.sleep(self._interval)
                continue
            try:
                readable, _, _ = select.select([stream], [], [], self._interval)
            except Exception:  # noqa: BLE001 — unselectable/closed stream: disarm
                return
            if not readable:
                continue
            # Re-check AFTER select returns: a stop()/suspend() that landed while
            # we were polling must win — the bytes stay buffered for the prompt.
            if not self._active.is_set() or self._suspended.is_set():
                continue
            try:
                line = stream.readline()
            except Exception:  # noqa: BLE001
                return
            if line == "":
                return  # EOF — window is dead for this stream
            self.push(line)


# ---------------------------------------------------------------------------
# Kernel-facing helpers (duck-typed via app_state — the kernel imports no world)
# ---------------------------------------------------------------------------


def interject_pending(app_state: dict[str, Any] | None) -> bool:
    """True iff an operator interject line is queued. Fail-safe: never raises."""
    reader = (app_state or {}).get("interject")
    if reader is None:
        return False
    try:
        return bool(reader.has_pending())
    except Exception:  # noqa: BLE001 — a broken reader must never break a turn
        return False


def cancel_current_motion(
    app_state: dict[str, Any] | None, default_msg: str = "已中断本轮任务。"
) -> str:
    """Cancel in-flight motion via the SAME seam Ctrl+C uses; return the report.

    Extracted VERBATIM from ``cli._operator_interrupt`` (field trace 2026-07-10)
    so the typed interject and Ctrl+C share ONE cancel path: the active world's
    ``on_operator_interrupt(agent)`` when it defines one (go2w_real cancels the
    nav goal — deliberately NOT an E-stop), else the cognitive abort flag.
    Never raises.
    """
    msg = default_msg
    try:
        world = (app_state or {}).get("world")
        agent = (app_state or {}).get("agent")
        hook = getattr(world, "on_operator_interrupt", None)
        if callable(hook):
            msg = hook(agent) or msg
        else:
            from zeno.vcli.cognitive.abort import request_abort

            request_abort()
    except Exception:  # noqa: BLE001 — the interrupt path must never raise
        pass
    return msg


# ---------------------------------------------------------------------------
# Current-reader registration (so ask_permission can suspend without plumbing)
# ---------------------------------------------------------------------------

_current_reader: InterjectReader | None = None


def set_current_reader(reader: InterjectReader | None) -> None:
    """Register the session's reader (the REPL sets it once at startup)."""
    global _current_reader
    _current_reader = reader


@contextmanager
def reader_suspended() -> Iterator[None]:
    """Suspend the session's reader (no-op when none) around a stdin prompt."""
    reader = _current_reader
    if reader is None:
        yield
        return
    with reader.suspended():
        yield
