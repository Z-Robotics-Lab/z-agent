# Sim Safety — MuJoCo discipline (pull-on-demand; read BEFORE running any sim/test)

Host RAM is a SHARED pool across every session/loop on this machine (check `free -g`; cap each
round via ROUND_MEM_GB). A leaked/duplicate sim is the #1 OOM cause. This card OVERRIDES any
user-global guidance that says to `pkill -9 -f mujoco` or to create progress.md files.

## Serialize & tear down (hard rules)
- Exactly ONE simulator at a time, globally, across ALL sessions/loops. Never two concurrently.
- BEFORE launch: `pgrep -f "mujoco|vcli"` + `free -g`; if a sim is live or RAM tight, WAIT.
- AFTER every run: `./scripts/sim-teardown`. It uses `rosm nuke --yes` when installed
  (rosm = Vector Robotics' ROS2/sim process manager, a sibling repo, optional on a fresh
  clone) and otherwise falls back to a repo-scoped
  `pkill -u $USER -f 'vector_os_nano\.vcli|launch_explore'`. NEVER `pkill mujoco` — bare
  pkill corrupts sim state and races other sessions.
- Inline sim `bash -c` must NOT pre-`pkill 'vector_os_nano.vcli.cli'` — it self-kills the shell.
- rc=137 == kernel OOM-kill → a sim leaked or two ran; tear down and re-check `free -g`.

## NEVER-KILL-INFRA (hard rule)
- Never kill the loop supervisor, its timeout wrapper, a sibling round, or another session's
  processes. On contention: WAIT or exit non-zero — arbitration belongs to the harness
  (locks, timeouts, scopes), never to the agent. (A round that killed its own supervisor
  wedged a loop for 10.6h on 2026-06-30.)

## Test structure
- Guard: `mujoco = pytest.importorskip("mujoco")` at file top; `importorskip("convex_mpc")` in MPC tests.
- ONE MuJoCoGo2 per test MODULE (`scope="module"`), reset posture between; never per-test in a physics file.

## Interface & assertions
- Speed commands are the ONLY control interface; assert ONLY observable outputs (pos/heading/lidar/camera),
  never joint angles/gait/controller state. Don't assert exact displacement — assert it did NOT fall.

## Sim vs real (one interface, two backends)
- Same API both sides — assert only interface-level observables so tests hold on both:
  sim = `MuJoCoGo2` (`set_velocity`→`_cmd_vel` thread, PD stand/sit, `mj_ray` lidar, `mj.Renderer` cam);
  real = `Go2ROS2Proxy` (ROS2 `/cmd_vel`, odometry pos/heading, Livox MID360, RealSense D435).

## Physics bounds
- Standing z∈[0.20,0.45]; sitting z<0.35; not-fallen z>0.15.

## Acceptance
- Real acceptance = bare `vector-cli` REPL + NL, eyes on the sim (docs/verify.md for the
  contract). Commit a WIP floor BEFORE a long verify; evidence → var/evidence/, never /tmp.
