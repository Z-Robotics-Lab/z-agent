# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Deterministic BOARD.md generator — the acceptance matrix, derived ONLY from the two
JSONL ledgers. Hand-edits are check.sh failures: edit the ledger, regenerate.

Usage: python3 loop/board.py [--stdout]   (default writes loop/ledger/BOARD.md)
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "loop" / "ledger"
DEFAULT_ROUND = 183
ADJUDICATE_AGE = 2    # provisional older than this → flag
STALE_AGE = 30        # confirmed older than this → flag


def current_round() -> int:
    env = os.environ.get("ROUND_N", "")
    if env.isdigit():
        return int(env)
    state = ROOT / "loop" / ".state" / "round_n"
    if state.exists():
        text = state.read_text().strip()
        if text.isdigit():
            return int(text)
    return DEFAULT_ROUND


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # checks_schema.py owns malformed-row failures
    return rows


def round_int(value: object) -> int:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits) if digits else 0


def flag(row: dict, now: int) -> str:
    age = now - round_int(row.get("round"))
    if row.get("status") == "provisional" and age > ADJUDICATE_AGE:
        return " ⚠ ADJUDICATE"
    if row.get("status") == "confirmed" and age > STALE_AGE:
        return " ⚠ STALE"
    return ""


def render() -> str:
    now = current_round()
    acc = load(LEDGER / "acceptance.jsonl")
    exp = load(LEDGER / "experiments.jsonl")
    latest: dict[str, dict] = {}
    for row in acc:  # append-only file ⇒ later line wins
        latest[str(row.get("capability", "?"))] = row

    out = ["# Acceptance board (GENERATED — edit the ledger, not this file)", ""]
    if not latest:
        out.append("_No acceptance rows yet (loop/ledger/acceptance.jsonl is empty)._")
    else:
        out += ["| capability | status | verdict n/m | face | provider | eyes "
                "| age (rounds) | commit |",
                "|---|---|---|---|---|---|---|---|"]
        for cap in sorted(latest):
            r = latest[cap]
            age = now - round_int(r.get("round"))
            out.append(
                f"| {cap} | {r.get('status', '?')}{flag(r, now)} "
                f"| {r.get('verdict', '?')} {r.get('n_pass', '?')}/{r.get('n_total', '?')} "
                f"| {r.get('face', '?')} | {r.get('provider', '?')} | {r.get('eyes', '?')} "
                f"| {age} | {r.get('commit', '?')} |")
    out += ["", "## Open refuted / do-not-retry (from experiments.jsonl)"]
    blocked = [r for r in exp
               if r.get("status") in ("refuted", "plateau") or r.get("do_not_retry_unless")]
    if not blocked:
        out.append("_none_")
    for r in blocked:
        cond = r.get("do_not_retry_unless") or "n/a"
        out.append(f"- {r.get('e', '?')} {r.get('round', '?')} [{r.get('status', '?')}] "
                   f"{r.get('hypothesis', '?')} — retry only if: {cond}")
    out.append("")
    return "\n".join(out)


def main() -> int:
    text = render()
    if "--stdout" in sys.argv[1:]:
        sys.stdout.write(text)
    else:
        (LEDGER / "BOARD.md").write_text(text, encoding="utf-8")
        print(f"wrote {LEDGER / 'BOARD.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
