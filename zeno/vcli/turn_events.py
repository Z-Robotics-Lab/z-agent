# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""turn_events — the DISPLAY-ONLY structured event a native turn emits.

P1.1 of the CLI UX redesign (docs/CLI_UX_REDESIGN.md): the native ReAct loop
already narrates every chain node through a one-line spinner tail; a UI cannot
rebuild the execution chain from that. ``NativeEvent`` is the structured form
of the SAME narration, emitted through an additive ``on_event`` callback.

Contract:
- Display metadata ONLY. Consumers render it; nothing in the verify spine,
  the trace, or routing ever reads these events. Emission is best-effort
  (a raising consumer is swallowed at the emission site).
- In-process only — never persisted, not a shipped JSONL schema. Fields still
  follow the additive discipline (new fields last, with defaults) so display
  consumers never break on a producer upgrade.

Kinds (label/detail/ok/data usage per kind):
- ``round``       label=round number (1-based) — a model round-trip begins.
- ``reasoning``   detail=reasoning chunk (reasoning models; never session text).
- ``text``        detail=assistant narration chunk.
- ``tool_start``  label=skill name, detail=short arg summary.
- ``tool_end``    label=skill name, ok=dispatch succeeded, detail=error tail.
- ``verify``      label=expr, ok=predicate result (None = rejected foreign
                  predicate, detail carries the rejection tail).
- ``nudge``       label=guardrail id (verify_before_finish | finish_on_fail |
                  degenerate_spin | spin_break), detail=human line.
- ``interject``   operator typed mid-turn; remaining plan cancelled.
- ``finish``      data={wall_sec, turns, in_tokens, out_tokens} — turn wrap-up
                  (emitted exactly once, right before the trace is returned).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class NativeEvent:
    """One display event from the native turn loop (see module docstring)."""

    kind: str
    label: str = ""
    detail: str = ""
    ok: bool | None = None
    data: dict[str, Any] | None = field(default=None)
