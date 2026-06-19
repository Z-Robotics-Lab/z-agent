# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Repo-wide pytest config — the R2a CI acceptance gate.

This project's #1 historical failure: capabilities were "verified" via ad-hoc
``~/sandbox`` scripts that BYPASS the product, while only 2/347 tests touched the
real ``cli.main`` entrypoint. R2a installs the missing acceptance INSTRUMENT (the
PTY ``cli.main`` harness + machine-checkable verdict) and this gate makes the
discipline enforceable:

    Any test that claims a product CAPABILITY (``@pytest.mark.capability``) MUST
    also be verified THROUGH the real product (``@pytest.mark.cli_main``).

``pytest_collection_modifyitems`` fails-closed: a ``capability`` test missing the
``cli_main`` marker is turned into a hard failure at collection time, so a future
capability claim cannot quietly regress to a bypass script. The PTY harness tests
(the acceptance instrument itself) carry both markers.

Also ensures the repo root is on ``sys.path`` so ``import vector_os_nano`` /
``import tests`` resolve when pytest is invoked from anywhere.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Fail-closed: a `capability` test MUST also carry `cli_main`.

    A capability is a claim that the PRODUCT does something; the only honest proof
    is exercising the real ``cli.main`` (the ``cli_main`` marker). A capability
    test that lacks it is verifying a bypass, not the product — so we replace it
    with a failing marker that surfaces the violation at run time (rather than
    skipping it, which would hide the gap).
    """
    offenders: list[str] = []
    for item in items:
        keywords = item.keywords
        if "capability" in keywords and "cli_main" not in keywords:
            offenders.append(item.nodeid)

    if not offenders:
        return

    msg = (
        "CI GATE (R2a): the following @pytest.mark.capability tests are NOT "
        "verified through the real cli.main entrypoint (missing "
        "@pytest.mark.cli_main). A capability MUST be proven through the product, "
        "never a bypass script:\n  - " + "\n  - ".join(sorted(offenders))
    )

    # Fail-closed: turn each offending item into a hard error so the violation is
    # impossible to miss and the suite cannot go green while a capability is
    # verified by a bypass.
    def _make_failer(node_id: str) -> "pytest.Function":
        def _gate_violation() -> None:
            pytest.fail(msg, pytrace=False)

        return _gate_violation  # type: ignore[return-value]

    for item in list(items):
        if item.nodeid in offenders and isinstance(item, pytest.Function):
            item.obj = _make_failer(item.nodeid)
