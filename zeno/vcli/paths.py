# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Single source of truth for Zeno's per-user home + cache directories.

Zeno is a fork of vector_os_nano. The product home dir is ``~/.zeno`` and the
model cache is ``~/.cache/zeno``. The legacy ``~/.vector`` / ``~/.cache/vector_os``
locations are READ as a fallback so a user upgrading in place keeps their config,
sessions, oauth token, traces, personality, scene graph, terrain map, REPL
history and downloaded models — no manual copy. Writes ALWAYS go to the ZENO_
location (the migration is one-directional forward; the old dir is never written).

All resolution is LAZY (``Path.home()`` is read on each call, never at import) so
tests that monkeypatch ``$HOME`` and the pty/sandbox harnesses see the right dir.

Every call site that used to hardcode ``Path.home() / ".vector"`` /
``os.path.expanduser("~/.vector/...")`` / ``~/.cache/vector_os`` routes through
here, so the primary-name + fallback-read rule lives in exactly one place.
"""
from __future__ import annotations

from pathlib import Path

# Directory names — the ZENO_ product name is primary, the legacy fork name is the
# read-only fallback. These are the ONLY places the literals appear.
_ZENO_HOME_NAME = ".zeno"
_LEGACY_HOME_NAME = ".vector"
_ZENO_CACHE_REL = ("zeno", "models")
_LEGACY_CACHE_REL = ("vector_os", "models")


def zeno_home() -> Path:
    """The product home dir ``~/.zeno`` (the WRITE root). Lazy: reads $HOME now."""
    return Path.home() / _ZENO_HOME_NAME


def legacy_home() -> Path:
    """The legacy fork home dir ``~/.vector`` (READ-only fallback)."""
    return Path.home() / _LEGACY_HOME_NAME


def resolve_read(subpath: str | Path) -> Path:
    """Path to READ ``subpath`` under the home dir, with legacy fallback.

    Returns ``~/.zeno/<subpath>`` if it exists; else ``~/.vector/<subpath>`` if
    THAT exists (the migration fallback — an upgrade-in-place user's old data);
    else ``~/.zeno/<subpath>`` (the default create/write location). ``subpath`` may
    be nested, e.g. ``"sessions/s1.json"``.
    """
    zeno_path = zeno_home() / subpath
    if zeno_path.exists():
        return zeno_path
    legacy_path = legacy_home() / subpath
    if legacy_path.exists():
        return legacy_path
    return zeno_path


def resolve_write(subpath: str | Path) -> Path:
    """Path to WRITE ``subpath`` under ``~/.zeno`` (parent dir created).

    Always the ZENO_ location — writes never touch the legacy dir. Creates the
    parent directory so callers can write immediately.
    """
    p = zeno_home() / subpath
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def migrate_and_resolve(subpath: str | Path) -> Path:
    """Return the ~/.zeno/<subpath> WRITE path, migrating legacy data forward first.

    For stores that use a SINGLE path for both load and save (e.g. SceneGraph's
    ``persist_path`` loads then saves back), a plain fallback-read would make later
    SAVES land in the legacy dir. Instead: if ~/.zeno/<subpath> is absent but the
    legacy ~/.vector/<subpath> exists, COPY it forward once (non-destructive — the
    legacy copy is left intact), then always return the ~/.zeno path. So a LOAD sees
    the old data and every SAVE writes to ~/.zeno. If neither exists, just return the
    ~/.zeno path (the caller creates it on first save).
    """
    zeno_path = zeno_home() / subpath
    if not zeno_path.exists():
        legacy_path = legacy_home() / subpath
        if legacy_path.exists():
            import shutil  # noqa: PLC0415
            zeno_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_path, zeno_path)
    return zeno_path


def zeno_cache_models() -> Path:
    """Model-cache dir ``~/.cache/zeno/models`` (the WRITE root for model downloads)."""
    return Path.home() / ".cache" / _ZENO_CACHE_REL[0] / _ZENO_CACHE_REL[1]


def legacy_cache_models() -> Path:
    """Legacy model-cache dir ``~/.cache/vector_os/models`` (READ-only fallback)."""
    return Path.home() / ".cache" / _LEGACY_CACHE_REL[0] / _LEGACY_CACHE_REL[1]


def resolve_cached_model(name: str) -> Path:
    """Path to a cached model dir ``<name>``, ZENO_ cache first, legacy fallback.

    Returns ``~/.cache/zeno/models/<name>`` if it exists; else the legacy
    ``~/.cache/vector_os/models/<name>`` if THAT exists (avoids a re-download of a
    model the pre-rename product already fetched); else the ZENO_ path (default).
    """
    zeno_path = zeno_cache_models() / name
    if zeno_path.exists():
        return zeno_path
    legacy_path = legacy_cache_models() / name
    if legacy_path.exists():
        return legacy_path
    return zeno_path
