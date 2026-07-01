#!/usr/bin/env bash
# D168 firm-the-number + D169 frontier probe.
#   Samples 1-3: category-only find-fetch-place on the bare REPL (罐子 -> red can),
#                firms D168's single-sample re-accept to N>=3.
#   Sample  4  : FRONTIER probe — ONE multi-clause utterance
#                "把红色的罐子拿过来放到架子上" (compositional fetch AND place in a single
#                command). Tests the native producer's multi-step decomposition on the
#                true bare-cli+NL face. Combo mode captures EVERY step verdict.
# One sim at a time (repl_accept.py nukes in its finally); we nuke again between for safety.
set -u
cd /home/yusen/Desktop/vector_os_nano
OUT=scratchpad/catfirm_campaign.log
: > "$OUT"
run() {  # tag mode fetch place
  echo "===== $1 @ $(date +%H:%M:%S) =====" | tee -a "$OUT"
  .venv/bin/python scratchpad/repl_accept.py "$3" "$4" "$1" "$2" 2>&1 \
    | grep -E "\[RESULT|sim ready|EXCEPTION|launch_explore RUNNING|combo turn done" | tee -a "$OUT"
  rosm nuke --yes >/dev/null 2>&1
  sleep 3
}
run catfirm1 both  "把罐子拿过来" "把罐子放到架子上"
run catfirm2 both  "把罐子拿过来" "把罐子放到架子上"
run catfirm3 both  "把罐子拿过来" "把罐子放到架子上"
run combo1   combo "把红色的罐子拿过来放到架子上" ""
echo "===== CAMPAIGN DONE @ $(date +%H:%M:%S) =====" | tee -a "$OUT"
