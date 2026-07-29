# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""CapabilityLock — an actuator-resource claim registry (research report §3 P3).

dimos guards "two skills both want to drive the base" with ``@skill(uses=["movement"])``
+ an MCP-server claim that REJECTS a conflicting concurrent call. This is the same
idea, scoped to zeno's native producer: an EFFECTING skill declares the physical
resources it occupies (``{"base"}`` / ``{"arm", "gripper"}``), and only ONE holder may
own a given resource at a time. A second request for a held resource is REJECTED with a
clear reason — NEVER blocked — so a model (or a future concurrent / background skill)
gets an actionable correction instead of a deadlock.

Why non-blocking: the native loop runs on the operator's turn thread; a blocking
acquire would freeze the REPL if a background skill held the base. Rejection keeps the
loop live and hands the decision back to the model (wait + retry, or do something else).

Inv-1 (verify is the moat) is untouched: this is a pre-dispatch admission gate. It
records no StepRecord, computes no ``verified``, and never enters the verify namespace —
it can only make the sandbox STRICTER (refuse an action), never greener.

Thread-safe: a single ``threading.Lock`` guards the ``held`` map so ``acquire`` is
atomic (check-all-then-claim-all — no partial claim on a multi-resource skill).
"""
from __future__ import annotations

import threading
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Iterator


class CapabilityConflict(RuntimeError):
    """Raised by ``CapabilityLock.claim`` when a required resource is already held.

    Carries the conflicting resources and the current holder so a caller that prefers
    the context-manager form can translate it into a rejection message.
    """

    def __init__(self, requested: frozenset[str], holder: str, resource: str) -> None:
        self.requested = requested
        self.holder = holder
        self.resource = resource
        super().__init__(
            f"capability {sorted(requested)} conflicts on '{resource}' "
            f"(held by '{holder}')"
        )


class CapabilityLock:
    """A non-blocking claim registry over named actuator resources.

    ``acquire`` is all-or-nothing: if ANY requested resource is held by another holder
    it claims NONE and returns the conflicting holder's name; otherwise it claims ALL
    and returns None. ``release`` drops only the resources this holder actually owns
    (idempotent — a double release, or a release of an unheld resource, is a no-op), so
    a ``finally``-path release is always safe even if acquire never ran.
    """

    def __init__(self) -> None:
        self._held: dict[str, str] = {}  # resource -> holder name
        self._lock = threading.Lock()

    def held_by(self, resource: str) -> str | None:
        """The current holder of *resource*, or None if free (test/introspection)."""
        with self._lock:
            return self._held.get(resource)

    def acquire(self, holder: str, resources: Iterable[str]) -> str | None:
        """Atomically claim ALL *resources* for *holder*.

        Returns None on success. On conflict, claims nothing and returns the name of
        the holder that already owns one of the requested resources (the FIRST such,
        by sorted resource name for determinism). A re-acquire by the SAME holder of a
        resource it already owns is allowed (idempotent self-claim) — it never
        self-conflicts.
        """
        wanted = frozenset(str(r) for r in resources)
        with self._lock:
            for r in sorted(wanted):
                current = self._held.get(r)
                if current is not None and current != holder:
                    return current
            for r in wanted:
                self._held[r] = holder
            return None

    def release(self, holder: str, resources: Iterable[str]) -> None:
        """Drop the *resources* this *holder* owns. Idempotent and holder-scoped: a
        resource held by SOMEONE ELSE is left untouched (a stale/late release from a
        preempted holder can never steal a live claim)."""
        wanted = frozenset(str(r) for r in resources)
        with self._lock:
            for r in wanted:
                if self._held.get(r) == holder:
                    del self._held[r]

    @contextmanager
    def claim(self, holder: str, resources: Iterable[str]) -> Iterator[None]:
        """Context-manager claim: acquire on enter (raise ``CapabilityConflict`` on a
        busy resource), ALWAYS release on exit — including the exception path (finally).
        """
        wanted = frozenset(str(r) for r in resources)
        conflict = self.acquire(holder, wanted)
        if conflict is not None:
            # Report the specific busy resource for a precise message.
            busy = next(
                (r for r in sorted(wanted) if self.held_by(r) not in (None, holder)),
                "",
            )
            raise CapabilityConflict(wanted, conflict, busy)
        try:
            yield
        finally:
            self.release(holder, wanted)
