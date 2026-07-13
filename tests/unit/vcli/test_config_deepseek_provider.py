# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""resolve_credentials: the additive `provider: deepseek` branch.

DeepSeek's native API is OpenAI-compatible but its model ids carry no slash
(e.g. ``deepseek-v4-flash``). The OpenRouter path auto-prefixes ``anthropic/`` to
a slashless model, which would mangle a DeepSeek id — so an explicit
``provider: deepseek`` config returns early with the model UNCHANGED and routes
to the OpenAI-compatible backend. These tests pin that behaviour and that the
existing anthropic/openrouter paths are untouched.

All tests run under the shared ``isolated`` fixture (conftest.py): a real
repo-root ``.env`` would otherwise leak the host's DEEPSEEK_API_KEY into
resolution and beat the fake config keys asserted here.
"""
from __future__ import annotations

import zeno.vcli.config as config
import zeno.vcli.oauth as oauth


def _patch_config(monkeypatch, cfg: dict) -> None:
    monkeypatch.setattr(config, "load_config", lambda: cfg)


def test_deepseek_provider_returns_unmangled_model(isolated):
    _patch_config(isolated, {
        "provider": "deepseek",
        "deepseek_api_key": "sk-test-deepseek",
        "deepseek_base_url": "https://api.deepseek.com",
        "deepseek_model": "deepseek-v4-flash",
        # An OpenRouter key may also be present; it must NOT win.
        "openrouter_api_key": "sk-or-should-not-be-used",
        "model": "google/gemini-2.5-flash",
    })
    key, provider, model, base_url = config.resolve_credentials()
    assert key == "sk-test-deepseek"
    # Non-"anthropic" provider -> create_backend routes to the OpenAI-compat backend.
    assert provider == "openai_compat"
    # The model id is passed through WITHOUT an "anthropic/" prefix.
    assert model == "deepseek-v4-flash"
    assert base_url == "https://api.deepseek.com"


def test_deepseek_cli_model_override_wins(isolated):
    _patch_config(isolated, {
        "provider": "deepseek",
        "deepseek_api_key": "sk-test-deepseek",
        "deepseek_model": "deepseek-v4-flash",
    })
    _, provider, model, _ = config.resolve_credentials(cli_model="deepseek-v4-pro")
    assert provider == "openai_compat"
    assert model == "deepseek-v4-pro"  # CLI flag overrides the config model


def test_deepseek_branch_skipped_without_key(isolated):
    # provider=deepseek but no deepseek key -> fall through to the normal resolution
    # (here: openrouter), never a broken deepseek return.
    _patch_config(isolated, {
        "provider": "deepseek",
        "deepseek_api_key": "",
        "openrouter_api_key": "sk-or-real",
        "model": "google/gemini-2.5-flash",
    })
    key, provider, _, _ = config.resolve_credentials()
    assert provider == "openrouter"
    assert key == "sk-or-real"


def test_forced_openrouter_overrides_oauth(isolated):
    # The non-negotiable fetch-acceptance scenario: a Claude OAuth credential is
    # present (sk-ant-oat...) AND DeepSeek-direct is the configured default, but
    # the operator forces VECTOR_PROVIDER=openrouter because anthropic-direct +
    # DeepSeek-direct are network-blocked. An explicit force MUST win over the
    # OAuth branch — otherwise resolution silently routes to a dead endpoint.
    isolated.setenv("VECTOR_PROVIDER", "openrouter")
    isolated.setenv("OPENROUTER_API_KEY", "sk-or-forced")
    isolated.setenv("VECTOR_MODEL", "deepseek/deepseek-chat")
    isolated.setenv("DEEPSEEK_API_KEY", "sk-deepseek-present")  # default down
    # OAuth creds ARE present (would otherwise hijack to anthropic).
    isolated.setattr(oauth, "load_credentials", lambda: {"accessToken": "sk-ant-oat-xyz"})
    isolated.setattr(config, "load_claude_oauth", lambda: {"accessToken": "sk-ant-oat-xyz"})
    _patch_config(isolated, {"provider": "deepseek", "deepseek_api_key": "sk-ds"})
    key, provider, model, base_url = config.resolve_credentials()
    assert provider == "openrouter", f"forced openrouter ignored -> {provider}"
    assert key == "sk-or-forced"
    # A slash-bearing id is passed through untouched (no anthropic/ mangling).
    assert model == "deepseek/deepseek-chat"
    assert base_url == "https://openrouter.ai/api/v1"


def test_openrouter_path_unchanged(isolated):
    # Regression: a normal openrouter config still mangles a slashless model to
    # anthropic/<model> (existing behaviour the deepseek branch must not disturb).
    _patch_config(isolated, {
        "provider": "openrouter",
        "openrouter_api_key": "sk-or-real",
        "model": "some-model",
    })
    _, provider, model, _ = config.resolve_credentials()
    assert provider == "openrouter"
    assert model == "anthropic/some-model"
