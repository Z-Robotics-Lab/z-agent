# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""tests/vcli conftest — operator-log hygiene (autouse oplog redirect).

Field pollution (2026-07-13 15:00-15:24): the REAL operator log
``~/go2w-nuc/logs/zeno_agent.log`` accumulated fake test events (open_viz
pid-4242 'teleport' blocks; a mark 'A' (3.00,4.00) goto from fake-driver
coordinates) because newer test files lacked the per-file oplog-redirect
fixture. The redirect lives HERE now, autouse: EVERY test under tests/vcli
writes its oplog to tmp_path — the real operator log is never touched.
Pinned by tests/vcli/test_oplog_hygiene.py.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _redirect_oplog(tmp_path):
    """Every vcli test oplogs to tmp_path — never the REAL operator log."""
    from zeno.vcli.worlds import go2w_real_diag as d

    old = d._OPLOG_PATH
    d.set_oplog_path(str(tmp_path / "test_agent.log"))
    yield
    d.set_oplog_path(old)
