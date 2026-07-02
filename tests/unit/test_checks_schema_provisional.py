# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Regression: the provisional age-check must recognise supersession.

R187 wedge: an append-only ledger never rewrites a provisional row's `status`;
adjudication (ROUND.md §1b) happens by APPENDING a later row whose `supersedes`
points back at it. The age-check must therefore exempt a provisional once a
later row supersedes it — else a correctly-adjudicated row nags forever and
wedges every future round (R184 fetch-place.nl-compound: superseded by R186
row 21, yet flagged at R187 age 3).
"""
import importlib

import pytest

cs = importlib.import_module("loop.checks_schema")


def _run(monkeypatch, tmp_path, rows, cur_round):
    """Write `rows` to a temp acceptance.jsonl, run check_acceptance at ROUND_N=cur_round."""
    import json

    monkeypatch.setenv("ROUND_N", str(cur_round))
    cs.FAILS.clear()
    path = tmp_path / "acceptance.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    cs.check_acceptance(path)
    return list(cs.FAILS)


def _prov(round_, capability, source="round", supersedes=None):
    return {
        "schema": 1, "ts": "2026-07-02", "round": round_, "capability": capability,
        "face": "bare-repl+nl", "provider": "p", "n_pass": 1, "n_total": 1,
        "verdict": "GROUNDED", "status": "provisional", "eyes": "self-read",
        "evidence": "", "harness": "h", "commit": "c", "source": source,
        "supersedes": supersedes,
    }


def _confirmed(round_, capability, supersedes):
    r = _prov(round_, capability)
    r.update(status="confirmed", redteam="survived: reproduced", supersedes=supersedes)
    return r


def test_superseded_provisional_not_flagged(monkeypatch, tmp_path):
    """A provisional that a later row supersedes is adjudicated → no age-fail."""
    rows = [
        _prov("R184", "fetch-place.nl-compound"),
        _confirmed("R186", "fetch-place.nl-compound", "R184 provisional 49d6e0c"),
    ]
    fails = _run(monkeypatch, tmp_path, rows, cur_round=187)
    assert not any("provisional row from R184" in f for f in fails), fails


def test_unadjudicated_aged_provisional_still_flagged(monkeypatch, tmp_path):
    """Guard: an aged provisional with NO superseding row still fails (not looser)."""
    rows = [_prov("R184", "fetch-place.nl-compound")]
    fails = _run(monkeypatch, tmp_path, rows, cur_round=187)
    assert any("provisional row from R184" in f for f in fails), fails


def test_supersession_must_match_capability(monkeypatch, tmp_path):
    """A supersedes for a DIFFERENT capability does not clear an unrelated provisional."""
    rows = [
        _prov("R184", "fetch-place.nl-compound"),
        _confirmed("R186", "g1.navigation", "R184 provisional deadbee"),
    ]
    fails = _run(monkeypatch, tmp_path, rows, cur_round=187)
    assert any("provisional row from R184" in f for f in fails), fails


def test_fresh_provisional_within_window_ok(monkeypatch, tmp_path):
    """A provisional only 2 rounds old is inside the window → no fail regardless."""
    rows = [_prov("R185", "fetch-place.nl-compound")]
    fails = _run(monkeypatch, tmp_path, rows, cur_round=187)
    assert not any("provisional row from R185" in f for f in fails), fails
