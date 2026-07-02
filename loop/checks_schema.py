# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Validate loop/ledger/*.jsonl — schema, enums, caps. stdlib only; called by check.sh.

Exit 0 = valid (missing files are fine: the kit ships before the ledger).
Exit 1 = violation (printed, one per line, prefixed LEDGER-FAIL).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "loop" / "ledger"

MAX_FILE_BYTES = 512 * 1024      # beyond this: rotate to loop/ledger/archive/
MAX_LINE_BYTES = 1024
MAX_TEXT_CHARS = 280             # any free-text string field
PROVISIONAL_MAX_AGE = 2          # rounds; older unadjudicated provisionals fail

ACC_REQUIRED = {"schema", "ts", "round", "capability", "face", "provider", "n_pass",
                "n_total", "verdict", "status", "eyes", "evidence", "harness",
                "commit", "source"}
ACC_STATUS = {"provisional", "confirmed", "refuted", "superseded"}
ACC_EYES = {"vlm-judge", "self-read", "human"}
SOURCES = {"round", "backfill"}
EXP_REQUIRED = {"schema", "ts", "round", "e", "type", "hypothesis", "result",
                "status", "source"}
EXP_TYPE = {"build", "verify", "research", "debug", "review"}
EXP_STATUS = {"confirmed", "refuted", "plateau", "inconclusive"}

FAILS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f"LEDGER-FAIL: {msg}")


def _round_int(value: object) -> int | None:
    s = str(value)
    digits = "".join(ch for ch in s if ch.isdigit())
    return int(digits) if digits else None


def _current_round() -> int | None:
    env = os.environ.get("ROUND_N")
    if env and env.isdigit():
        return int(env)
    state = ROOT / "loop" / ".state" / "round_n"
    if state.exists():
        text = state.read_text().strip()
        if text.isdigit():
            return int(text)
    return None


def _load(path: Path) -> list[tuple[int, dict]]:
    if path.stat().st_size > MAX_FILE_BYTES:
        fail(f"{path.name} >512KB — rotate it to loop/ledger/archive/"
             f"{path.stem}-<year>.jsonl (append-only move), then retry")
    rows: list[tuple[int, dict]] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        if len(line.encode()) > MAX_LINE_BYTES:
            fail(f"{path.name}:{i} row >1KB")
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            fail(f"{path.name}:{i} not JSON: {exc}")
            continue
        for key, val in obj.items():
            if isinstance(val, str) and len(val) > MAX_TEXT_CHARS:
                fail(f"{path.name}:{i} field '{key}' >{MAX_TEXT_CHARS} chars")
        rows.append((i, obj))
    return rows


def check_acceptance(path: Path) -> None:
    cur = _current_round()
    for i, row in _load(path):
        missing = ACC_REQUIRED - row.keys()
        if missing:
            fail(f"{path.name}:{i} missing keys {sorted(missing)}")
        if row.get("status") not in ACC_STATUS:
            fail(f"{path.name}:{i} status {row.get('status')!r} not in {sorted(ACC_STATUS)}")
        if row.get("eyes") not in ACC_EYES:
            fail(f"{path.name}:{i} eyes {row.get('eyes')!r} not in {sorted(ACC_EYES)}")
        if row.get("source") not in SOURCES:
            fail(f"{path.name}:{i} source {row.get('source')!r} not in {sorted(SOURCES)}")
        if row.get("status") == "confirmed" and not str(row.get("redteam", "")).startswith("survived"):
            fail(f"{path.name}:{i} confirmed row requires redteam starting 'survived'")
        age_from = _round_int(row.get("round"))
        # source:"backfill" rows predate the ledger; BOARD flags them ADJUDICATE and
        # STATUS `next:` carries the adjudication task — the age check must not wedge
        # the first round that is supposed to do that adjudication.
        if (row.get("status") == "provisional" and cur is not None
                and row.get("source") != "backfill"
                and age_from is not None and cur - age_from > PROVISIONAL_MAX_AGE):
            fail(f"{path.name}:{i} provisional row from R{age_from} is >"
                 f"{PROVISIONAL_MAX_AGE} rounds old — adjudicate it (ROUND.md §1b)")


def check_experiments(path: Path) -> None:
    last_e = 0
    for i, row in _load(path):
        missing = EXP_REQUIRED - row.keys()
        if missing:
            fail(f"{path.name}:{i} missing keys {sorted(missing)}")
        if row.get("type") not in EXP_TYPE:
            fail(f"{path.name}:{i} type {row.get('type')!r} not in {sorted(EXP_TYPE)}")
        if row.get("status") not in EXP_STATUS:
            fail(f"{path.name}:{i} status {row.get('status')!r} not in {sorted(EXP_STATUS)}")
        if row.get("source") not in SOURCES:
            fail(f"{path.name}:{i} source {row.get('source')!r} not in {sorted(SOURCES)}")
        e_num = _round_int(row.get("e"))
        if e_num is None:
            fail(f"{path.name}:{i} bad e field {row.get('e')!r} (want E<n>)")
        elif e_num < last_e:
            fail(f"{path.name}:{i} E# not monotone (E{e_num} after E{last_e})")
        else:
            last_e = e_num


def main() -> int:
    acc = LEDGER / "acceptance.jsonl"
    exp = LEDGER / "experiments.jsonl"
    if acc.exists():
        check_acceptance(acc)
    if exp.exists():
        check_experiments(exp)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
