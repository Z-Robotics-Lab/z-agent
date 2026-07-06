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


# --- Migrated read-point defaults: the behavior-sensitive ones (default-value +
#     truth semantics must be identical to the pre-migration os.environ.get calls). ---

class TestMigratedDefaults:
    """Pin the default-value + truth semantics of the behavior-sensitive reads that
    moved onto read_env. A regression here would silently flip a security gate or a
    default-on capability."""

    def test_dev_allow_tests_gate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from zeno.vcli.worlds import dev

        monkeypatch.delenv("ZENO_DEV_ALLOW_TESTS", raising=False)
        monkeypatch.delenv("VECTOR_DEV_ALLOW_TESTS", raising=False)
        assert dev._tests_allowed() is False  # default: gate CLOSED
        monkeypatch.setenv("VECTOR_DEV_ALLOW_TESTS", "1")  # legacy fallback still opens it
        assert dev._tests_allowed() is True
        monkeypatch.delenv("VECTOR_DEV_ALLOW_TESTS", raising=False)
        monkeypatch.setenv("ZENO_DEV_ALLOW_TESTS", "1")  # product name opens it
        assert dev._tests_allowed() is True

    def test_shared_executor_default_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # read_env("SHARED_EXECUTOR", "1") == "1" — default ON, == "0" opt-out unchanged.
        monkeypatch.delenv("ZENO_SHARED_EXECUTOR", raising=False)
        monkeypatch.delenv("VECTOR_SHARED_EXECUTOR", raising=False)
        assert (read_env("SHARED_EXECUTOR", "1") == "1") is True  # default on
        monkeypatch.setenv("VECTOR_SHARED_EXECUTOR", "0")
        assert (read_env("SHARED_EXECUTOR", "1") == "1") is False  # legacy opt-out
        monkeypatch.setenv("ZENO_SHARED_EXECUTOR", "1")  # product name wins
        assert (read_env("SHARED_EXECUTOR", "1") == "1") is True

    def test_enable_manipulation_default_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ZENO_ENABLE_MANIPULATION", raising=False)
        monkeypatch.delenv("VECTOR_ENABLE_MANIPULATION", raising=False)
        assert (read_env("ENABLE_MANIPULATION", "1") == "0") is False  # default: NOT skipped
        monkeypatch.setenv("VECTOR_ENABLE_MANIPULATION", "0")
        assert (read_env("ENABLE_MANIPULATION", "1") == "0") is True  # legacy opt-out
        monkeypatch.delenv("VECTOR_ENABLE_MANIPULATION", raising=False)
        monkeypatch.setenv("ZENO_ENABLE_MANIPULATION", "0")
        assert (read_env("ENABLE_MANIPULATION", "1") == "0") is True

    def test_max_tokens_default_and_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("ZENO_MAX_TOKENS", raising=False)
        monkeypatch.delenv("VECTOR_MAX_TOKENS", raising=False)
        assert int(read_env("MAX_TOKENS", "8000")) == 8000  # default preserved
        monkeypatch.setenv("VECTOR_MAX_TOKENS", "4096")
        assert int(read_env("MAX_TOKENS", "8000")) == 4096  # legacy fallback
        monkeypatch.setenv("ZENO_MAX_TOKENS", "2048")
        assert int(read_env("MAX_TOKENS", "8000")) == 2048  # product name wins
