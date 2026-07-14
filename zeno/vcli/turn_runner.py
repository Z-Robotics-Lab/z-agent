# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""turn_runner — the persistent-composer turn executor (P3.7, owner ask).

Claude-Code-style REPL: the composer input NEVER goes away. ``submit()``
returns immediately; the turn body runs on ONE worker thread; output prints
above the live composer (prompt_toolkit ``patch_stdout``); a submit while a
turn is running routes into the SAME interject queue the kernel already polls
at its safe boundaries (native_loop iteration top / per motor dispatch), so
typing mid-turn keeps the field cancel-and-replace semantics byte-identical.
When the turn ends and the kernel left a queued line unconsumed, the runner
starts it as the next turn automatically.

Display-only module: it owns NO verify/routing logic — ``run_turn`` is the
cli's existing single-turn body, injected as a callable.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable

logger = logging.getLogger(__name__)


class ComposerInterjectQueue:
    """The kernel-facing interject duck type, MINUS the stdin reader thread.

    In persistent-composer mode prompt_toolkit owns stdin for the whole
    session, so the select()-loop ``InterjectReader`` must never run — typed
    lines arrive via ``TurnRunner.submit`` instead. This queue keeps the exact
    protocol surface the kernel and cli helpers already consume
    (``has_pending``/``pop``/``push``; ``start``/``stop``/``suspend``/
    ``resume``/``is_active`` are safe no-ops).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lines: deque[str] = deque()

    # -- protocol no-ops (stdin never touched) --------------------------
    def start(self) -> None:  # noqa: D102 — protocol no-op
        return None

    def stop(self) -> None:  # noqa: D102 — protocol no-op
        return None

    def suspend(self) -> None:  # noqa: D102 — protocol no-op
        return None

    def resume(self) -> None:  # noqa: D102 — protocol no-op
        return None

    def is_active(self) -> bool:
        return False

    # -- the queue ------------------------------------------------------
    def push(self, line: str) -> None:
        line = (line or "").strip()
        if not line:
            return
        with self._lock:
            self._lines.append(line)

    def has_pending(self) -> bool:
        with self._lock:
            return bool(self._lines)

    def pop(self) -> str | None:
        with self._lock:
            return self._lines.popleft() if self._lines else None


class TurnRunner:
    """Run one turn at a time on a worker thread; queue mid-turn submissions."""

    def __init__(
        self,
        *,
        run_turn: Callable[[str], Any],
        interject_queue: ComposerInterjectQueue,
        echo: Callable[[str], None] | None = None,
        name: str = "zeno-turn",
    ) -> None:
        self._run_turn = run_turn
        self._queue = interject_queue
        self._echo = echo
        self._name = name
        self._lock = threading.Lock()
        self._busy = False
        self._idle = threading.Event()
        self._idle.set()
        self._activity = ""

    # -- state for the composer footer -----------------------------------
    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy

    @property
    def activity(self) -> str:
        with self._lock:
            return self._activity

    def set_activity(self, text: str) -> None:
        with self._lock:
            if self._busy:
                self._activity = str(text or "")

    # -- submission -------------------------------------------------------
    def submit(self, text: str) -> str:
        """Start the turn now, or queue it as an interject when busy.

        Returns 'started' | 'queued' | 'ignored' (blank input). Never blocks.
        """
        text = (text or "").strip()
        if not text:
            return "ignored"
        with self._lock:
            if self._busy:
                self._queue.push(text)
                if self._echo is not None:
                    try:
                        self._echo(f"⏸ 已插队: {text}")
                    except Exception:  # noqa: BLE001 — echo is display-only
                        pass
                return "queued"
            self._busy = True
            self._idle.clear()
        threading.Thread(
            target=self._worker, args=(text,), name=self._name, daemon=True
        ).start()
        return "started"

    def _worker(self, text: str) -> None:
        while True:
            try:
                self._run_turn(text)
            except Exception:  # noqa: BLE001 — a turn crash must not wedge input
                logger.exception("turn body raised")
            # The kernel pops queued lines it consumed at its safe boundaries;
            # anything still queued is the operator's NEXT turn — run it now.
            nxt = None
            try:
                nxt = self._queue.pop()
            except Exception:  # noqa: BLE001
                nxt = None
            if nxt is None:
                break
            if self._echo is not None:
                try:
                    self._echo(f"⏸ 插队: {nxt}")
                except Exception:  # noqa: BLE001
                    pass
            text = nxt
        with self._lock:
            self._busy = False
            self._activity = ""
        self._idle.set()

    def wait_idle(self, timeout: float | None = None) -> bool:
        """Block until idle (tests / clean exit). True iff idle was reached."""
        return self._idle.wait(timeout)


def runner_from(app_state: dict[str, Any] | None) -> TurnRunner | None:
    """The session's TurnRunner, if the persistent composer is active."""
    runner = (app_state or {}).get("turn_runner")
    return runner if isinstance(runner, TurnRunner) else None
