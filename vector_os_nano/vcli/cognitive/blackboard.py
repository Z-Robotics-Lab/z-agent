# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Blackboard — run-scoped store for per-step structured observations.

The VGG executor used to discard every step's structured output. The Blackboard
captures each step's observation dict (keyed by sub-goal name) so later steps can
reference earlier outputs (consumption is wired in Stage 1b; this module only
captures + defines the reference-resolution syntax).

Reference syntax (resolved by :meth:`Blackboard.resolve`):

    ``${step_name.key}``                 -> blackboard[step_name]["key"]
    ``${step_name.key.subkey}``          -> nested dict traversal
    ``${detect_all.objects.0.id}``       -> integer index into a list

SAFETY: ``resolve`` performs *pure* dict / list traversal only. It NEVER calls
``eval``/``exec``/``getattr`` on arbitrary code, and never dereferences object
attributes. A path that cannot be resolved by plain dict-key / list-index lookup
is returned unchanged (the original ``${...}`` text), with a debug log. This makes
an injection payload such as ``"${__import__('os')}"`` a harmless passthrough.
"""
from __future__ import annotations

import logging
import re
from typing import Any

_LOG = logging.getLogger(__name__)

# Matches a single ``${...}`` reference. The inner group is the raw path text;
# it is parsed by structural traversal only — never evaluated.
_REF_RE = re.compile(r"\$\{([^}]*)\}")

# A bare string that is EXACTLY one reference, e.g. ``"${a.b}"``. When the whole
# string is one reference the resolved value keeps its native type (dict / list /
# int / ...); otherwise references embedded in a larger string are stringified.
_EXACT_REF_RE = re.compile(r"^\$\{([^}]*)\}$")


class Blackboard:
    """Mutable, run-scoped map of ``sub_goal_name -> observation dict``."""

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Capture / read
    # ------------------------------------------------------------------

    def put(self, step_name: str, data: dict) -> None:
        """Store *data* under *step_name*, overwriting any prior entry.

        Non-dict *data* is ignored (the blackboard only holds observation dicts);
        an empty / missing *step_name* is ignored. Both fail soft so a capture
        miss never aborts execution.
        """
        if not isinstance(step_name, str) or not step_name:
            _LOG.debug("Blackboard.put: ignoring empty step_name")
            return
        if not isinstance(data, dict):
            _LOG.debug("Blackboard.put: ignoring non-dict data for %r", step_name)
            return
        self._data[step_name] = data

    def get(self, step_name: str) -> dict | None:
        """Return the observation dict stored under *step_name*, or ``None``."""
        return self._data.get(step_name)

    @property
    def data(self) -> dict[str, dict]:
        """A shallow copy of the full blackboard (top-level dict copied)."""
        return dict(self._data)

    def snapshot(self) -> dict[str, dict]:
        """Alias for :attr:`data` — a shallow read-only copy."""
        return dict(self._data)

    # ------------------------------------------------------------------
    # Reference resolution (pure traversal, no eval)
    # ------------------------------------------------------------------

    def resolve(self, value: Any) -> Any:
        """Recursively resolve ``${path}`` references inside *value*.

        - ``dict`` / ``list`` are walked and rebuilt with resolved members.
        - A ``str`` that is exactly one ``${path}`` is replaced by the looked-up
          value, preserving its native type.
        - A ``str`` containing embedded ``${path}`` substrings has each reference
          substituted (stringified) in place.
        - Any other type is returned unchanged.

        Unknown paths resolve to the original ``${...}`` text (debug-logged). No
        code is ever evaluated.
        """
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve(v) for v in value]
        if isinstance(value, str):
            return self._resolve_str(value)
        return value

    def _resolve_str(self, text: str) -> Any:
        """Resolve references inside a single string."""
        exact = _EXACT_REF_RE.match(text)
        if exact is not None:
            # Whole string is one reference -> preserve native type.
            resolved, found = self._lookup(exact.group(1))
            if not found:
                _LOG.debug("Blackboard.resolve: unknown path %r (passthrough)", exact.group(1))
                return text
            return resolved

        # Embedded references -> stringify each match in place.
        def _sub(match: re.Match[str]) -> str:
            path = match.group(1)
            resolved, found = self._lookup(path)
            if not found:
                _LOG.debug("Blackboard.resolve: unknown path %r (passthrough)", path)
                return match.group(0)
            return str(resolved)

        return _REF_RE.sub(_sub, text)

    def _lookup(self, path: str) -> tuple[Any, bool]:
        """Traverse *path* through the blackboard via dict-key / list-index only.

        Returns ``(value, found)``. ``found`` is False if any segment fails to
        resolve — the caller then falls back to passthrough. Traversal never uses
        ``getattr`` or evaluation; only ``dict.__getitem__`` and
        ``list.__getitem__`` (with integer indices) are used.
        """
        parts = path.split(".")
        if not parts or parts == [""]:
            return None, False

        current: Any = self._data
        for part in parts:
            if isinstance(current, dict):
                if part not in current:
                    return None, False
                current = current[part]
            elif isinstance(current, (list, tuple)):
                idx = self._as_index(part)
                if idx is None or not (-len(current) <= idx < len(current)):
                    return None, False
                current = current[idx]
            else:
                # Cannot traverse further into a scalar -> not found.
                return None, False
        return current, True

    @staticmethod
    def _as_index(part: str) -> int | None:
        """Parse *part* as an integer list index, or ``None`` if not an int."""
        try:
            return int(part)
        except (TypeError, ValueError):
            return None
