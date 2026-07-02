#!/usr/bin/env bash
# loop/run.sh — the portable round supervisor. One round per tick, forever.
#   ./loop/run.sh [loop/harness/<adapter>.sh]     (default: $AGENT_ADAPTER or claude.sh)
#   MAX_ROUNDS=1 ./loop/run.sh ...                (run N rounds then exit — smoke/CI mode)
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

# ELP/1 event stream (E1): one JSON line per event, O_APPEND (>>), pure shell — gitignored.
emit(){ printf '%s\n' "$1" >> loop/.state/events.jsonl; }

ADAPTER=$(realpath "${1:-${AGENT_ADAPTER:-loop/harness/claude.sh}}")
[ -x "$ADAPTER" ] || { echo "adapter not executable: $ADAPTER"; exit 1; }

exec 9>loop/.state/lock
flock -n 9 || { echo "another loop already drives this repo (loop/.state/lock) — never double-drive"; exit 1; }

# Owner keys / host constants (gitignored copy of .env.example)
set -a; [ -f loop/local.env ] && . loop/local.env; set +a

SEED_ROUND=182   # R-space seed: rounds continue the pre-migration count
NET_BACKOFF=60
while :; do
  # ELP stop sentinel (E6): viewer/human asks for a graceful stop — exit BETWEEN rounds.
  if [ -f loop/.state/stop-requested ]; then
    rm -f loop/.state/stop-requested
    echo "stop-requested sentinel found — supervisor exiting cleanly"; exit 0
  fi
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
  T0=$(date +%s)
  date +%s > loop/.state/heartbeat                   # start-of-round beat (ELP liveness)
  emit "{\"schema\":1,\"ts\":$T0,\"round\":\"R$N\",\"src\":\"supervisor\",\"event\":\"round_start\",\"kind\":\"$ROUND_KIND\",\"deadline\":$ROUND_DEADLINE_EPOCH,\"log\":\"$LOG\"}"

  EXIT=0
  if command -v systemd-run >/dev/null 2>&1 && systemd-run --user --scope --collect true >/dev/null 2>&1; then
    cat loop/GOAL.md loop/ROUND.md | systemd-run --user --scope --collect --quiet \
        -p RuntimeMaxSec="${ROUND_TIMEOUT:-3600}" -p MemoryMax="${ROUND_MEM_GB:-40}G" \
        "$ADAPTER" >"$LOG" 2>&1 || EXIT=$?
  else
    echo "WARN: systemd-run unavailable — plain timeout cannot cap memory; PGID reap is best-effort" >&2
    cat loop/GOAL.md loop/ROUND.md | setsid timeout --foreground "${ROUND_TIMEOUT:-3600}" "$ADAPTER" >"$LOG" 2>&1 &
    P=$!; wait "$P" || EXIT=$?
    kill -TERM -- "-$P" 2>/dev/null || true; sleep 5; kill -KILL -- "-$P" 2>/dev/null || true
  fi

  ./scripts/sim-teardown || true                     # repo-scoped; never bare mujoco
  if out=$(./loop/check.sh --post 2>&1); then
    rm -f loop/.state/quarantine                     # breach (if any) is fixed and green
    POST=ok
  else
    printf '%s\n' "$out" > loop/.state/quarantine
    echo "R$N post-check FAILED — tree quarantined; next round must fix the breach first"
    printf '%s\n' "$out" | tail -15
    POST=quarantined
  fi
  T1=$(date +%s); COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo none)
  emit "{\"schema\":1,\"ts\":$T1,\"round\":\"R$N\",\"src\":\"supervisor\",\"event\":\"round_end\",\"exit\":$EXIT,\"post_check\":\"$POST\",\"commit\":\"$COMMIT\",\"dur_s\":$(( T1 - T0 ))}"
  # ELP durable round history (E2): committed by the NEXT round's RECORD.
  printf '%s\n' "{\"schema\":1,\"ts\":$T1,\"round\":\"R$N\",\"kind\":\"$ROUND_KIND\",\"exit\":$EXIT,\"post_check\":\"$POST\",\"commit\":\"$COMMIT\",\"dur_s\":$(( T1 - T0 ))}" >> loop/ledger/rounds.jsonl
  date +%s > loop/.state/heartbeat
  if [ -n "${MAX_ROUNDS:-}" ]; then
    MAX_ROUNDS=$(( MAX_ROUNDS - 1 ))
    [ "$MAX_ROUNDS" -le 0 ] && { echo "MAX_ROUNDS reached — supervisor exiting cleanly"; exit 0; }
  fi
  emit "{\"schema\":1,\"ts\":$(date +%s),\"round\":\"R$N\",\"src\":\"supervisor\",\"event\":\"tick\"}"
  sleep "${INTERVAL:-60}"
done
