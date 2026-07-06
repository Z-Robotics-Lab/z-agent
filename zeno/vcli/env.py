"""Single source of truth for ZENO_-first / VECTOR_-fallback env resolution.

Zeno is a fork of vector_os_nano. Product env vars are ``ZENO_<NAME>``; the
legacy ``VECTOR_<NAME>`` names are kept as a silent fallback because external
scripts, the upstream .env, and sibling harnesses still set them. Resolution is
additive: read ZENO_ first, fall back to VECTOR_, first present-and-non-empty
wins.

Every read point in the product routes through :func:`read_env` so the fallback
rule lives in exactly one place (no ~20 scattered ``os.environ.get('VECTOR_..')``
that silently miss the ZENO_ name). ``vcli/cli.py`` and ``vcli/config.py`` keep
their own module-local ``_env`` names as thin delegates that only differ in the
default they return (``None`` vs ``''``) to preserve their historic call-site
semantics.
"""
from __future__ import annotations

import os

# Read order: product name first, legacy fork name as fallback. Additive — never
# drop the VECTOR_ prefix (upstream .env / external harnesses still set it).
_PREFIXES: tuple[str, ...] = ("ZENO_", "VECTOR_")


def read_env(suffix: str, default: str | None = None) -> str | None:
    """Read ``ZENO_<suffix>`` then ``VECTOR_<suffix>``; first non-empty wins.

    ``suffix`` is the bare name, e.g. ``read_env("SIM_WITH_ARM")`` reads
    ``ZENO_SIM_WITH_ARM`` then ``VECTOR_SIM_WITH_ARM``. A set-but-empty ZENO_
    value does NOT mask a real VECTOR_ value — it falls through (this mirrors the
    historic ``.get(name, "").strip()`` guards the call sites relied on). Returns
    ``default`` when neither name is present-and-non-empty.
    """
    for prefix in _PREFIXES:
        val = os.environ.get(prefix + suffix)
        if val:
            return val
    return default
