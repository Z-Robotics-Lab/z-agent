# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Persistent configuration for Vector CLI.

Stores API keys, default model, provider preferences in ~/.vector/config.yaml.
Also discovers Claude Code OAuth tokens from ~/.claude/.credentials.json.

Config file location: ~/.vector/config.yaml
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path.home() / ".vector"
_CONFIG_PATH = _CONFIG_DIR / "config.yaml"
_CLAUDE_CREDS_PATH = Path.home() / ".claude" / ".credentials.json"

# Defaults when no config file exists
_DEFAULTS: dict[str, Any] = {
    "provider": "openrouter",
    "model": "claude-haiku-4-5",
    "anthropic_api_key": "",
    "openrouter_api_key": "",
    "base_url": "",
}


def load_config() -> dict[str, Any]:
    """Load config from ~/.vector/config.yaml, merging with defaults."""
    config = dict(_DEFAULTS)
    if not _CONFIG_PATH.exists():
        return config
    try:
        import yaml  # noqa: PLC0415
        raw = yaml.safe_load(_CONFIG_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            config.update(raw)
    except ImportError:
        # No PyYAML — fall back to simple key=value parsing
        config.update(_load_simple(_CONFIG_PATH))
    except Exception:
        pass
    return config


def save_config(config: dict[str, Any]) -> None:
    """Write config to ~/.vector/config.yaml."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import yaml  # noqa: PLC0415
        _CONFIG_PATH.write_text(
            yaml.dump(config, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )
    except ImportError:
        _save_simple(_CONFIG_PATH, config)


def _load_simple(path: Path) -> dict[str, str]:
    """Parse a simple key: value file (YAML subset)."""
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            result[k.strip()] = v.strip().strip("'\"")
    return result


def _save_simple(path: Path, config: dict[str, Any]) -> None:
    """Write a simple key: value file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k}: {v}" for k, v in config.items() if v]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_claude_oauth() -> dict[str, Any] | None:
    """Load Claude Code OAuth credentials from ~/.claude/.credentials.json.

    Returns the OAuth data dict if valid and not expired, else None.
    """
    if not _CLAUDE_CREDS_PATH.exists():
        return None
    try:
        raw = json.loads(_CLAUDE_CREDS_PATH.read_text(encoding="utf-8"))
        oauth = raw.get("claudeAiOauth")
        if not isinstance(oauth, dict):
            return None
        access_token = oauth.get("accessToken", "")
        expires_at = oauth.get("expiresAt", 0)
        if not access_token:
            return None
        # Check expiry (expiresAt is ms timestamp)
        if expires_at and time.time() * 1000 > expires_at:
            return None
        return oauth
    except (json.JSONDecodeError, OSError, KeyError):
        return None


def resolve_credentials(
    cli_api_key: str | None = None,
    cli_base_url: str | None = None,
    cli_model: str | None = None,
) -> tuple[str, str, str, str | None]:
    """Resolve API key, provider, model, and base_url from all sources.

    Priority: CLI flags > DeepSeek (env/config) > Vector OAuth > Claude OAuth >
              ANTHROPIC_API_KEY (env/config) > OPENROUTER_API_KEY (env/config).

    A repo-root .env is loaded first so env vars set there participate in the
    same priority order as real env vars. load_dotenv() is a no-op when no .env
    exists, so all existing behaviour is byte-identical when .env is absent.

    Returns:
        (api_key, provider, model, base_url)
    """
    import os  # noqa: PLC0415
    from dotenv import load_dotenv  # noqa: PLC0415

    # Load repo-root .env into the process environment BEFORE reading any env var.
    # Standard find-from-cwd behaviour: walks up from cwd until it finds .env.
    # No-op when absent; existing env vars are NOT overwritten (override=False default).
    load_dotenv()

    config = load_config()

    api_key = cli_api_key or ""
    provider = "anthropic"
    base_url = cli_base_url
    _forced_provider = os.environ.get("VECTOR_PROVIDER", "").lower()

    # Qwen / DashScope (阿里百炼) branch: OpenAI-compatible. Activated by VECTOR_PROVIDER=qwen
    # (or config provider: qwen). Routing brain runs on Qwen text models via DashScope with the
    # QWEN_API_KEY — used when DeepSeek-direct is network-blocked AND the OpenRouter credit is
    # exhausted (the vision judge uses the same key/endpoint via VECTOR_JUDGE_*). China endpoint.
    qwen_key = os.environ.get("QWEN_API_KEY", "") or config.get("qwen_api_key", "")
    if not cli_api_key and _forced_provider == "qwen" and qwen_key:
        qwen_model = (
            cli_model
            or os.environ.get("QWEN_MODEL")
            or config.get("qwen_model")
            or "qwen-plus"
        )
        qwen_base = (
            cli_base_url
            or os.environ.get("QWEN_BASE_URL")
            or config.get("qwen_base_url")
            or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        return qwen_key, "openai_compat", qwen_model, qwen_base

    # DeepSeek branch: OpenAI-compatible provider (model ids carry no slash and must
    # NOT be mangled by the OpenRouter "anthropic/" prefix below).  Activated when:
    #   - DEEPSEEK_API_KEY is present in env/.env, OR
    #   - config explicitly sets ``provider: deepseek`` with a key.
    # Opt-out: if VECTOR_PROVIDER is explicitly set to 'openrouter' or 'anthropic',
    # skip this branch so the user can force the fallback even when a DS key exists.
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "") or config.get("deepseek_api_key", "")
    _forced_provider = os.environ.get("VECTOR_PROVIDER", "").lower()
    deepseek_selected = (
        _forced_provider == "deepseek"
        or bool(os.environ.get("DEEPSEEK_API_KEY", ""))
        or config.get("provider") == "deepseek"
    )
    deepseek_opted_out = _forced_provider in ("openrouter", "anthropic")

    if not cli_api_key and deepseek_selected and not deepseek_opted_out and ds_key:
        ds_model = (
            cli_model
            or os.environ.get("DEEPSEEK_MODEL")
            or config.get("deepseek_model")
            or "deepseek-v4-flash"
        )
        ds_base = (
            cli_base_url
            or os.environ.get("DEEPSEEK_BASE_URL")
            or config.get("deepseek_base_url")
            or "https://api.deepseek.com"
        )
        return ds_key, "openai_compat", ds_model, ds_base

    # Forced OpenRouter: VECTOR_PROVIDER=openrouter is a HARD override — it wins
    # over the OAuth / ANTHROPIC branches below, not just the DeepSeek branch.
    # Without this, a present Claude OAuth credential (sk-ant-oat...) silently
    # hijacks resolution to anthropic-direct even when the operator explicitly
    # forced OpenRouter because anthropic/DeepSeek-direct are network-blocked
    # (the bare-cli fetch-acceptance path). A CLI --api-key still wins above this.
    if _forced_provider == "openrouter" and not cli_api_key:
        or_key = os.environ.get("OPENROUTER_API_KEY", "") or config.get("openrouter_api_key", "")
        if or_key:
            or_model = cli_model or os.environ.get("VECTOR_MODEL") or config.get("model", "claude-sonnet-4-6")
            if "/" not in or_model:
                or_model = f"anthropic/{or_model}"
            or_base = cli_base_url or config.get("base_url", "") or "https://openrouter.ai/api/v1"
            return or_key, "openrouter", or_model, or_base

    if not api_key:
        # Vector CLI's own OAuth credentials (independent rate limits)
        from vector_os_nano.vcli.oauth import load_credentials
        own_creds = load_credentials()
        if own_creds:
            api_key = own_creds["accessToken"]
            provider = "anthropic"

    if not api_key:
        # Claude Code OAuth fallback (shared rate limits)
        oauth = load_claude_oauth()
        if oauth:
            api_key = oauth["accessToken"]
            provider = "anthropic"

    if not api_key:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        api_key = config.get("anthropic_api_key", "")

    if api_key:
        provider = "anthropic"
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            api_key = config.get("openrouter_api_key", "")
        if api_key:
            provider = "openrouter"
            if not base_url:
                base_url = config.get("base_url", "") or "https://openrouter.ai/api/v1"

    # Model resolution: CLI flag > VECTOR_MODEL env > config > default
    model = cli_model or os.environ.get("VECTOR_MODEL") or config.get("model", "claude-sonnet-4-6")

    # Auto-prefix for OpenRouter, strip prefix for Anthropic direct
    if provider == "openrouter" and "/" not in model:
        model = f"anthropic/{model}"
    elif provider == "anthropic" and "/" in model:
        model = model.split("/", 1)[1]

    return api_key, provider, model, base_url or None
