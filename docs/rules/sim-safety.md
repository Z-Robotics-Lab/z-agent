# Sim Safety — MuJoCo discipline (pull-on-demand; read BEFORE running any sim/test)

Host = 64 GB RAM SHARED across every session/loop. A leaked/duplicate sim is the #1 OOM cause.

## Serialize & tear down (hard rules)
- Exactly ONE simulator at a time, globally, across ALL sessions/loops. Never two concurrently.
- BEFORE launch: `pgrep -f "mujoco|vcli"` + `free -g`; if a sim is live or RAM tight, WAIT.
- AFTER every run: `rosm nuke --yes`. NEVER `pkill mujoco` (corrupts state, races sessions).
- Inline sim `bash -c` must NOT pre-`pkill 'vector_os_nano.vcli.cli'` — self-kills the shell.
- rc=137 == kernel OOM-kill → a sim leaked or two ran; nuke and re-check `free -g`.

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
- Real acceptance = bare `vector-cli` REPL + NL, eyes on the sim. Commit a WIP floor BEFORE a long verify.
