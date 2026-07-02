#!/usr/bin/env bash
# loop/check.sh — THE doc/ledger enforcement gate (blocking; the docs are the human copy,
# this script is the law). Call sites: round agent at RECORD (default), supervisor
# post-round (--post, tolerates a dirty tree), CI (--ci), report-only (--warn, exit 0).
# Every check DEGRADES TO A WARN when its target file does not exist yet — the kit ships
# before the constitution/ledger (migration ordering).
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

MODE="${1:-record}"          # record | --post | --ci | --warn
FAIL=0
f(){ if [ "$MODE" = "--warn" ]; then echo "DOC-GATE WARN: $*"; else echo "DOC-GATE FAIL: $*"; FAIL=1; fi; }
w(){ echo "DOC-GATE note: $*"; }

# ---------- CONSTANTS (this file is manifest-hashed; changing a cap = CEO-APPROVED) ----
declare -A CAP=( [AGENTS.md]=100 [STATUS.md]=40 [docs/LESSONS.md]=260 [loop/ROUND.md]=135
                 [loop/GOAL.md]=15 [docs/VERIFY.md]=80 [docs/RULES.md]=240
                 [docs/WIRING.md]=170 [docs/reference.md]=280 [loop/README.md]=50 )
DECISIONS_MAX_ENTRIES=48     # full '^## D' entries (overflow = CEO-gated fold)
DECISIONS_MAX_BYTES=196608   # 192KB backstop (the real bound is MAX_ENTRIES; 48 x ~4KB)
# Honest-verify spine (Invariant 1) — enumerated REAL paths, verified on disk:
SPINE='^vector_os_nano/(vcli/cognitive/(trace_store|actor_causation|evidence_classifier)\.py|vcli/verdict\.py|vcli/worlds/[^/]*oracle[^/]*\.py|acceptance/)'

# ---------- 0. Self-integrity: manifest over the constitution + checkers ---------------
if [ -f loop/MANIFEST.sha256 ]; then
  if ! sha256sum -c loop/MANIFEST.sha256 --quiet >/dev/null 2>&1; then
    git log -1 --format=%B | grep -q 'CEO-APPROVED:' \
      || f "manifest-gated file changed without CEO-APPROVED: token in the commit body"
  fi
else
  w "loop/MANIFEST.sha256 not created yet (integration step) — manifest check skipped"
fi

# ---------- 1. Size caps ---------------------------------------------------------------
for p in "${!CAP[@]}"; do
  [ -f "$p" ] || { w "$p missing — cap check skipped"; continue; }
  [ "$(wc -l <"$p")" -le "${CAP[$p]}" ] || f "$p over ${CAP[$p]} lines ($(wc -l <"$p"))"
done
if [ -f docs/DECISIONS.md ]; then
  n=$(grep -c '^## D' docs/DECISIONS.md)
  [ "$n" -le "$DECISIONS_MAX_ENTRIES" ] || f "DECISIONS.md has $n full entries (max $DECISIONS_MAX_ENTRIES — CEO-gated fold due)"
  [ "$(stat -c%s docs/DECISIONS.md)" -le "$DECISIONS_MAX_BYTES" ] || f "DECISIONS.md over the byte backstop"
else w "docs/DECISIONS.md missing — cap check skipped"; fi

# ---------- 2. Allowlist + placement ---------------------------------------------------
if [ -f loop/checks_allowlist.txt ]; then
  ALLOW=$(grep -Ev '^\s*(#|$)' loop/checks_allowlist.txt)
  while IFS= read -r p; do
    ok=0
    while IFS= read -r a; do [[ "$p" == $a ]] && { ok=1; break; }; done <<<"$ALLOW"
    [ "$ok" -eq 1 ] || f "tracked .md not in loop/checks_allowlist.txt: $p"
  done < <(git ls-files '*.md' | grep -E '^([^/]+\.md|docs/[^/]+\.md|loop/[^/]+\.md|loop/ledger/[^/]+\.md)$')
else w "loop/checks_allowlist.txt missing — allowlist check skipped"; fi
[ -z "$(git ls-files scratchpad/)" ] || f "tracked files under scratchpad/ (must be pure gitignored scratch)"
[ -z "$(git ls-files var/)" ]        || f "evidence committed under var/ (gitignored by design)"
git ls-files loop/local.env | grep -q . && f "loop/local.env is TRACKED (owner keys — remove from git)"
git diff --cached --name-only 2>/dev/null | grep -qx 'loop/local.env' && f "loop/local.env is STAGED"

# ---------- 3. Append-only integrity (numstat — mechanical) ----------------------------
if git rev-parse -q --verify HEAD~1 >/dev/null 2>&1; then
  CEO_OK=0; git log -1 --format=%B | grep -q 'CEO-APPROVED:' && CEO_OK=1
  for p in docs/DECISIONS.md loop/ledger/acceptance.jsonl loop/ledger/experiments.jsonl \
           loop/ledger/gates.jsonl loop/ledger/rounds.jsonl; do
    d=$(git diff HEAD~1..HEAD --numstat -- "$p" | awk '{print $2}')
    [ "${d:-0}" = "0" ] || [ "$CEO_OK" = 1 ] || f "$p had deletions without CEO-APPROVED: (append-only)"
  done
  if [ "$CEO_OK" != 1 ] && git diff HEAD~1..HEAD -- docs/DECISIONS.md | grep -E '^\+## D[0-9]+' | grep -vq '\[RULING\]'; then
    f "new DECISIONS.md '## D' entry without [RULING] — results belong in the ledger + commit body"
  fi
  # ---------- 4. Spine gate (tamper-EVIDENT, not tamper-proof — docs/RULES.md CEO-gates) ---
  if git diff HEAD~1..HEAD --name-only | grep -Eq "$SPINE"; then
    git log -1 --format=%B | grep -q 'GATE-APPROVED:' \
      || f "honest-verify spine path changed without GATE-APPROVED: (Invariant 1 CEO gate)"
  fi
else
  w "repo has a single commit — diff-based checks (append-only, spine gate) skipped"
fi

# ---------- 5. Ledger schema -----------------------------------------------------------
python3 loop/checks_schema.py || f "ledger schema violations (LEDGER-FAIL lines above)"

# ---------- 6. Generated artifacts -----------------------------------------------------
if [ -f loop/ledger/BOARD.md ]; then
  python3 loop/board.py --stdout | diff -q - loop/ledger/BOARD.md >/dev/null \
    || f "BOARD.md stale or hand-edited — regenerate: python3 loop/board.py"
else w "loop/ledger/BOARD.md not generated yet — regen check skipped"; fi

# ---------- 7. Rot greps (docs/DECISIONS.md is append-only HISTORY — exempt) -----------
ROT_MD=$(git ls-files 'docs/*.md' 'loop/*.md' AGENTS.md README.md 2>/dev/null | grep -v '^docs/DECISIONS.md$')
for p in $(grep -ln 'Rule [0-9]' $ROT_MD 2>/dev/null); do f "dead 'Rule N' numbering in $p (use Invariant-N)"; done
for p in $(grep -ln '~/.claude' $ROT_MD 2>/dev/null); do f "private '~/.claude' path in shipped file $p"; done
for p in STATUS.md docs/LESSONS.md loop/ledger/acceptance.jsonl loop/ledger/experiments.jsonl; do
  [ -f "$p" ] && grep -qn '/tmp/' "$p" && f "/tmp evidence path in $p (use var/evidence/)"
done
if [ -f docs/DECISIONS.md ] || [ -f docs/decisions-index.md ]; then
  RESOLVERS=$(ls docs/DECISIONS.md docs/decisions-index.md 2>/dev/null)
  for d in $(cat STATUS.md docs/LESSONS.md docs/ARCHITECTURE.md docs/WIRING.md 2>/dev/null | grep -ohE 'D[0-9]{1,3}' | sort -u); do
    grep -qw "$d" $RESOLVERS || f "dangling citation $d (not in DECISIONS.md / decisions-index.md)"
  done
fi
if [ -f STATUS.md ] && grep -q 'VECTOR_PROVIDER=' STATUS.md; then
  f "provider literal in STATUS.md (env facts live only in .env.example)"
fi
for p in $(grep -ln 'VECTOR_PROVIDER=' $ROT_MD 2>/dev/null); do f "provider literal in $p (env facts live only in .env.example)"; done

# ---------- 8. Anchors + North-Star block ----------------------------------------------
python3 loop/checks_anchors.py || f "WIRING.md anchors stale (ANCHOR-FAIL lines above)"
if [ -f AGENTS.md ] && [ -f loop/GOAL.md ] \
   && grep -q 'northstar-anchor-begin' AGENTS.md && grep -q 'northstar-anchor-begin' loop/GOAL.md; then
  # marker lines carry file-specific comments; compare the BODY between the markers
  diff <(sed -n '/northstar-anchor-begin/,/northstar-anchor-end/p' AGENTS.md   | sed '1d;$d') \
       <(sed -n '/northstar-anchor-begin/,/northstar-anchor-end/p' loop/GOAL.md | sed '1d;$d') >/dev/null \
    || f "North-Star anchor block drift between AGENTS.md and loop/GOAL.md (must be byte-equal)"
else
  w "North-Star anchor markers missing in AGENTS.md or loop/GOAL.md — drift check skipped"
fi

if [ "$FAIL" -ne 0 ]; then echo "DOC-GATE: FAILED ($MODE)"; exit 1; fi
echo "DOC-GATE: OK ($MODE)"; exit 0
