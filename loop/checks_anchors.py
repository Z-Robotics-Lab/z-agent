# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""Hard-check docs/WIRING.md `anchors:` blocks — every `path/file.py::symbol` must
point at an existing file that still contains the symbol string. stdlib only.

WIRING.md holds one '## <subsystem>' section per wiring card; each section may carry
its own fenced anchors block. Checked per-section.

Exit 0 = all anchors resolve (no wiring file / no anchors block = pass with a note).
Exit 1 = a section cites a file or symbol that no longer exists (the section is stale).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WIRING = ROOT / "docs" / "WIRING.md"

FAILS: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)
    print(f"ANCHOR-FAIL: {msg}")


def split_sections(text: str) -> list[tuple[str, str]]:
    """Return (section_name, section_text) pairs, one per '## ' heading."""
    sections: list[tuple[str, str]] = []
    name: str | None = None
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if name is not None:
                sections.append((name, "\n".join(lines)))
            name = line[3:].split("—")[0].strip() or line[3:].strip()
            lines = []
        elif name is not None:
            lines.append(line)
    if name is not None:
        sections.append((name, "\n".join(lines)))
    return sections


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


def check_section(name: str, body: str) -> None:
    entries = extract_anchors(body)
    if not entries:
        print(f"note: WIRING.md section {name!r} has no anchors: block")
        return
    for entry in entries:
        if "::" not in entry:
            fail(f"{name}: malformed anchor {entry!r} (want path/file.py::symbol)")
            continue
        rel_path, symbol = entry.split("::", 1)
        target = ROOT / rel_path
        if not target.exists():
            fail(f"{name}: anchor file missing: {rel_path}")
            continue
        if symbol not in target.read_text(encoding="utf-8", errors="replace"):
            fail(f"{name}: symbol {symbol!r} absent from {rel_path}")


def main() -> int:
    if not WIRING.is_file():
        print("note: docs/WIRING.md does not exist yet — nothing to check")
        return 0
    sections = split_sections(WIRING.read_text(encoding="utf-8"))
    if not sections:
        print("note: docs/WIRING.md has no '## ' sections — nothing to check")
        return 0
    for name, body in sections:
        check_section(name, body)
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
