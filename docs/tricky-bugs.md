# Tricky Bugs — hidden-bug casebook

**This doc records the IMPLICIT/hidden bugs hit during development** — the ones whose
symptom pointed away from the cause, that survived a green test suite, or that hid behind
"every component is correct in isolation". Append-only, newest case first. Keep entries
SHORT: dot points, key facts only (symptom → why hidden → root cause → fix → lesson).
Routine bugs do NOT belong here; git history covers those.

---

## Case 0 — Go2 won't walk (walk + explore "PASS" but dog stays put): casadi missing because `[all]` omitted `[go2]` (2026-06-18)

- **Symptom:** every `walk`/`explore` returns `[PASS]` but the dog doesn't move — stands and drifts ~0.15 m for a ~1 m command, body z destabilizes. Looked like a TARE/nav problem; it was not.
- **Why hidden:** judged by the WRONG signals. `walk` returns PASS on a timer; the bridge `odom=N` is a *message count* (not motion); `nav=ON` + path-count climb regardless of real movement; the MPC solver error was swallowed per-tick. The whole stack reported success while the robot sat still. (Certified "gait works" twice off PASS/odom-count before measuring position.)
- **Root cause:** the convex-MPC gait needs `casadi` (its QP solver). `pyproject` pinned casadi in the `[go2]` extra, but `all = [sim,perception,ik,mcp]` **omitted `go2`**, so a `.[all]` venv never installed casadi. casadi is imported LAZILY inside `convex_mpc.centroidal_mpc` on the first solve, so `connect()` set `_use_mpc=True` (convex_mpc + pinocchio import fine) and the QP then threw EVERY tick (`_MPC_DIAG: qp_ok=0, qp_fail=149`) → zero torque → no walk. "Worked before" = casadi was installed then; a venv rebuild dropped it.
- **Cracked by:** measuring the actual base POSITION delta (0.149 m vs ~1 m), then `VECTOR_MPC_LOG=1` → `qp_fail=149/149`, then `import casadi` → ModuleNotFoundError.
- **Fix:** (1) `pyproject` `all` now includes `go2` so casadi is always installed. (2) `MuJoCoGo2._init_mpc_stack` imports casadi EAGERLY → a missing dep raises at connect → clean fallback, never a silent per-tick stumble. (3) the auto→sinusoidal fallback log is now a WARNING naming the cause + `uv pip install -e .[go2]`. Verified: casadi present → `qp_ok=142, qp_fail=0`, walk delta 0.15 m → 0.57 m.
- **Lesson:** NEVER certify robot motion from PASS / odom-count / nav-flag — measure the actual position/state delta (ground truth). A capability's HARD dep must be in the install set it ships in, or fail loud at connect — never a lazily-imported solver that fails silently every tick.

## Case 1 — Go2 explore gait instability (飘/瘸腿): two-clock skew (2026-06, fixed `d7e158b`)

- **Symptom:** during explore the gait went unstable/limping, step size over/undershoot.
  Worse on a loaded machine (GUI + RViz). Single `walk` skill commands looked fine.
- **Why hidden:** every component was correct in isolation. Ruled out BY DATA before the
  real cause: code regression (gait + bridge byte-identical to a known-good commit),
  duplicate cmd sources (cmd log: single MainThread @19 Hz, smooth), duplicate physics
  daemons (count=1), mujoco 3.1.6-vs-3.9, pinocchio 3.9-vs-4.0 (dynamics byte-identical),
  swallowed QP failures (2645/2645 ok), solver tolerance, velocity smoothing.
- **Root cause:** a CROSS-DOMAIN interaction invisible in either domain alone. The physics
  daemon ran compute-bound at ~0.65× real-time, while `go2_vnav_bridge._follow_path`
  ramped velocity by fixed per-tick increments on a 20 Hz WALL timer → the commanded
  velocity profile slewed ~1.5× faster in the gait's own (sim) time than it was tuned
  for → MPC gait destabilized.
- **Cracked by:** measuring before theorizing — tiny env-gated diagnostics
  (`VECTOR_PHYS_LOG` printed `sim/wall≈0.65x` + daemon count; `VECTOR_CMDVEL_LOG` proved
  one clean command source). The ratio number WAS the diagnosis.
- **Fix:** integrate every ramp/accumulator in `_follow_path` against actual sim-dt
  (`hardware/sim/sim_clock.sim_tick_dt` + `MuJoCoGo2.get_sim_time()`); the wall-escape
  state machine converted to sim time too (adversarial review caught the remaining mixed
  time bases). sim/wall=1 → byte-identical; no sim clock (real HW) → nominal fallback.
- **Lesson:** a wall-clock controller commanding a simulation must integrate by sim-dt.
  "Sim runs slower than real-time" silently changes the meaning of every per-tick
  constant — and no unit test catches it, because each side is correct alone.

## Case 2 — MPC "stands but won't walk": errors swallowed by `except: pass` (2026-06)

- **Symptom:** the dog stood up but never walked. No error, no warning, anywhere.
- **Why hidden:** the QP fallback in the per-tick control loop was a bare
  `except Exception: pass` — it ate the SAME exception every single tick, so a hard
  dependency break presented as silent physical misbehavior instead of a stack trace.
- **Root cause:** external `convex_mpc` was written for numpy<2; the rebuilt venv had
  numpy 2.x, which hard-errors on `(N,1)`-array→scalar-slot assignment. The solver threw
  on every tick → no torque ever computed → PD hold only.
- **Fix:** shape-only fixes at the source (`compute_com_x_vec` → `(12,)`,
  `compute_current_mask` → `(4,)`); the except clauses now count+log failures
  (`VECTOR_MPC_LOG`). NOTE: convex_mpc is still not pinned in `pyproject.toml`.
- **Lesson:** `except: pass` on a control path converts loud failures into silent wrong
  behavior. Always count/log swallowed exceptions — "0 failures" must be provable.

## Case 3 — Explore stack silently ran on the WRONG interpreter: dead PYTHONPATH (2026-06, fixed `13a9429`)

- **Symptom:** none, at first — explore "worked", but on system python3 (mujoco 3.6)
  instead of the repo venv (mujoco 3.9 / numpy 2.4.6 / pinocchio 4.0) where the MPC fix
  had been verified.
- **Why hidden:** the uv rebuild renamed `.venv-nano` → `.venv`; the launch scripts'
  PYTHONPATH pointed at the deleted dir. Python silently ignores nonexistent path
  entries and falls back to whatever system site-packages provide.
- **Root cause:** the venv path was hardcoded in 12+ scripts with no existence check and
  no single source.
- **Fix:** all launch/test scripts + `vector-sim` + `verify_pick_top_down.py` prefer
  `.venv` with a `.venv-nano` fallback; CLAUDE.md build line updated.
- **Lesson:** PYTHONPATH to a missing dir fails silent — when debugging "version
  mismatch" symptoms, print `module.__file__` to verify WHICH copy is actually loaded;
  single-source interpreter resolution.

## Case 4 — Grasp picked a brown table sliver, not the green cylinder: saturation-bridge blob FUSION (2026-06-20, fixed in front_object.py `_open`)

- **Symptom:** the deictic grasp aimed ~12cm off — a 116px brown sliver between the green
  and blue cylinders — only when the Piper arm was connected (go2+piper). 3 rounds chased
  it as robot SELF-OCCLUSION (the arm in the head camera): site-alpha=0, geomgroup hide,
  segmentation self-mask — every "fix" was a no-op because the cause was not the arm.
- **Why hidden (pointed away from cause):** the symptom CORRELATED with connecting the arm,
  so it looked like an arm-view problem. It wasn't: connecting the arm only nudges the dog's
  settle by mm, which shifts WHICH brown table sliver wins the (already-broken) selection.
  The green cylinder was being lost in BOTH configs; one earlier render happened to let green
  win, manufacturing a false "go2-only works / full broken" contrast.
- **Root cause:** `front_object.py` `_SAT_MIN=140` is BELOW the brown table's saturation
  (med~132, **p90~146, max~160**). The table therefore passes the saliency mask in thin
  1-3px chains that 8-connectivity FUSES the vivid cylinders + table into one giant blob —
  so the central green cylinder stops existing as its own connected component, and the
  "most-central blob" fallback grabs a brown table sliver. (Verified: at sat≥140 the
  green-centre pixel lands in a 2105px blob spanning the whole table; at sat≥160 it becomes
  a clean 757px blob.)
- **Fix:** morphological OPENING (`_open`, erode→dilate, 3×3) on the salient mask before
  connected components — severs sub-kernel bridges so each object survives as its own
  component, threshold-independently (stable for sat_min 140-155; a raw threshold flips
  central→wrong-object within ~5 sat units, and the table reaches 160). Honest, pose/colour/
  group-agnostic. REAL-SIM full-config: front=755px GREEN, grasp **2.3cm** (was 12.2cm); full
  motion EE reaches (10.97,3.01,0.31) over the green cylinder at (11,3).
- **Lesson:** when a saliency THRESHOLD overlaps the background, the failure shows up as a
  CONNECTED-COMPONENT topology bug (blobs fuse), not as a thresholding bug — and the wrong
  winner drifts with tiny scene changes, faking a "config A works, config B doesn't" signal.
  Before blaming an occluder, dump the actual candidate blobs (area/centroid/colour) the
  selector considers; the central object simply not being in the list is the tell. Fix the
  topology (opening) rather than chasing the threshold.
