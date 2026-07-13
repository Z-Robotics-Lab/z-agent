# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Shared fixtures for vcli config/credential tests.

``resolve_credentials`` calls ``dotenv.load_dotenv()``, so on any host with a
real repo-root ``.env`` the developer's actual keys leak into tests that assert
on fake ones. The ``isolated`` fixture makes credential resolution hermetic:
no real ``.env`` / ``~/.vector/config.yaml`` / OAuth token is ever read.
"""
from __future__ import annotations

import pytest

from zeno.vcli import config as cfg
from zeno.vcli import oauth as oauth_mod

_CRED_ENV = (
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_MODEL",
    "DEEPSEEK_BASE_URL",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "VECTOR_PROVIDER",
    "VECTOR_MODEL",
)


@pytest.fixture
def isolated(monkeypatch):
    """Isolate resolve_credentials from any real .env / config / OAuth on the host."""
    import dotenv

    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    monkeypatch.setattr(cfg, "load_config", lambda *a, **k: {})
    monkeypatch.setattr(cfg, "load_claude_oauth", lambda *a, **k: None)
    monkeypatch.setattr(oauth_mod, "load_credentials", lambda *a, **k: None)
    for var in _CRED_ENV:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch
