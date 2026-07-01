#!/usr/bin/env bash
set +e
cd /home/yusen/Desktop/vector_os_nano
N=${1:-12}
OUT=scratchpad/place_campaign_R14.log
: > "$OUT"
for i in $(seq 1 "$N"); do
  echo "=== TRIAL $i $(date +%H:%M:%S) ===" >> "$OUT"
  timeout 240 .venv/bin/python scratchpad/place_probe.py 2>>scratchpad/place_campaign_R14.err | grep '^RESULT' >> "$OUT"
  rosm nuke --yes >/dev/null 2>&1
  sleep 1
done
echo "=== CAMPAIGN DONE $(date +%H:%M:%S) ===" >> "$OUT"
