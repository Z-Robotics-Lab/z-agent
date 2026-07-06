"""zeno.vcli.paths — ~/.zeno primary home with ~/.vector fallback READ.

Zeno is a fork of vector_os_nano. The product home dir is ``~/.zeno``; the legacy
``~/.vector`` is READ as a fallback so a user upgrading in place keeps their
config / sessions / oauth / traces / history without a manual copy. Writes ALWAYS
go to ``~/.zeno`` (the migration is one-directional forward).

Fully offline — pure path resolution against a monkeypatched HOME; no I/O beyond
creating a couple of marker files under tmp_path.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from zeno.vcli import paths


@pytest.fixture(autouse=True)
def _home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    # Path.home() honours $HOME on POSIX; assert it so the test is meaningful.
    assert Path.home() == tmp_path
    return tmp_path


def test_zeno_home_is_dot_zeno(_home: Path) -> None:
    assert paths.zeno_home() == _home / ".zeno"


def test_legacy_home_is_dot_vector(_home: Path) -> None:
    assert paths.legacy_home() == _home / ".vector"


def test_resolve_read_prefers_zeno_when_present(_home: Path) -> None:
    (_home / ".zeno").mkdir()
    (_home / ".vector").mkdir()
    (_home / ".zeno" / "config.yaml").write_text("z")
    (_home / ".vector" / "config.yaml").write_text("v")
    assert paths.resolve_read("config.yaml") == _home / ".zeno" / "config.yaml"


def test_resolve_read_falls_back_to_vector(_home: Path) -> None:
    # Only the legacy ~/.vector copy exists → the reader must find it (migration path).
    (_home / ".vector").mkdir()
    (_home / ".vector" / "config.yaml").write_text("v")
    assert paths.resolve_read("config.yaml") == _home / ".vector" / "config.yaml"


def test_resolve_read_defaults_to_zeno_when_neither(_home: Path) -> None:
    # Neither present → the ZENO_ path (the default write/create location).
    assert paths.resolve_read("config.yaml") == _home / ".zeno" / "config.yaml"


def test_resolve_read_nested_subpath(_home: Path) -> None:
    (_home / ".vector" / "sessions").mkdir(parents=True)
    (_home / ".vector" / "sessions" / "s1.json").write_text("v")
    assert paths.resolve_read("sessions/s1.json") == (
        _home / ".vector" / "sessions" / "s1.json"
    )


def test_resolve_write_always_zeno(_home: Path) -> None:
    (_home / ".vector").mkdir()
    (_home / ".vector" / "config.yaml").write_text("v")
    # Writes never touch the legacy dir even when only the legacy copy exists.
    assert paths.resolve_write("config.yaml") == _home / ".zeno" / "config.yaml"


def test_resolve_write_creates_parent(_home: Path) -> None:
    p = paths.resolve_write("traces/run.json")
    assert p == _home / ".zeno" / "traces" / "run.json"
    assert p.parent.is_dir()  # parent dir was created


# --- Model-cache resolution (~/.cache/zeno primary, ~/.cache/vector_os fallback) ---

def test_zeno_cache_models_dir(_home: Path) -> None:
    assert paths.zeno_cache_models() == _home / ".cache" / "zeno" / "models"


def test_resolve_cached_model_prefers_zeno(_home: Path) -> None:
    (_home / ".cache" / "zeno" / "models" / "edgetam").mkdir(parents=True)
    (_home / ".cache" / "vector_os" / "models" / "edgetam").mkdir(parents=True)
    assert paths.resolve_cached_model("edgetam") == (
        _home / ".cache" / "zeno" / "models" / "edgetam"
    )


def test_resolve_cached_model_falls_back_to_vector_os(_home: Path) -> None:
    # A model the pre-rename product downloaded lives under ~/.cache/vector_os → reuse it
    # (no re-download).
    (_home / ".cache" / "vector_os" / "models" / "edgetam").mkdir(parents=True)
    assert paths.resolve_cached_model("edgetam") == (
        _home / ".cache" / "vector_os" / "models" / "edgetam"
    )


def test_resolve_cached_model_defaults_to_zeno(_home: Path) -> None:
    # Neither cached → the ZENO_ path (the error message then points at the new location).
    assert paths.resolve_cached_model("edgetam") == (
        _home / ".cache" / "zeno" / "models" / "edgetam"
    )


# --- migrate_and_resolve: one-time forward copy so SceneGraph/terrain load old data
#     then always WRITE to ~/.zeno (persist_path is one path for load AND save). ---

def test_migrate_and_resolve_copies_legacy_to_zeno(_home: Path) -> None:
    (_home / ".vector").mkdir()
    (_home / ".vector" / "scene_graph.yaml").write_text("old-graph")
    result = paths.migrate_and_resolve("scene_graph.yaml")
    # Always returns the ~/.zeno path (so subsequent SAVES land there)...
    assert result == _home / ".zeno" / "scene_graph.yaml"
    # ...and the legacy content was migrated forward so a LOAD sees it.
    assert result.read_text() == "old-graph"
    # The legacy copy is left intact (non-destructive migration).
    assert (_home / ".vector" / "scene_graph.yaml").read_text() == "old-graph"


def test_migrate_and_resolve_prefers_existing_zeno(_home: Path) -> None:
    (_home / ".zeno").mkdir()
    (_home / ".zeno" / "scene_graph.yaml").write_text("new-graph")
    (_home / ".vector").mkdir()
    (_home / ".vector" / "scene_graph.yaml").write_text("old-graph")
    result = paths.migrate_and_resolve("scene_graph.yaml")
    assert result == _home / ".zeno" / "scene_graph.yaml"
    assert result.read_text() == "new-graph"  # ~/.zeno wins, no overwrite


def test_migrate_and_resolve_no_legacy_returns_zeno(_home: Path) -> None:
    result = paths.migrate_and_resolve("scene_graph.yaml")
    assert result == _home / ".zeno" / "scene_graph.yaml"
    assert not result.exists()  # nothing to migrate; caller creates it on save
