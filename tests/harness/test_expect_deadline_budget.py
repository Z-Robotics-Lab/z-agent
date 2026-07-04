"""REAL-pexpect integration for the R296/E87 deadline-aware verdict-expect clamp.

Not a capability acceptance (no sim/NL) — this exercises the ACTUAL failure mechanism that
orphaned R294's sim into R296's quarantine: a per-turn ``child.expect([grounded, TIMEOUT],
timeout=600)`` against a REPL that never grounds. Pre-fix that expect blocks the full 600s and
out-waits the round; post-fix ``budget_timeout`` clamps it to ``deadline - margin`` so the
harness reaches teardown first. We drive a real ``pexpect.spawn`` on a child that emits chatter
but never ``grounded)`` and assert the clamped wait returns within a couple seconds under a tight
injected deadline — the real code path, deterministic, no MuJoCo.
"""
from __future__ import annotations

import time

import pexpect
import pytest

from tools.acceptance.vlm_guard import budget_timeout


def _spawn_never_grounds() -> pexpect.spawn:
    # A child that prints non-verdict chatter forever (the brain-thrash signature: skills fire,
    # but ``verified=... grounded)`` never appears) then would run for minutes.
    return pexpect.spawn(
        "bash", ["-c", "for i in $(seq 1 600); do echo native look step $i; sleep 0.2; done"],
        encoding="utf-8", timeout=600,
    )


@pytest.mark.integration
def test_expect_returns_at_clamped_budget_not_default() -> None:
    child = _spawn_never_grounds()
    try:
        now = int(time.time())
        # Round ends in 121s; margin 120 -> budget 1s (below floor -> floor=15... too slow for a
        # test). Use a small floor so the real clamp is a couple seconds, exercising the SAME
        # code path a 600s default would, just fast.
        clamped = budget_timeout(600, now=now, deadline_epoch=now + 122, margin=120, floor=2)
        assert clamped == 2, clamped
        t0 = time.time()
        idx = child.expect([r"grounded\)", pexpect.TIMEOUT], timeout=clamped)
        elapsed = time.time() - t0
        # It TIMED OUT (never grounded), and it did so at the clamped budget — NOT the 600s
        # default that would orphan the sim past the round deadline.
        assert idx == 1, "expected TIMEOUT (child never emits grounded)"
        assert elapsed < 10, f"expect out-waited the clamp ({elapsed:.1f}s) — orphan risk"
    finally:
        child.close(force=True)
    assert not child.isalive(), "child not torn down after close(force=True)"


@pytest.mark.integration
def test_ample_deadline_keeps_full_default_available() -> None:
    # With an hour of headroom the clamp is a no-op: the harness keeps its full patience so a
    # slow-but-real grounding turn is never cut short.
    now = int(time.time())
    assert budget_timeout(600, now=now, deadline_epoch=now + 3600) == 600
