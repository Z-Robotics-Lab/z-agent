# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""The /agent REPL self-description panel is a product face — it must identify
as Zeno / Z-Robotics-Lab. Any mention of the upstream 'Vector' name is allowed
only as fork-origin attribution, never as the current builder.

Pure-offline: drives _handle_slash_command and captures the rich console output.
"""
from __future__ import annotations

from typing import Any

import zeno.vcli.cli as cli


class _DummyRegistry:
    def list_tools(self) -> list[Any]:
        return []

    def get(self, _name: str) -> Any:
        return None


def _agent_panel_text() -> str:
    """Render the /agent panel and return its captured plain text."""
    with cli.console.capture() as cap:
        cont = cli._handle_slash_command(
            "agent", [], registry=_DummyRegistry(), app_state={}
        )
    assert cont is True  # /agent keeps the REPL running
    return cap.get()


def test_agent_panel_self_identity_is_zeno() -> None:
    text = _agent_panel_text()
    # The panel names the agent Zeno as the AI core of the product's stack.
    assert "Zeno -- the AI core" in text, text
    # Current builder is the fork org, not the upstream org.
    assert "Z-Robotics-Lab" in text, text


def test_agent_panel_vector_only_as_fork_attribution() -> None:
    text = _agent_panel_text()
    # If the upstream name appears at all, it must be framed as fork origin.
    if "Vector" in text:
        assert "Forked from Vector" in text, text
    # It must NOT claim Vector Robotics as the current builder.
    assert "Built by Vector Robotics" not in text, text


def test_agent_panel_ai_core_self_names_zeno_not_v() -> None:
    """The panel body must self-identify as Zeno, never the legacy short name 'V'.

    The old copy read "V -- the AI core ..." and "V owns the hardware ... V's
    body. V speaks your language." 'V' is the Vector-derived persona name; the
    product face must use Zeno consistently with prompt.py's DEFAULT_PERSONALITY.
    """
    text = _agent_panel_text()
    assert "Zeno owns the hardware" in text, text
    assert "Zeno speaks your language" in text, text
    # No bare "V" acting as the agent's own name.
    assert "V --" not in text, text
    assert "V owns" not in text, text
    assert "V's body" not in text, text
