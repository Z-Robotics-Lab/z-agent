# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Operator-log hygiene pin — tests must NEVER write the real zeno_agent.log.

Field pollution (2026-07-13 15:00-15:24): fake test events (open_viz pid 4242
'teleport' blocks, a mark 'A' goto with fake-driver coordinates) landed in the
REAL operator log because some test files lacked the oplog-redirect fixture.
The redirect is now an AUTOUSE fixture in tests/vcli/conftest.py; this file
pins that during any test the module-level default path is never the real
``~/go2w-nuc`` path and that oplog writes land in the per-test tmp_path.
"""

from __future__ import annotations

import os


def test_oplog_path_is_never_the_real_operator_log_during_tests():
    from zeno.vcli.worlds import go2w_real_diag as d

    real_root = os.path.expanduser("~/go2w-nuc")
    assert not d._OPLOG_PATH.startswith(real_root), (
        "the autouse conftest redirect is missing — tests would pollute the "
        "REAL operator log ~/go2w-nuc/logs/zeno_agent.log (field pollution "
        "2026-07-13 15:00-15:24)")


def test_oplog_writes_land_in_the_per_test_tmp_path(tmp_path):
    from zeno.vcli.worlds import go2w_real_diag as d

    d.oplog("test", "hygiene", "pin line — must land in tmp_path")
    target = tmp_path / "test_agent.log"
    assert target.exists(), (
        "oplog() must write the conftest-redirected tmp_path file")
    assert "pin line" in target.read_text(encoding="utf-8")
