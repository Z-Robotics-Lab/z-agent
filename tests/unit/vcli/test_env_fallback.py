"""ZENO_-first / VECTOR_-fallback env resolution — the single shared read_env().

Every product-namespaced env var read must prefer ``ZENO_<NAME>`` and fall back
to the legacy ``VECTOR_<NAME>`` (external scripts + the upstream .env still set
the VECTOR_ names, so nothing is removed — additive only). This suite pins the
four-cell matrix (ZENO-only / VECTOR-only / both / neither) once, at the seam,
so the ~20 migrated read points never have to re-test the resolution rule.

Fully offline — no sim, no network.
"""
from __future__ import annotations

import pytest

from zeno.vcli.env import read_env


_SUFFIX = "FALLBACK_PROBE"  # a suffix no real code reads, so the host env can't leak in


@pytest.fixture(autouse=True)
def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZENO_" + _SUFFIX, raising=False)
    monkeypatch.delenv("VECTOR_" + _SUFFIX, raising=False)


def test_zeno_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZENO_" + _SUFFIX, "z")
    assert read_env(_SUFFIX) == "z"


def test_vector_only_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    # The load-bearing case: only the legacy VECTOR_ name is set (upstream .env,
    # external harness) — it must still be honoured.
    monkeypatch.setenv("VECTOR_" + _SUFFIX, "v")
    assert read_env(_SUFFIX) == "v"


def test_both_zeno_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZENO_" + _SUFFIX, "z")
    monkeypatch.setenv("VECTOR_" + _SUFFIX, "v")
    assert read_env(_SUFFIX) == "z"


def test_neither_returns_default() -> None:
    assert read_env(_SUFFIX) is None
    assert read_env(_SUFFIX, "d") == "d"


def test_empty_zeno_falls_through_to_vector(monkeypatch: pytest.MonkeyPatch) -> None:
    # A set-but-empty ZENO_ value does NOT mask a real VECTOR_ value; this mirrors
    # the historic ``.get(..., "").strip()`` guards the call sites relied on.
    monkeypatch.setenv("ZENO_" + _SUFFIX, "")
    monkeypatch.setenv("VECTOR_" + _SUFFIX, "v")
    assert read_env(_SUFFIX) == "v"


def test_empty_both_returns_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZENO_" + _SUFFIX, "")
    monkeypatch.setenv("VECTOR_" + _SUFFIX, "")
    assert read_env(_SUFFIX, "d") == "d"


def test_cli_env_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    """cli._env is a thin delegate (default=None) over read_env."""
    from zeno.vcli import cli

    monkeypatch.setenv("VECTOR_" + _SUFFIX, "v")
    assert cli._env(_SUFFIX) == "v"
    monkeypatch.delenv("VECTOR_" + _SUFFIX, raising=False)
    assert cli._env(_SUFFIX) is None


def test_config_env_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    """config._env is a thin delegate (default='') over read_env."""
    from zeno.vcli import config

    monkeypatch.setenv("VECTOR_" + _SUFFIX, "v")
    assert config._env(_SUFFIX) == "v"
    monkeypatch.delenv("VECTOR_" + _SUFFIX, raising=False)
    assert config._env(_SUFFIX) == ""
