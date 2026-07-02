#!/usr/bin/env bash
# loop/preflight.sh — executable ORIENT step 0. Run this FIRST, every round.
# Prints the round context, refuses quarantined/double-driven trees, sanity-checks env,
# sim liveness and the ledgers. Exit 0 = clear to work; non-zero = fix the breach first.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p loop/.state
FAIL=0

# --- deadline / mode ---
if [ -n "${ROUND_N:-}" ] && [ -n "${ROUND_DEADLINE_EPOCH:-}" ]; then
  left=$(( ROUND_DEADLINE_EPOCH - $(date +%s) ))
  echo "round: R$ROUND_N — deadline in ${left}s (stop new work at T-15min; RECORD by T-5min)"
else
  echo "round: interactive mode (no ROUND_N/ROUND_DEADLINE_EPOCH — no deadline, all other rules apply)"
fi

# --- quarantine: previous round failed post-checks ---
if [ -f loop/.state/quarantine ]; then
  echo "PREFLIGHT FAIL: loop/.state/quarantine exists — previous round failed post-checks."
  echo "Fixing this breach IS the round's first job. Contents:"
  cat loop/.state/quarantine
  FAIL=1
fi

# --- double-drive guard (skip when WE are the supervised round: run.sh holds the lock) ---
if [ -z "${ROUND_N:-}" ] && [ -e loop/.state/lock ]; then
  if ! flock -n loop/.state/lock true 2>/dev/null; then
    echo "PREFLIGHT FAIL: loop/.state/lock is held — a supervisor is driving this repo. NEVER double-drive (Invariant 8)."
    FAIL=1
  fi
fi

# --- env sanity: vars marked 'required' in .env.example must be set ---
if [ -f .env.example ]; then
  for v in $(grep -iE '^[A-Z0-9_]+=.*#.*required' .env.example | cut -d= -f1); do
    [ -n "${!v:-}" ] || echo "warn: $v is marked required in .env.example but unset"
  done
else
  echo "warn: .env.example missing — env sanity skipped"
fi

# --- sim liveness (ONE sim at a time — docs/rules/sim-safety.md) ---
live=$(pgrep -af 'mujoco|vcli' | grep -v "preflight" || true)
if [ -n "$live" ]; then
  echo "warn: live sim/vcli processes — ONE sim at a time; WAIT or adopt, never kill infra:"
  echo "$live"
fi
free -g | sed -n '1,2p'

# --- ledger schema ---
python3 loop/checks_schema.py || FAIL=1

# --- inflight run to adopt ---
if [ -s loop/.state/inflight.json ]; then
  echo "inflight run to ADOPT OR CLOSE before new work (ROUND.md §1a):"
  cat loop/.state/inflight.json
fi

# --- unadjudicated provisional rows ---
if [ -f loop/ledger/acceptance.jsonl ]; then
  n=$(grep -c '"status": *"provisional"' loop/ledger/acceptance.jsonl || true)
  echo "provisional acceptance rows needing adjudication (ROUND.md §1b): ${n:-0}"
fi

# --- FakeBackend smoke (pointer only — never launches the sim) ---
if [ -f tests/harness/fake_backend.py ]; then
  echo "smoke (deterministic, no network — see docs/verify.md):"
  echo "  VECTOR_FAKE_LLM='<json>' python -m vector_os_nano.vcli.cli -p '<prompt>' --json  # expect a VECTOR_VERDICT line"
else
  echo "PREFLIGHT FAIL: tests/harness/fake_backend.py missing — the deterministic smoke seam is gone"
  FAIL=1
fi

[ "$FAIL" -eq 0 ] && echo "PREFLIGHT: OK" || echo "PREFLIGHT: FAILED"
exit "$FAIL"
