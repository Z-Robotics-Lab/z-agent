# REAL-VERIFY runbook — the verdict contract + canonical acceptance commands

The ONLY acceptance face is the bare `zeno` REPL driven by natural language, eyes on
the sim (Invariant 2). Everything below instruments that face; none of it replaces it. The
ledger (loop/ledger/) RECORDS verdicts from this face; it never IS the verdict.

## The machine verdict — `-p / --json / ZENO_VERDICT`
```bash
python -m zeno.vcli.cli -p "<prompt>" --json    # one turn, then exit
```
- `--json` prints the verdict as TWO stdout sentinel lines with ONE identical payload:
  `ZENO_VERDICT {<json>}` (primary, first) + `VECTOR_VERDICT {<json>}` (legacy alias,
  last — D184 transition; scanners accept either); Rich/banner output goes to stderr.
- The verdict is carried by frozen `VerdictReport` (vcli/verdict.py), built ONLY from the
  spine's `classify_step_evidence` / `evidence_passed` — never re-derived
  (`VerdictReport.from_trace(trace, oracle, preds).verified == evidence_passed(trace, oracle, preds)`).

### Grounding semantics (CEO-gated change, 2026-07-13)
- **Predicate-role map**: a world marks its goal-conditioned bool verify callables with
  `evidence_classifier.predicate_oracle` (go2w_real: `at`/`moved`/`turned`/`stack_ready`/
  `route_reached`/`explore_finished`); `verify_predicate_names(agent, engine)` collects the
  marked names from the SAME live namespace as `verify_oracle_names` and both sets feed the
  classifier. A bare call of a role-mapped, SERVED oracle now classifies GROUNDED like a
  kernel predicate (pre-fix, every world-registered predicate classified RAN, so an
  all-green hardware turn displayed `verified=False (0/N grounded)`). The role can only
  RECOGNIZE a served oracle — never add one; all structural guards (or-True short-circuit,
  bare state oracle, tautologies) are unchanged. Default empty set = kernel-only (fail-closed).
- **verified grades goal-state truth**: a turn where EVERY step's predicate ran and passed
  on a world-served oracle reports `verified=True (N/N grounded)`; any failed / never-run
  predicate still fails the turn.
- **Actor-causation is an annotation with teeth for actions**: `CAUSED`/`UNCAUSED`/
  `NOT_GRADED` is displayed per step (`(actor=...)` in the REPL). `UNCAUSED` still
  downgrades a step that ACTED (non-empty strategy — a teleport / satisfied-at-baseline
  no-op behind a commanded action stays RAN). A VERIFY-ONLY step (no action) with a passing
  predicate is a grounded OBSERVATION — it verifies (`where am I` / `is the stack up`
  turns are honest greens) and can never mask a failed action step (every checked step
  must still ground).

| field | meaning |
|---|---|
| `verified` | bool — `evidence_passed` result (THE acceptance truth; `verified == (exit==0)`) |
| `success` | bool — steps succeeded (not necessarily grounded) |
| `evidence` | `GROUNDED` \| `RAN` \| `FAILED` \| `NO_TRACE` (top evidence grade) |
| `goal` / `n_steps` / `n_grounded` | turn goal · step count · grounded count |
| `oracle_names` | the live verify namespace (same source as GoalVerifier), AFTER the world's optional `verify_namespace_deny()` opt-out — a hardware world may REMOVE engine stub names (never add), so only predicates the world actually serves are advertised/taught/eval-able (native `verify` rejects out-of-vocab calls with a corrective error) |
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
   hook, written before the verdict sentinel lines — see tricky-bugs Case 11 for the
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
