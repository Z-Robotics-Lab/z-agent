# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""FakeBackend — a deterministic test LLM that drives the REAL cli.main.

R2a PART B: the backend-injection seam in ``cli.create_backend_with_fake_seam``
is gated ONLY on the env var ``VECTOR_FAKE_LLM=<json-path>``. When set, the
network LLM is replaced by this ``FakeBackend``, which returns a canned
``LLMResponse(text=<decompose-plan JSON>)`` — the plan the GoalDecomposer parses.

This replaces ONLY the network LLM. The REAL decomposer / validator / skill /
GoalVerifier / evidence-gate / verdict all still run on the canned plan, so the
verdict stays HONEST by construction: a canned step whose ``verify`` is the
sentinel ``"True"`` STILL classifies RAN (not GROUNDED) and the verdict is False.
The seam never bypasses any verify or permission layer.

Ported from the mock helper in
``tests/integration/vcli/test_end_to_end.py`` (``make_mock_client`` /
``make_response``) — a ``.call(...)`` matching the ``LLMBackend`` Protocol.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from vector_os_nano.vcli.backends.types import LLMResponse
from vector_os_nano.vcli.session import TokenUsage


class FakeBackend:
    """A canned ``LLMBackend``: every ``.call()`` returns the same plan JSON.

    The decomposer's ``.call()`` is the only LLM call on the ``-p`` VGG path
    (the fast single-skill path is byte-identical and never hits the backend),
    so returning the canned decompose-plan JSON as ``LLMResponse.text`` drives a
    fully deterministic plan through the REAL pipeline.
    """

    def __init__(self, plan: dict[str, Any]) -> None:
        # The exact decompose-plan JSON the GoalDecomposer will parse + validate.
        self._plan_text = json.dumps(plan, ensure_ascii=False)

    @classmethod
    def from_json_file(cls, path: str | Path) -> "FakeBackend":
        """Build from a JSON file containing the canned decompose plan.

        The file's top-level object is the plan: ``{"goal", "sub_goals", ...}``.
        Fails LOUD (raises) on a missing / unparseable file — a silent empty plan
        would let a broken harness masquerade as a real run.
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"VECTOR_FAKE_LLM plan must be a JSON object, got {type(data).__name__}")
        return cls(data)

    def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: list[dict[str, Any]],
        max_tokens: int,
        on_text: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Return the canned plan as response text (matches LLMBackend.call)."""
        if on_text is not None:
            on_text(self._plan_text)
        return LLMResponse(
            text=self._plan_text,
            tool_calls=[],
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=0, output_tokens=0),
        )


class FakeToolScriptBackend:
    """A canned ``LLMBackend`` that REPLAYS a SCRIPT of native tool_use turns.

    Drives ``engine.run_turn_native`` deterministically: each ``.call()`` returns
    the NEXT scripted ``LLMResponse`` (a native tool_use turn), advancing a turn
    cursor. A native ReAct turn looks like::

        turn1: tool_calls=[walk(...)]                   stop_reason='tool_use'
        turn2: tool_calls=[verify('at_position(11,3)')] stop_reason='tool_use'  (after the tool_result)
        turn3: tool_calls=[finish()] (or text)          stop_reason='end_turn'

    Unlike ``FakeBackend`` (single-plan decompose JSON for the LEGACY path), this
    seam never returns a decompose plan — it returns the ordered native turns the
    model "would" issue. The REAL native runner still dispatches every skill via
    SkillWrapperTool, evaluates ``verify`` via the REAL GoalVerifier, grades
    actor-causation, and hands the assembled trace to the EXISTING verdict gate —
    so the verdict stays honest by construction (a verify-only script with no walk
    still grades UNCAUSED -> RAN -> verified False).

    After the script is exhausted, every further ``.call()`` returns a terminal
    ``end_turn`` with no tool calls (the loop stops). This makes the runner robust
    to an off-by-one without ever silently re-issuing a stale tool call.
    """

    def __init__(self, turns: list[LLMResponse]) -> None:
        # Defensive copy so a caller mutating the list after construction cannot
        # perturb the replay sequence.
        self._turns: list[LLMResponse] = list(turns)
        self._cursor: int = 0

    # -- serialization seam (parity with FakeBackend.from_json_file) ----------

    @classmethod
    def from_json_file(cls, path: str | Path) -> "FakeToolScriptBackend":
        """Build a tool-script backend from a JSON file of scripted turns.

        The file's top-level object is ``{"turns": [<turn>, ...]}`` where each
        ``<turn>`` is ``{"text"?: str, "stop_reason"?: str,
        "tool_calls": [{"id"?, "name", "input"}, ...]}``. Fails LOUD on a missing /
        unparseable / wrong-shaped file — a silent empty script would let a broken
        harness masquerade as a real native run.
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "turns" not in data:
            raise ValueError(
                "VECTOR_FAKE_LLM_TOOLS payload must be a JSON object with a 'turns' "
                f"list, got {type(data).__name__}"
            )
        return cls.from_tool_script(_turns_from_dicts(data["turns"]))

    @classmethod
    def from_tool_script(cls, turns: list[LLMResponse]) -> "FakeToolScriptBackend":
        """Build directly from an ordered list of ``LLMResponse`` turns."""
        if not isinstance(turns, list):
            raise ValueError(f"tool-script turns must be a list, got {type(turns).__name__}")
        return cls(turns)

    def call(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        system: list[dict[str, Any]],
        max_tokens: int,
        on_text: Callable[[str], None] | None = None,
        on_reasoning: Callable[[str], None] | None = None,
    ) -> LLMResponse:
        """Return the NEXT scripted native turn; terminal end_turn when exhausted."""
        if self._cursor >= len(self._turns):
            return LLMResponse(
                text="", tool_calls=[], stop_reason="end_turn",
                usage=TokenUsage(input_tokens=0, output_tokens=0),
            )
        turn = self._turns[self._cursor]
        self._cursor += 1
        if on_text is not None and turn.text:
            on_text(turn.text)
        return turn


# ---------------------------------------------------------------------------
# JSON <-> LLMResponse turn helpers (single source for the env-var seam)
# ---------------------------------------------------------------------------


def _turns_from_dicts(raw_turns: Any) -> list["LLMResponse"]:
    """Deserialize a list of turn dicts into ``LLMResponse`` native turns."""
    from vector_os_nano.vcli.backends.types import LLMToolCall

    if not isinstance(raw_turns, list):
        raise ValueError(f"'turns' must be a list, got {type(raw_turns).__name__}")
    turns: list[LLMResponse] = []
    for i, t in enumerate(raw_turns):
        if not isinstance(t, dict):
            raise ValueError(f"turn {i} must be an object, got {type(t).__name__}")
        raw_calls = t.get("tool_calls", []) or []
        calls: list[LLMToolCall] = []
        for j, c in enumerate(raw_calls):
            if not isinstance(c, dict) or "name" not in c:
                raise ValueError(f"turn {i} tool_call {j} must name a tool")
            calls.append(
                LLMToolCall(
                    id=str(c.get("id", f"call_{i}_{j}")),
                    name=str(c["name"]),
                    input=dict(c.get("input", {}) or {}),
                )
            )
        stop = str(t.get("stop_reason", "tool_use" if calls else "end_turn"))
        turns.append(
            LLMResponse(
                text=str(t.get("text", "")),
                tool_calls=calls,
                stop_reason=stop,
                usage=TokenUsage(input_tokens=0, output_tokens=0),
            )
        )
    return turns


def tool_turn(*tool_calls: Any, text: str = "", end: bool = False) -> "LLMResponse":
    """Build one scripted native ``LLMResponse`` turn for a tool-script.

    Each positional arg is ``(name, input_dict)``. ``end=True`` (or no tool calls)
    marks the turn's stop_reason ``end_turn``; otherwise ``tool_use``.
    """
    from vector_os_nano.vcli.backends.types import LLMToolCall

    calls = [
        LLMToolCall(id=f"tc_{i}", name=str(name), input=dict(inp or {}))
        for i, (name, inp) in enumerate(tool_calls)
    ]
    stop = "end_turn" if (end or not calls) else "tool_use"
    return LLMResponse(text=text, tool_calls=calls, stop_reason=stop, usage=TokenUsage())
