# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""go2w_real pre-built map integration — the read-only map/relocalization seam.

CONTEXT (CEO 2026-07-14): pre-built-map relocalization is LIVE. A SLAM prior
lives in ``~/maps/<name>/`` (``<name>.pcd`` for nav, ``start_pose.txt`` line 1 =
the home pose, ``places.json`` = persisted named marks). ``nav.sh start <name>``
launches arise_slam in pure-localization mode against that prior; ``nav.sh``
also writes the ACTIVE map name to ``logs/current_map.txt`` (or ``none`` on a
plain start / stop). This module is the z-agent WORLD's read side of that
contract — every function is best-effort and NEVER raises into a skill.

Three concerns, one small module (repo rule: files under 800 lines):

* BRINGUP RESOLUTION (``resolve_bringup_map``) — turns the optional ``map`` param
  into the nav.sh argument. Explicit name wins; explicit 从零/none/'' = plain
  fresh mapping; unspecified = env ``GO2W_DEFAULT_MAP`` else the built-in
  ``DEFAULT_MAP`` (zeno_office) IF its PCD exists, else plain.
* CURRENT-MAP HANDSHAKE (``current_map``) — reads the active map name nav.sh
  wrote to ``current_map.txt``; ``none``/blank/missing = None. Test override:
  env ``GO2W_CURRENT_MAP_FILE`` points at a temp file.
* PERSISTENT PLACES (``save_places``/``load_places``/``home_place``) — the
  named-mark store under ``~/maps/<map>/places.json`` (atomic tmp+rename;
  schema ``{name: [x, y, yaw]}``) plus the built-in home pose from
  ``start_pose.txt`` line 1 (x y z roll pitch yaw dur -> (x, y, yaw)).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

#: Root of the on-disk map library. Module-level so tests can monkeypatch it to
#: a temp dir (the real path is ~/maps, resolved at import time).
MAPS_ROOT: Path = Path(os.path.expanduser("~/maps"))

#: The built-in default map used when nothing is specified AND its PCD exists.
DEFAULT_MAP: str = "zeno_office"

#: nav.sh's handshake file: the active map name (or 'none'). Env override is the
#: hermetic-test seam (a temp file); default matches nav.sh's LOGDIR.
_CURRENT_MAP_FILE_DEFAULT: str = "~/go2w-nuc/logs/current_map.txt"

#: Params that mean "plain fresh mapping, no pre-built map".
_PLAIN_WORDS: frozenset[str] = frozenset({"从零", "none", "", "从零建图", "fresh"})

#: The persisted named-mark file basename inside a map directory.
PLACES_BASENAME: str = "places.json"


# ---------------------------------------------------------------------------
# Bringup map resolution (Task 1)
# ---------------------------------------------------------------------------


def _pcd_path(name: str) -> Path:
    return MAPS_ROOT / name / f"{name}.pcd"


def map_pcd_exists(name: str) -> bool:
    """True when ``~/maps/<name>/<name>.pcd`` exists (the nav prior)."""
    try:
        return bool(name) and _pcd_path(name).is_file()
    except OSError:  # noqa: BLE001 — filesystem probe must never raise
        return False


def resolve_bringup_map(param: str | None) -> str | None:
    """Resolve the bringup ``map`` param to a map NAME or None (plain start).

    * explicit name (with an existing PCD) wins;
    * explicit 从零/none/'' -> None (plain fresh mapping);
    * unspecified (None) -> env GO2W_DEFAULT_MAP, else DEFAULT_MAP, but only
      when that map's PCD actually exists — otherwise None (plain).

    A non-empty explicit name whose PCD is missing still resolves to that name:
    nav.sh itself refuses missing priors with a helpful error (available maps),
    which the skill surfaces honestly rather than silently mapping fresh.
    """
    if param is not None:
        label = str(param).strip()
        if label.lower() in _PLAIN_WORDS or label in _PLAIN_WORDS:
            return None
        return label
    # Unspecified: env default, else the built-in default map when present.
    env = os.environ.get("GO2W_DEFAULT_MAP", "").strip()
    if env:
        if env.lower() in _PLAIN_WORDS:
            return None
        return env if map_pcd_exists(env) else None
    return DEFAULT_MAP if map_pcd_exists(DEFAULT_MAP) else None


# ---------------------------------------------------------------------------
# Current-map handshake (Task 2 — z-agent reads what nav.sh writes)
# ---------------------------------------------------------------------------


def current_map_file() -> Path:
    """Path to nav.sh's current_map.txt (env GO2W_CURRENT_MAP_FILE override)."""
    raw = os.environ.get("GO2W_CURRENT_MAP_FILE", "").strip() \
        or _CURRENT_MAP_FILE_DEFAULT
    return Path(os.path.expanduser(raw))


def current_map() -> str | None:
    """The ACTIVE map name nav.sh wrote, or None (none/blank/missing/error).

    This is the honesty gate for persistence: a mark only survives to disk when
    a pre-built map is truly active (localization mode). A fresh-mapping session
    ('none') or a down stack (missing file) reads None -> session-only places.
    """
    try:
        text = current_map_file().read_text(encoding="utf-8").strip()
    except (OSError, ValueError):  # missing / unreadable
        return None
    if not text or text.lower() == "none":
        return None
    # Guard against a partially-written file (first whitespace-delimited token).
    return text.split()[0]


# ---------------------------------------------------------------------------
# Persistent named places (Task 3)
# ---------------------------------------------------------------------------


def places_json_path(map_name: str) -> Path:
    return MAPS_ROOT / map_name / PLACES_BASENAME


def load_places(map_name: str) -> dict[str, tuple[float, float, float]]:
    """Load persisted named marks {name: (x, y, yaw)} — {} on any problem.

    Corrupt / missing / wrong-shaped entries are skipped, never raised: a bad
    places.json must degrade to a memory-less (but working) session.
    """
    try:
        raw = json.loads(places_json_path(map_name).read_text(encoding="utf-8"))
    except (OSError, ValueError):  # missing / corrupt JSON
        return {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, tuple[float, float, float]] = {}
    for name, triple in raw.items():
        try:
            x, y, yaw = (float(triple[0]), float(triple[1]), float(triple[2]))
        except (TypeError, ValueError, IndexError):
            continue  # skip a malformed entry, keep the rest
        out[str(name)] = (x, y, yaw)
    return out


def save_places(
        map_name: str,
        marks: dict[str, tuple[float, float, float]]) -> bool:
    """Atomically persist named marks to ~/maps/<map>/places.json (tmp+rename).

    Schema: {name: [x, y, yaw]}. Best-effort: returns False (never raises) when
    the map dir is absent / unwritable — a failed save must not break a mark.
    """
    path = places_json_path(map_name)
    tmp = path.with_name(f".{PLACES_BASENAME}.tmp.{os.getpid()}")
    try:
        if not path.parent.is_dir():
            return False
        payload = {str(n): [float(p[0]), float(p[1]), float(p[2])]
                   for n, p in marks.items()}
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, path)  # atomic on POSIX — no partial file ever read
        return True
    except (OSError, ValueError, TypeError) as exc:  # noqa: BLE001
        logger.warning("go2w_real: save_places(%s) failed: %s", map_name, exc)
        try:  # leave no half-written temp file behind
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        return False


def clear_places(map_name: str) -> int:
    """Wipe the persisted named marks for *map_name*; return the count removed.

    The /clean REPL command's disk half (CEO 2026-07-14). Backs the current
    ``places.json`` up to ``places.json.bak`` (OVERWRITING any old backup) and
    then removes the file, so the store reads empty on the next load. The
    built-in ``home``/``家`` place is NOT stored here (it derives from
    ``start_pose.txt``), so it survives a clear and reloads via
    :func:`home_place` — nothing to do for it.

    Best-effort: no places.json / missing map dir -> 0 (no backup, no raise);
    a backup or unlink failure is logged and yields 0 rather than propagating.
    """
    path = places_json_path(map_name)
    try:
        if not path.is_file():
            return 0
        count = len(load_places(map_name))
        bak = path.with_name(f"{PLACES_BASENAME}.bak")
        os.replace(path, bak)  # atomic move = backup + delete in one step
        return count
    except OSError as exc:  # noqa: BLE001 — a failed clear must not crash /clean
        logger.warning("go2w_real: clear_places(%s) failed: %s", map_name, exc)
        return 0


def home_place(map_name: str) -> tuple[float, float, float] | None:
    """The built-in 'home' pose from start_pose.txt line 1, or None.

    Format: ``x y z roll pitch yaw dur`` -> (x, y, yaw). Missing / malformed
    file returns None (no home injected) rather than raising.
    """
    try:
        line = (MAPS_ROOT / map_name / "start_pose.txt").read_text(
            encoding="utf-8").splitlines()[0]
        parts = line.split()
        return (float(parts[0]), float(parts[1]), float(parts[5]))
    except (OSError, ValueError, IndexError):
        return None
