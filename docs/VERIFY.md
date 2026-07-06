# REAL-VERIFY runbook — the verdict contract + canonical acceptance commands

The ONLY acceptance face is the bare `vector-cli` REPL driven by natural language, eyes on
the sim (Invariant 2). Everything below instruments that face; none of it replaces it. The
ledger (loop/ledger/) RECORDS verdicts from this face; it never IS the verdict.

## The machine verdict — `-p / --json / VECTOR_VERDICT`
```bash
python -m zeno.vcli.cli -p "<prompt>" --json    # one turn, then exit
```
- `--json` prints exactly ONE stdout line: `VECTOR_VERDICT {<json>}` (fixed sentinel);
  all Rich/banner output goes to stderr.
- The verdict is carried by frozen `VerdictReport` (vcli/verdict.py), built ONLY from the
  spine's `classify_step_evidence` / `evidence_passed` — never re-derived
  (`VerdictReport.from_trace(trace, oracle).verified == evidence_passed(trace, oracle)`).

| field | meaning |
|---|---|
| `verified` | bool — `evidence_passed` result (THE acceptance truth; `verified == (exit==0)`) |
| `success` | bool — steps succeeded (not necessarily grounded) |
| `evidence` | `GROUNDED` \| `RAN` \| `FAILED` \| `NO_TRACE` (top evidence grade) |
| `goal` / `n_steps` / `n_grounded` | turn goal · step count · grounded count |
| `oracle_names` | the live verify namespace (same source as GoalVerifier) |
| `per_step` | `{name, strategy, success, verify, verify_result, evidence}` per step |
| `error` | only on NO_TRACE/error |

Exit codes: `0` verified (GROUNDED) · `2` ran-not-verified (RAN/FAILED) · `1` error/NO_TRACE
(chat turns have no deterministic trace → fail-closed).

REMEMBER: a `-p` number is instrument-grade, NOT the face. Bare-REPL + NL is the face; `-p`
exists for harnesses and CI (the D163/D164 lesson: flag-path rates ≠ face rates).

## Canonical acceptance harnesses (tools/acceptance/)
```bash
# NL fetch/place acceptance on the bare REPL (in-process sim; drives a PTY REPL):
VECTOR_NO_ROS2=1 MUJOCO_GL=egl python tools/acceptance/repl_accept.py   # MODE=fetch|place|neg|combo
tools/acceptance/run_neg.sh                                             # negated-distractor NL campaign
python tools/acceptance/g1_accept.py                                    # g1 perception acceptance
python tools/acceptance/g1_nav_accept.py                                # g1 navigation acceptance
python tools/acceptance/visual_e2e.py                                   # ADR-002 visual witness e2e
```
Env comes from `.env.example` (the single canonical template) — one provider block + the
sim block. Deterministic no-network testing: `VECTOR_FAKE_LLM=<json>` injects FakeBackend at
the single `create_backend` seam; every verify/permission layer still runs.

## Eyes (the second witness — required for any physical claim)
1. Capture frames from the SAME sim process that executed the turn (the `VECTOR_SNAPSHOT_DIR`
   hook, written before the `VECTOR_VERDICT` sentinel — see tricky-bugs Case 11 for the
   thread-safety rules).
2. Judge them: the VLM judge (`VECTOR_JUDGE_*` in .env — a DIFFERENT model family from the
   routing brain, generator ≠ evaluator) or read them back yourself.
3. If `VECTOR_JUDGE_*` is unset, the harness must FAIL LOUDLY, never silently pass; record
   the eyes mode honestly in the ledger row: `vlm-judge | self-read | human`. Self-read is
   witness-grade, not oracle-grade. Vision may only DOWNGRADE a verdict, never upgrade
   (ARCHITECTURE §6 vision-honesty invariants).

## Evidence filing
- Frames + verdict JSON + trimmed log → `var/evidence/R<round>/` (gitignored, reboot-safe;
  NEVER /tmp). The verdict JSON is also inlined in the ledger row so the claim outlives the
  frames; paths resolve only on the producing machine — review rounds re-verify on the real
  face instead of trusting old frames.
- Every headline claim passes docs/RULES.md#red-team-before-recording-any-headline-claim BEFORE it is recorded anywhere.
