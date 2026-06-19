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
