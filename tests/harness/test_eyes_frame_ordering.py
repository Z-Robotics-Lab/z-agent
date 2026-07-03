"""R273/E70 regression: the eyes/judge frame must be taken from the SETTLED post-verdict
state, never mid-flight.

E70 (R272) observed on a place run: `_eyes_frame("place")` was called immediately after the
`grounded)` marker matched but BEFORE `drain_until_quiet`. `capture.snapshot_on_verdict`
writes `verdict_*.png` slightly AFTER that marker, so the pre-drain copy raced the PNG write:
the vision judge graded a STALE frame (a prior turn's) or never fired at all. The seq path
already drained-then-eyes and its judge fired correctly (R270 turn1) — the fetch/place/combo/
quantity paths did eyes-then-drain and lost the judge.

This test is a source-structure guard (the pexpect flow is a module-level script that cannot be
unit-exercised without a live sim): for EVERY `_eyes_frame(...)` call it asserts a
`drain_until_quiet(...)` settle appears between the turn's `child.sendline(...)` and the eyes
frame — i.e. the frame is taken after the scene settles and the verdict PNG is on disk.
Reintroducing the eyes-before-drain anti-pattern fails here.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[2] / "tools" / "acceptance" / "repl_accept.py"


def _call_name(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return ""


def _collect(tree: ast.AST):
    eyes, drains, sends = [], [], []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _call_name(node)
        if name == "_eyes_frame":
            eyes.append(node.lineno)
        elif name == "drain_until_quiet":
            drains.append(node.lineno)
        elif name == "sendline":  # child.sendline(...) — the turn's utterance
            sends.append(node.lineno)
    return sorted(eyes), sorted(drains), sorted(sends)


@pytest.mark.unit
def test_every_eyes_frame_follows_a_settle_after_its_send():
    """Between a turn's sendline and its _eyes_frame there MUST be a drain_until_quiet."""
    tree = ast.parse(HARNESS.read_text(encoding="utf-8"))
    eyes, drains, sends = _collect(tree)

    assert eyes, "no _eyes_frame calls found — test is mis-targeted"

    offenders = []
    for e_line in eyes:
        prior_sends = [s for s in sends if s < e_line]
        # The turn that owns this eyes frame is gated by the most recent sendline above it.
        turn_send = max(prior_sends) if prior_sends else 0
        settled = any(turn_send < d < e_line for d in drains)
        if not settled:
            offenders.append(e_line)

    assert not offenders, (
        "E70 regression: _eyes_frame at line(s) "
        f"{offenders} is NOT preceded by a drain_until_quiet settle after its turn's "
        "sendline — the judge will race the verdict_*.png write (grade a stale frame or "
        "never fire). Move the eyes/judge frame AFTER drain_until_quiet."
    )
