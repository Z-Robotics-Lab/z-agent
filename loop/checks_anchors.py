# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Hard-check docs/wiring/*.md `anchors:` blocks — every `path/file.py::symbol` must
point at an existing file that still contains the symbol string. stdlib only.

Exit 0 = all anchors resolve (no wiring cards / no anchors block = pass with a note).
Exit 1 = a card cites a file or symbol that no longer exists (the card is stale).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIRING = ROOT / "docs" / "wiring"

FAILS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f"ANCHOR-FAIL: {msg}")


def extract_anchors(text: str) -> list[str]:
    """Return anchor entries from the fenced block whose first line is 'anchors:'."""
    anchors: list[str] = []
    in_fence = False
    in_anchors = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            if in_fence:
                in_fence = in_anchors = False
            else:
                in_fence = True
            continue
        if in_fence and not in_anchors:
            in_anchors = stripped == "anchors:"
            if in_anchors:
                continue
            in_fence = False  # some other fenced block — skip it
        if in_anchors and stripped:
            anchors.append(stripped)
    return anchors


def check_card(card: Path) -> None:
    entries = extract_anchors(card.read_text(encoding="utf-8"))
    if not entries:
        print(f"note: {card.relative_to(ROOT)} has no anchors: block")
        return
    for entry in entries:
        if "::" not in entry:
            fail(f"{card.name}: malformed anchor {entry!r} (want path/file.py::symbol)")
            continue
        rel_path, symbol = entry.split("::", 1)
        target = ROOT / rel_path
        if not target.exists():
            fail(f"{card.name}: anchor file missing: {rel_path}")
            continue
        if symbol not in target.read_text(encoding="utf-8", errors="replace"):
            fail(f"{card.name}: symbol {symbol!r} absent from {rel_path}")


def main() -> int:
    if not WIRING.is_dir():
        print("note: docs/wiring/ does not exist yet — nothing to check")
        return 0
    for card in sorted(WIRING.glob("*.md")):
        check_card(card)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
