#!/usr/bin/env bash
# loop/run.sh — the portable round supervisor. One round per tick, forever.
#   ./loop/run.sh [loop/harness/<adapter>.sh]     (default: $AGENT_ADAPTER or claude.sh)
# Contract: hold the per-repo lock · bump loop/.state/round_n · export ROUND_N +
# ROUND_DEADLINE_EPOCH + ROUND_KIND (build; review on every 10th) · pipe GOAL.md+ROUND.md
# to the adapter · then sim-teardown, check.sh --post (fail => quarantine), heartbeat, sleep.
#
# Hardening for multi-day unattended runs (host-specific, ALL optional — the loop is
# correct without it, only less immortal):
#   - wrap this script in a systemd user service with Restart=always;
#   - an external watchdog restarting the service when loop/.state/heartbeat goes stale;
#   - per-round CPU/memory caps come free when systemd-run is available (below).
# NEVER kill this supervisor, its timeout wrapper, or a sibling round (Invariant 8).
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"
mkdir -p loop/.state loop/ledger

ADAPTER=$(realpath "${1:-${AGENT_ADAPTER:-loop/harness/claude.sh}}")
[ -x "$ADAPTER" ] || { echo "adapter not executable: $ADAPTER"; exit 1; }

exec 9>loop/.state/lock
flock -n 9 || { echo "another loop already drives this repo (loop/.state/lock) — never double-drive"; exit 1; }

# Owner keys / host constants (gitignored copy of .env.example)
set -a; [ -f loop/local.env ] && . loop/local.env; set +a

SEED_ROUND=182   # R-space seed: rounds continue the pre-migration count
NET_BACKOFF=60
while :; do
  # Network hold: never launch a round into a dead network (skip with LOOP_OFFLINE=1)
  if [ -z "${LOOP_OFFLINE:-}" ]; then
    while ! timeout 8 bash -c 'exec 3<>/dev/tcp/1.1.1.1/443' 2>/dev/null; do
      echo "network down — holding ${NET_BACKOFF}s"; sleep "$NET_BACKOFF"
      NET_BACKOFF=$(( NET_BACKOFF >= 300 ? 600 : NET_BACKOFF * 2 ))
    done
    NET_BACKOFF=60
  fi

  N=$(( $(cat loop/.state/round_n 2>/dev/null || echo "$SEED_ROUND") + 1 ))
  echo "$N" > loop/.state/round_n
  export ROUND_KIND=build
  [ $(( N % 10 )) -eq 0 ] && export ROUND_KIND=review   # reviews are SET, not remembered (ROUND.md §7)
  export ROUND_N="$N" ROUND_DEADLINE_EPOCH=$(( $(date +%s) + ${ROUND_TIMEOUT:-3600} ))
  LOG="loop/.state/round-$N.log"
  echo "=== R$N ($ROUND_KIND) — deadline $(date -d "@$ROUND_DEADLINE_EPOCH" '+%H:%M:%S') — log $LOG ==="

  if command -v systemd-run >/dev/null 2>&1 && systemd-run --user --scope --collect true >/dev/null 2>&1; then
    cat loop/GOAL.md loop/ROUND.md | systemd-run --user --scope --collect --quiet \
        -p RuntimeMaxSec="${ROUND_TIMEOUT:-3600}" -p MemoryMax="${ROUND_MEM_GB:-40}G" \
        "$ADAPTER" >"$LOG" 2>&1 || true
  else
    echo "WARN: systemd-run unavailable — plain timeout cannot cap memory; PGID reap is best-effort" >&2
    cat loop/GOAL.md loop/ROUND.md | setsid timeout --foreground "${ROUND_TIMEOUT:-3600}" "$ADAPTER" >"$LOG" 2>&1 &
    P=$!; wait "$P" || true
    kill -TERM -- "-$P" 2>/dev/null || true; sleep 5; kill -KILL -- "-$P" 2>/dev/null || true
  fi

  ./scripts/sim-teardown || true                     # repo-scoped; never bare mujoco
  if out=$(./loop/check.sh --post 2>&1); then
    rm -f loop/.state/quarantine                     # breach (if any) is fixed and green
  else
    printf '%s\n' "$out" > loop/.state/quarantine
    echo "R$N post-check FAILED — tree quarantined; next round must fix the breach first"
    printf '%s\n' "$out" | tail -15
  fi
  date +%s > loop/.state/heartbeat
  sleep "${INTERVAL:-60}"
done
