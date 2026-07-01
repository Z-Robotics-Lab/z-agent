#!/usr/bin/env bash
# D169 — firm category-only PLACE to N>=3 on the bare REPL, CORRECTLY.
# The catfirm_campaign.sh used MODE=both for its firming samples; repl_accept.py:34-36
# warns a pre-held object (grabbed by the fetch turn) makes the place-turn grasp UNCAUSED,
# so its place verdict (catfirm1 0/2, catfirm2 1/2) is a HARNESS ARTIFACT, not a real
# category-place regression. This runs MODE=place (FRESH session each -> the can starts on
# the table, the place-turn grasp is CAUSED) to firm category-only place honestly.
# One sim at a time; repl_accept.py nukes in its finally; we nuke again for safety.
set -u
cd /home/yusen/Desktop/vector_os_nano
OUT=scratchpad/catplace_firm.log
: > "$OUT"
run() {  # tag
  echo "===== $1 @ $(date +%H:%M:%S) =====" | tee -a "$OUT"
  .venv/bin/python scratchpad/repl_accept.py "把罐子拿过来" "把罐子放到架子上" "$1" place 2>&1 \
    | grep -E "\[RESULT|sim ready|EXCEPTION|launch_explore RUNNING" | tee -a "$OUT"
  rosm nuke --yes >/dev/null 2>&1
  sleep 3
}
run catplace1
run catplace2
run catplace3
echo "===== CATPLACE FIRM DONE @ $(date +%H:%M:%S) =====" | tee -a "$OUT"
