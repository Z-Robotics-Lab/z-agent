# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Regression tests for repo-root .env credential resolution (config DX).

Covers the env-var branches added to ``resolve_credentials``: ``DEEPSEEK_API_KEY``
as the default provider, OpenRouter as the multi-model fallback, the
``VECTOR_PROVIDER`` opt-out, ``VECTOR_MODEL`` selection, and config-file
back-compat. Fully hermetic — no real ``.env`` / ``~/.vector/config.yaml`` / OAuth
token is read (load_dotenv, load_config and both OAuth loaders are patched).
"""
from __future__ import annotations

import pytest

from vector_os_nano.vcli import config as cfg
from vector_os_nano.vcli import oauth as oauth_mod

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


def test_deepseek_api_key_env_is_the_default(isolated):
    """A DEEPSEEK_API_KEY in env/.env makes DeepSeek the CLI default."""
    isolated.setenv("DEEPSEEK_API_KEY", "ds-test-key")
    key, provider, model, base = cfg.resolve_credentials()
    assert key == "ds-test-key"
    assert provider == "openai_compat"
    assert model == "deepseek-v4-flash"
    assert base == "https://api.deepseek.com"


def test_deepseek_model_and_base_env_overrides(isolated):
    isolated.setenv("DEEPSEEK_API_KEY", "ds-test-key")
    isolated.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    isolated.setenv("DEEPSEEK_BASE_URL", "https://example.test/v1")
    _, _, model, base = cfg.resolve_credentials()
    assert (model, base) == ("deepseek-reasoner", "https://example.test/v1")


def test_openrouter_only_is_the_fallback(isolated):
    """With no DeepSeek/Anthropic key, OPENROUTER_API_KEY is used."""
    isolated.setenv("OPENROUTER_API_KEY", "or-test-key")
    key, provider, model, base = cfg.resolve_credentials()
    assert key == "or-test-key"
    assert provider == "openrouter"
    assert base == "https://openrouter.ai/api/v1"
    assert model.startswith("anthropic/")  # default model auto-prefixed


def test_vector_model_env_respected_for_openrouter(isolated):
    isolated.setenv("OPENROUTER_API_KEY", "or-test-key")
    isolated.setenv("VECTOR_MODEL", "qwen/qwen2.5-vl-72b-instruct")
    _, provider, model, _ = cfg.resolve_credentials()
    assert provider == "openrouter"
    assert model == "qwen/qwen2.5-vl-72b-instruct"  # has a slash -> not re-prefixed


def test_vector_provider_openrouter_opts_out_of_deepseek(isolated):
    """VECTOR_PROVIDER=openrouter forces the fallback even when a DeepSeek key exists."""
    isolated.setenv("DEEPSEEK_API_KEY", "ds-test-key")
    isolated.setenv("OPENROUTER_API_KEY", "or-test-key")
    isolated.setenv("VECTOR_PROVIDER", "openrouter")
    key, provider, _, _ = cfg.resolve_credentials()
    assert provider == "openrouter"
    assert key == "or-test-key"


def test_forced_openrouter_default_model_has_endpoints(isolated):
    """VECTOR_PROVIDER=openrouter with no VECTOR_MODEL must default to a model that
    actually has OpenRouter endpoints, NOT the old anthropic/claude-sonnet-4-6 that
    returned 404 'No endpoints found' (the third-brain blocker). The default is a
    fully-qualified, cross-family id (openai/...), never bare-anthropic-prefixed."""
    isolated.setenv("OPENROUTER_API_KEY", "or-test-key")
    isolated.setenv("VECTOR_PROVIDER", "openrouter")
    _, provider, model, base = cfg.resolve_credentials()
    assert provider == "openrouter"
    assert model == "openai/gpt-4o-mini"
    assert not model.startswith("anthropic/")  # the 404 default is gone
    assert base == "https://openrouter.ai/api/v1"


def test_forced_openrouter_respects_explicit_vector_model(isolated):
    """An explicit VECTOR_MODEL still wins over the new default (BYO any model)."""
    isolated.setenv("OPENROUTER_API_KEY", "or-test-key")
    isolated.setenv("VECTOR_PROVIDER", "openrouter")
    isolated.setenv("VECTOR_MODEL", "meta-llama/llama-3.3-70b-instruct")
    _, provider, model, _ = cfg.resolve_credentials()
    assert provider == "openrouter"
    assert model == "meta-llama/llama-3.3-70b-instruct"


def test_anthropic_api_key_env(isolated):
    isolated.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    key, provider, model, _ = cfg.resolve_credentials()
    assert key == "sk-ant-test"
    assert provider == "anthropic"
    assert "/" not in model  # anthropic-direct strips any prefix


def test_config_file_deepseek_backcompat(isolated):
    """No env keys: a legacy ~/.vector/config.yaml provider:deepseek still resolves."""
    isolated.setattr(
        cfg,
        "load_config",
        lambda *a, **k: {
            "provider": "deepseek",
            "deepseek_api_key": "ds-cfg-key",
            "deepseek_model": "deepseek-v4-flash",
        },
    )
    key, provider, model, base = cfg.resolve_credentials()
    assert key == "ds-cfg-key"
    assert provider == "openai_compat"
    assert model == "deepseek-v4-flash"
    assert base == "https://api.deepseek.com"


def test_no_credentials_is_inert(isolated):
    """No env, no config, no OAuth -> empty key, anthropic default (byte-identical fallthrough)."""
    key, provider, _, _ = cfg.resolve_credentials()
    assert key == ""
    assert provider == "anthropic"
