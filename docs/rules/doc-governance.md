# Doc Governance — the fixed doc set + compression that keep sessions continuous (pull-on-demand)

Bounded, allowlisted doc set; a new session reads only these. Git is the archive — superseded docs are DELETED, not moved to archive/.

## Allowlist (nothing else gets committed under docs/)
- Root: CLAUDE.md (constitution, only auto-loaded) + README.md (overview + 5-min quickstart).
- Rules (pull-on-demand, ≤50L): docs/rules/{standards,sim-safety,doc-governance}.md.
- State: docs/agent-kernel-STATUS.md (resume anchor) + docs/DECISIONS.md (decision record).
- Reference (durable): docs/{ARCHITECTURE,cli-tool-system,skill-protocol,tricky-bugs}.md.
- Anything else = scratch, delete before commit. NEVER create index/START_HERE/dated-session/manifest docs.

## Line caps (hard)
- CLAUDE.md ≤50L; each docs/rules/*.md ≤50L. Reference docs are EXEMPT (carry durable detail; keep CURRENT, not short).

## STATUS compression
- SNAPSHOT not log: OVERWRITE every round (≤40L). Round history lives in DECISIONS + git.

## DECISIONS compression
- APPEND-ONLY; add a new `## D<N>`. NEVER rewrite an accepted D# (correction = new line).
- Fold ONLY on a Review round, ONLY entries old AND superseded AND uncited → one-line git-stub. Never fold a STATUS-cited or open-gate entry.

## MANDATORY before every work commit (advisory print — a human/loop eyeballs it; NOT a blocking gate)
1. Update docs/agent-kernel-STATUS.md to the new state + next step. ALWAYS.
2. Structure/contract/data-flow/invariant change → update docs/ARCHITECTURE.md (and CLAUDE.md if an invariant changed) same commit.
3. Delete scratch/analysis/plan docs not on the allowlist; scan ALL of docs/ for stale and delete (git keeps them).
4. PRINT the census + eyeball it: `find docs -name '*.md' | wc -l` and `find docs -name '*.md' | xargs wc -l`;
   confirm CLAUDE.md and each docs/rules/*.md are ≤50 lines. Advisory only — no test blocks the commit.
