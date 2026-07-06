# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""S9 — CI doc-drift gate: the documented DEFAULT producer must match the LIVE default.

The #1 doc-rot failure this guards: ``docs/reference.md`` (formerly docs/cli-tool-system.md)
once described the legacy
IntentRouter + ``VectorEngine.run_turn()`` keyword path as canonical while the live default had
moved to the native model-driven producer. This gate ties the doc's machine-readable claim
(``<!-- doc-drift-gate: default_producer=run_turn_native -->``) to the code's ACTUAL default —
so the documented producer can never silently diverge from the live one again (if S8, or anyone,
flips the default, this fails until the doc is updated).
"""
from __future__ import annotations

import re
from pathlib import Path

from zeno.vcli import cli

_DOC = Path(__file__).resolve().parents[3] / "docs" / "reference.md"


def test_documented_default_producer_matches_live_default(monkeypatch):
    text = _DOC.read_text(encoding="utf-8")
    m = re.search(r"doc-drift-gate:\s*default_producer=(\w+)", text)
    assert m, (
        "docs/reference.md must carry the "
        "`<!-- doc-drift-gate: default_producer=... -->` marker (S9)"
    )
    documented = m.group(1)
    assert documented == "run_turn_native", (
        f"doc claims default_producer={documented!r}; this gate expects the native producer. "
        "If the default producer genuinely changed, update BOTH the code and this gate."
    )

    # The LIVE default must agree: native is the default producer on BOTH the interactive
    # REPL and the -p acceptance path, with no env override. If a future change flips either
    # default without updating the doc marker, this gate fails (the drift it exists to catch).
    for env in (
        "VECTOR_REPL_NATIVE", "VECTOR_PRINT_NATIVE",
        "VECTOR_NATIVE_LOOP", "VECTOR_NATIVE_FIRST",
    ):
        monkeypatch.delenv(env, raising=False)
    assert cli._repl_native_enabled() is True, (
        "doc says default_producer=run_turn_native, but _repl_native_enabled() is False "
        "(REPL no longer defaults to native — doc drift)"
    )
    assert cli._print_native_enabled() is True, (
        "doc says default_producer=run_turn_native, but _print_native_enabled() is False "
        "(-p no longer defaults to native — doc drift)"
    )
