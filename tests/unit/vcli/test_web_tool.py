# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Unit tests for WebFetchTool — outbound HTTP identity (User-Agent).

The User-Agent header is a product face: it lands in external servers' access
logs, so it must carry the product name Zeno, not the upstream fork name.
These tests are pure-offline: urllib.request.urlopen is stubbed, no network.
"""
from __future__ import annotations

import io
from typing import Any

from zeno.vcli.tools import web_tool
from zeno.vcli.tools.web_tool import WebFetchTool, _USER_AGENT


def test_user_agent_constant_is_zeno_branded() -> None:
    """The UA constant carries the Zeno product name, not the fork name."""
    assert _USER_AGENT.startswith("Zeno/"), _USER_AGENT
    assert "Vector" not in _USER_AGENT, _USER_AGENT
    assert "VectorOS" not in _USER_AGENT, _USER_AGENT


def test_outbound_request_sends_zeno_user_agent(monkeypatch: Any) -> None:
    """execute() actually puts a Zeno-branded User-Agent on the wire.

    Verifies the real outbound header (behaviour), not just the constant, by
    capturing the urllib Request handed to urlopen. No network is touched.
    """
    captured: dict[str, Any] = {}

    class _FakeResponse:
        def __enter__(self) -> "_FakeResponse":
            return self

        def __exit__(self, *exc: Any) -> None:
            return None

        def read(self) -> bytes:
            return b"<html><body>hi</body></html>"

    def _fake_urlopen(req: Any, timeout: float = 0.0) -> _FakeResponse:  # noqa: ARG001
        # urllib normalises header keys to title-case (User-agent).
        captured["ua"] = req.get_header("User-agent")
        return _FakeResponse()

    # Skip the SSRF DNS resolution so example.com needs no network.
    monkeypatch.setattr(web_tool, "_is_blocked_url", lambda _url: False)
    monkeypatch.setattr(web_tool.urllib.request, "urlopen", _fake_urlopen)

    # web_fetch's execute() never reads context, so None is sufficient here.
    tool = WebFetchTool()
    result = tool.execute({"url": "https://example.com"}, None)  # type: ignore[arg-type]

    assert not result.is_error, result.content
    assert captured["ua"] is not None
    assert captured["ua"].startswith("Zeno/"), captured["ua"]
    assert "Vector" not in captured["ua"], captured["ua"]
