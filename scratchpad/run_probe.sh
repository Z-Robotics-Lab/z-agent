#!/bin/bash
# Run place_probe.py N times, one subprocess each (MuJoCo realloc), rosm nuke between.
set +e
cd /home/yusen/Desktop/vector_os_nano
N=${1:-6}
OUT=scratchpad/probe_results.txt
: > $OUT
export VECTOR_SIM_WITH_ARM=1 MUJOCO_GL=egl VECTOR_NO_ROS2=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
for k in $(seq 1 $N); do
  SNAP=/tmp/claude-1000/-home-yusen/de114851-2aa5-4dd2-b3cb-20b2199b9b23/scratchpad/probe_$k
  rm -rf $SNAP; mkdir -p $SNAP
  rosm nuke --yes >/dev/null 2>&1; sleep 1
  export VECTOR_PLACE_DIAG=$SNAP/diag.jsonl
  R=$(timeout 260 .venv/bin/python scratchpad/place_probe.py 2>$SNAP/err.log | grep '^RESULT')
  echo "[$k/$N] $R" | tee -a $OUT
done
rosm nuke --yes >/dev/null 2>&1
echo "DONE" | tee -a $OUT
