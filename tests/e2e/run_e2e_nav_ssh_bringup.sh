#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
#
# Repeatable E2E driver for the SSH nav transport (Phase 2). Brings the REAL nav
# stack up on the NUC over ssh from the 4090, proves /state_estimation flows
# cross-machine (DDS domain 20), reads pose via the product `where` tool, then
# tears the stack down — all READ-ONLY on the ROS layer (no motion topic, no
# posture/estop service). See tests/e2e/e2e_nav_ssh_bringup.py for the flow.
#
# Usage:  tests/e2e/run_e2e_nav_ssh_bringup.sh
# Env you may override:
#   GO2W_NAV_SSH_HOST   (default go2w-nuc)
#   CYCLONEDDS_URI      (default: the repo workstation profile; must let the
#                        4090 join the NUC on domain 20 — set to your smoke xml
#                        if the workstation profile is not on disk yet)
#   ROS_SETUP           (default /opt/ros/jazzy/setup.bash)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"

ROS_SETUP="${ROS_SETUP:-/opt/ros/jazzy/setup.bash}"
# ROS ament setup scripts reference unbound vars — disable nounset around it.
set +u
# shellcheck disable=SC1090
source "$ROS_SETUP"
set -u

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-20}"

# DDS profile: default to the workstation profile shipped in the go2w-nuc repo
# (sibling checkout of z-agent-run); fall back to whatever CYCLONEDDS_URI is set.
_DEFAULT_DDS="$REPO/../go2w-nuc/bringup/workstation/cyclonedds-workstation.xml"
if [ -z "${CYCLONEDDS_URI:-}" ] && [ -f "$_DEFAULT_DDS" ]; then
  export CYCLONEDDS_URI="file://$_DEFAULT_DDS"
fi
if [ -z "${CYCLONEDDS_URI:-}" ]; then
  echo "ERROR: CYCLONEDDS_URI unset and no workstation profile at $_DEFAULT_DDS" >&2
  echo "       Set CYCLONEDDS_URI=file://<your-domain-20 profile> and re-run." >&2
  exit 2
fi

# Drive nav.sh over ssh to the NUC (the whole point of this E2E).
export GO2W_NAV_TRANSPORT=ssh
export GO2W_NAV_SSH_HOST="${GO2W_NAV_SSH_HOST:-go2w-nuc}"

echo "[e2e] REPO=$REPO"
echo "[e2e] ROS_DOMAIN_ID=$ROS_DOMAIN_ID RMW=$RMW_IMPLEMENTATION"
echo "[e2e] CYCLONEDDS_URI=$CYCLONEDDS_URI"
echo "[e2e] GO2W_NAV_TRANSPORT=$GO2W_NAV_TRANSPORT host=$GO2W_NAV_SSH_HOST"

cd "$REPO"
exec .venv/bin/python -m tests.e2e.e2e_nav_ssh_bringup
