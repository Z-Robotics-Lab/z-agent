# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""In-turn progress indicator controller for the REPL.

A single live region that updates IN PLACE for the duration of one user turn.
It exists to fix a concrete UX bug with reasoning models (e.g. DeepSeek): during
the model's long reasoning phase NO text streams for several seconds, and any line
printed to the console while a raw Rich ``Live`` is active interleaves with the
live region's redraws — re-emitting the panel's box-top frame on every refresh so
frames STACK and the prompt duplicates.

``TurnStatus`` owns exactly one live region per turn and exposes:

- ``start()`` / ``stop()`` — open / close the region (idempotent; counted).
- ``pause()`` / ``resume()`` — temporarily stop the region so a tool-execution
  line or summary can be printed cleanly, then restart it. Use ``paused()`` as a
  context manager around any ``console.print`` that must not stack frames.
- ``update_text(text)`` — render streamed assistant text in place.
- ``thinking(elapsed_sec)`` — render the calm "thinking…" indicator during the
  reasoning gap (single in-place status, never a new box).
- an internal one-second heartbeat advances elapsed time even when a provider
  buffers all reasoning and invokes no callbacks.

The renderer is injected (``content_factory``) and the live region is created via
``live_factory`` so the controller's start/stop/pause/resume *logic* is unit-testable
without a TTY — tests pass stub factories and assert the call counts.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from threading import Event, RLock, Thread
from typing import Any, Callable, Iterator, Protocol


class _LiveLike(Protocol):
    """Minimal structural interface for the live region we drive."""

    def start(self, refresh: bool = ...) -> None: ...

    def stop(self) -> None: ...

    def update(self, renderable: Any, refresh: bool = ...) -> None: ...


# A renderable factory: given (text, elapsed_sec, is_thinking) -> a Rich renderable.
ContentFactory = Callable[[str, float, bool], Any]
# A live-region factory: given an initial renderable -> a _LiveLike.
LiveFactory = Callable[[Any], "_LiveLike"]


class TurnStatus:
    """Single in-place progress region for one REPL turn.

    Lifecycle (one turn)::

        status = TurnStatus(content_factory, live_factory)
        status.start()                 # open the region, shows "thinking…"
        ...   status.update_text(...)  # streamed text, in place
        with status.paused():          # stop region, print a tool line, restart
            console.print("read X ok")
        status.stop()                  # close once; never stacks

    All transitions are idempotent: a second ``start()`` while already running is a
    no-op, ``stop()`` when already stopped is a no-op. ``start_count`` /
    ``stop_count`` count only real transitions, so a test can assert the region was
    opened and closed exactly once per turn.
    """

    def __init__(
        self,
        content_factory: ContentFactory,
        live_factory: LiveFactory,
        *,
        thinking_label: str = "thinking…",
        tick_interval: float | None = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._content_factory = content_factory
        self._live_factory = live_factory
        self._thinking_label = thinking_label
        self._tick_interval = (
            max(0.001, float(tick_interval)) if tick_interval is not None else None
        )
        self._clock = clock

        self._live: _LiveLike | None = None
        self._running = False
        self._text = ""
        self._elapsed = 0.0
        # Once any real assistant text streams we leave the "thinking" state and
        # stop showing the reasoning indicator.
        self._has_text = False
        self._started_at: float | None = None
        self._ticker_stop: Event | None = None
        self._ticker_thread: Thread | None = None
        self._lock = RLock()

        # Observable counters (for tests / debugging). Count real transitions only.
        self.start_count = 0
        self.stop_count = 0
        self.pause_count = 0

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def _renderable(self) -> Any:
        is_thinking = not self._has_text
        return self._content_factory(self._text, self._elapsed, is_thinking)

    def _start_ticker_locked(self) -> None:
        """Start one autonomous heartbeat for the current live-region generation."""
        if self._tick_interval is None or self._has_text:
            return
        stop_event = Event()
        self._ticker_stop = stop_event
        ticker = Thread(
            target=self._tick,
            args=(stop_event,),
            name="zeno-thinking-timer",
            daemon=True,
        )
        self._ticker_thread = ticker
        ticker.start()

    def _invalidate_ticker_locked(self) -> None:
        stop_event = self._ticker_stop
        self._ticker_stop = None
        self._ticker_thread = None
        if stop_event is not None:
            stop_event.set()

    def _tick(self, stop_event: Event) -> None:
        """Refresh elapsed time even when the provider buffers every chunk."""
        assert self._tick_interval is not None
        while not stop_event.wait(self._tick_interval):
            with self._lock:
                if (
                    stop_event is not self._ticker_stop
                    or not self._running
                    or self._has_text
                ):
                    return
                started_at = self._started_at
                if started_at is None:
                    continue
                self._elapsed = max(self._elapsed, self._clock() - started_at)
                if self._live is not None:
                    self._live.update(self._renderable())

    def start(self) -> None:
        """Open the live region. Idempotent — a no-op if already running."""
        with self._lock:
            if self._running:
                return
            if self._started_at is None:
                self._started_at = self._clock()
            self._live = self._live_factory(self._renderable())
            self._live.start()
            self._running = True
            self.start_count += 1
            self._start_ticker_locked()

    def stop(self) -> None:
        """Close the live region. Idempotent — a no-op if already stopped.

        Always call this BEFORE printing a final answer or anything outside the
        region, so the region is cleared first and frames never stack.
        """
        with self._lock:
            if not self._running:
                return
            live = self._live
            self._live = None
            self._running = False
            self._invalidate_ticker_locked()
            self.stop_count += 1
        if live is not None:
            live.stop()

    # ------------------------------------------------------------------
    # Pause / resume around foreign prints
    # ------------------------------------------------------------------

    def pause(self) -> bool:
        """Stop the region so a foreign line can be printed without stacking.

        Returns True if it actually stopped a running region (so ``resume`` should
        restart it), False if nothing was running.
        """
        with self._lock:
            if not self._running:
                return False
            self.pause_count += 1
        self.stop()
        return True

    def resume(self) -> None:
        """Restart the region after a pause (no-op if already running)."""
        self.start()

    @contextmanager
    def paused(self) -> Iterator[None]:
        """Context manager: stop the region, yield (caller prints), then restart.

        Restarts only if the region was running on entry, so it is safe to use even
        when no region is active (e.g. on the VGG/MCP path).
        """
        was_running = self.pause()
        try:
            yield
        finally:
            if was_running:
                self.resume()

    # ------------------------------------------------------------------
    # Content updates (in place)
    # ------------------------------------------------------------------

    def update_text(self, text: str) -> None:
        """Append streamed assistant text and refresh the region in place."""
        with self._lock:
            if text:
                self._text += text
                self._has_text = True
                # Once answer text arrives, no late timer frame may replace it.
                if self._ticker_stop is not None:
                    self._ticker_stop.set()
            if self._running and self._live is not None:
                self._live.update(self._renderable())

    def thinking(self, elapsed_sec: float) -> None:
        """Refresh the calm reasoning indicator in place (no new box).

        Called during the reasoning gap (no streamed text). Bumps the elapsed timer
        only while still in the thinking state; once real text has streamed this is
        a no-op so the answer is never replaced by a spinner.
        """
        with self._lock:
            if self._has_text:
                return
            self._elapsed = max(self._elapsed, float(elapsed_sec))
            if self._running and self._live is not None:
                self._live.update(self._renderable())
