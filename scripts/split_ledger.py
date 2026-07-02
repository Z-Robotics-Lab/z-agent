#!/usr/bin/env python3
"""One-time DECISIONS.md fold — 2026-07-01 CEO-approved restructure (precedent e21d5ad).

Kept in-repo as the audit trail. Deterministic, stdlib-only.

What it does (plan §4 "docs/DECISIONS.md (post-fold shape)" + §5 step 6):
- Header (everything before the first '## D' heading) preserved BYTE-IDENTICALLY;
  the CEO addendum is APPENDED directly after it (never edited into it).
- KEEP-LIST = union of:
    (i)   every D# cited in tracked files OUTSIDE docs/DECISIONS.md
          (\\bD[0-9]{1,3}\\b, filtered to existing entry numbers);
    (ii)  the named spine set;
    (iii) the last 6 entries by number (recency floor).
  A '-confirm' addendum entry follows its base entry's keep/fold status.
- KEPT entries are copied byte-identically (asserted by re-extraction from the output).
- FOLDED entries become one-line stubs under '## Archive index (journal stubs)':
      D### <original headline> → git <hash>
  where <hash> = the commit that introduced the entry into docs/DECISIONS.md
  (git log -S, --reverse), falling back to the newest commit whose subject cites the
  D#, falling back to the literal 'git-history'.

Refuses to run twice (idempotency guard on the Archive-index section).
"""

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LEDGER = REPO / "docs" / "DECISIONS.md"

# (ii) named spine set (plan §5 step 6; confirm-addenda ride along via base number).
SPINE = {6, 9, 14, 69, 101, 103, 106, 112, 116, 163, 164, 165, 170, 176, 178}
# (iii) recency floor: the last N entries by number.
RECENCY = 6

ADDENDUM = (
    "> **2026-07-01 CEO-approved restructure (one-time, precedent e21d5ad):** "
    "journal-class entries\n"
    "> folded to one-line stubs per the fold rule this header already sanctions; "
    "every D3–D182 remains\n"
    "> resolvable here + docs/decisions-index.md + git history. New entries require "
    "a [RULING] tag\n"
    "> (admission test: docs/RULES.md doc-governance — an entry must change an "
    "invariant, contract, or\n"
    "> spine semantic, or record a CEO ruling; everything else is a ledger row + "
    "commit message). Rounds\n"
    "> and experiments now use R#/E# in loop/ledger/ — D# is rulings-only, D183+. "
    "No accepted ruling was\n"
    "> edited or renumbered.\n"
)

ARCHIVE_HEADING = "## Archive index (journal stubs)"
HEADING_RE = re.compile(r"^## ", re.M)
ENTRY_RE = re.compile(r"^## (D(\d{1,3})(-[A-Za-z0-9]+)?) — (.*)$")
CITE_RE = re.compile(r"\bD(\d{1,3})\b")


def run_git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        check=True, capture_output=True, text=True,
    ).stdout


def parse(text: str):
    """Split into (header, entries, archive_text).

    header  = everything before the first '## ' heading (byte-preserved)
    entries = list of (entry_id, num, headline, segment) — segment includes the
              heading line and runs to the next '## ' heading (byte-preserved)
    archive_text = the '## Archive index' segment if present, else ''
    """
    starts = [m.start() for m in HEADING_RE.finditer(text)]
    if not starts:
        raise SystemExit("no '## ' headings found — not a DECISIONS ledger?")
    header = text[: starts[0]]
    entries = []
    archive = ""
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(text)
        seg = text[start:end]
        first_line = seg.split("\n", 1)[0]
        if first_line.startswith(ARCHIVE_HEADING):
            archive = text[start:]
            break
        m = ENTRY_RE.match(first_line)
        if not m:
            raise SystemExit(f"unrecognized heading (not 'D### — ...'): {first_line!r}")
        entries.append((m.group(1), int(m.group(2)), m.group(4), seg))
    return header, entries, archive


def cited_numbers(valid_nums: set) -> set:
    """(i) every D# cited in tracked *.md files outside docs/DECISIONS.md.

    Scope = .md only (2026-07-01 reconciliation): code comments cite D#s as historical
    breadcrumbs by the dozen; those resolve via docs/decisions-index.md -> git show and
    do not need the full prose kept. The generated index itself is excluded (it lists
    every D# by construction). Pure-version strings are excluded by requiring a word
    boundary BEFORE the D (so 'D435i'/'3D10' don't match) and by filtering to existing
    entry numbers.
    """
    cited = set()
    for path in run_git("ls-files", "-z").split("\0"):
        if not path or path == "docs/DECISIONS.md":
            continue
        if not path.endswith(".md") or path == "docs/decisions-index.md":
            continue
        p = REPO / path
        if not p.is_file():
            continue
        text = p.read_bytes().decode("utf-8", errors="ignore")
        for m in CITE_RE.finditer(text):
            n = int(m.group(1))
            if n in valid_nums:
                cited.add(n)
    return cited


_SUBJECTS = None  # cached [(hash, subject)] newest-first


def entry_hash(entry_id: str) -> str:
    """Commit that introduced '## <entry_id> ' into docs/DECISIONS.md."""
    global _SUBJECTS
    out = run_git("log", "--format=%h", "-S", f"## {entry_id} ", "--reverse",
                  "--", "docs/DECISIONS.md").split()
    if out:
        return out[0]
    if _SUBJECTS is None:
        _SUBJECTS = [
            line.split(" ", 1) for line in run_git("log", "--format=%h %s").splitlines()
        ]
    pat = re.compile(rf"\b{re.escape(entry_id)}\b")
    for h, subj in _SUBJECTS:
        if pat.search(subj):
            return h
    return "git-history"


def main() -> None:
    orig = LEDGER.read_text(encoding="utf-8")
    if ARCHIVE_HEADING in orig:
        raise SystemExit("Archive index already present — fold already ran; refusing.")
    if not orig.endswith("\n"):
        raise SystemExit("ledger does not end with a newline; refusing.")

    header, entries, _ = parse(orig)
    nums = {n for _, n, _, _ in entries}
    missing_spine = SPINE - nums
    if missing_spine:
        raise SystemExit(f"spine D#s missing from ledger: {sorted(missing_spine)}")

    keep_cited = cited_numbers(nums)
    keep_recent = set(sorted(nums)[-RECENCY:])
    keep = keep_cited | SPINE | keep_recent

    kept = [e for e in entries if e[1] in keep]
    folded = [e for e in entries if e[1] not in keep]

    stubs = [
        f"{eid} {headline} → git {entry_hash(eid)}"
        for eid, _num, headline, _seg in folded
    ]

    new = header + ADDENDUM + "\n"
    new += "".join(seg for _, _, _, seg in kept)
    new += ARCHIVE_HEADING + "\n\n" + "\n".join(stubs) + "\n"

    # --- assertions before writing (byte-conservative guarantees) ---
    new_header, new_entries, new_archive = parse(new)
    assert new_header == header + ADDENDUM + "\n", "header not preserved+appended"
    assert new_header.startswith(header), "original header bytes not preserved"
    old_segs = {eid: seg for eid, _, _, seg in entries}
    assert [e[0] for e in new_entries] == [e[0] for e in kept], "kept order/ids drifted"
    for eid, _num, _hl, seg in new_entries:
        assert seg == old_segs[eid], f"kept entry {eid} not byte-identical"
    stub_ids = {line.split(" ", 1)[0] for line in new_archive.splitlines()
                if line.startswith("D")}
    assert stub_ids == {e[0] for e in folded}, "stub set mismatch"
    all_ids = {e[0] for e in entries}
    assert {e[0] for e in new_entries} | stub_ids == all_ids, "an entry vanished"

    LEDGER.write_text(new, encoding="utf-8")

    kept_nums = sorted({n for _, n, _, _ in kept})
    print(f"entries total : {len(entries)}")
    print(f"kept full-text: {len(kept)} segments ({len(kept_nums)} D#s)")
    print(f"folded stubs  : {len(folded)}")
    print(f"keep (cited)  : {sorted(keep_cited)}")
    print(f"keep (spine)  : {sorted(SPINE)}")
    print(f"keep (recent) : {sorted(keep_recent)}")
    print(f"keep-list     : {kept_nums}")
    print(f"new size      : {len(new.encode('utf-8'))} bytes "
          f"(was {len(orig.encode('utf-8'))})")


if __name__ == "__main__":
    sys.exit(main())
