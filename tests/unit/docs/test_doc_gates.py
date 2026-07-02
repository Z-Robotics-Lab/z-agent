# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""CI doc/ledger gate: `loop/check.sh --ci` must be green on every commit.

The enforcement law lives in ``loop/check.sh`` (size caps, allowlist, append-only
DECISIONS/ledger, spine gate, BOARD regen-match, rot greps, wiring anchors); this test is
the CI call site — the third of the three unavoidable points (agent at RECORD, supervisor
post-round, CI). It extends the one doc gate with a proven fire record
(``test_doc_drift_gate.py``): the only doc fact that never rots is the one CI blocks on.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_CHECK = _ROOT / "loop" / "check.sh"


def test_doc_gates_ci_green():
    if shutil.which("bash") is None or shutil.which("git") is None:
        pytest.skip("bash or git unavailable — doc gate needs both")
    if not (_ROOT / ".git").exists():
        pytest.skip("not a git checkout — doc gate reads git state")
    assert _CHECK.exists(), "loop/check.sh missing — the doc/ledger enforcement gate is gone"

    proc = subprocess.run(
        ["bash", str(_CHECK), "--ci"],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, (
        "loop/check.sh --ci failed — fix the DOC-GATE FAIL lines, never this test:\n"
        f"{proc.stdout}\n{proc.stderr}"
    )
