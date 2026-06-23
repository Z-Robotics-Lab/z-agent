# Tricky Bugs — hidden-bug casebook

**This doc records the IMPLICIT/hidden bugs hit during development** — the ones whose
symptom pointed away from the cause, that survived a green test suite, or that hid behind
"every component is correct in isolation". Append-only, newest case first. Keep entries
SHORT: dot points, key facts only (symptom → why hidden → root cause → fix → lesson).
Routine bugs do NOT belong here; git history covers those.

---

## Case 6 — placed_count never grounds when placing onto the pedestal: `_LIFT_MIN_Z=0.10` excludes the z=0.32 table surface (2026-06-21)

- **Symptom (latent, caught by design-probe before coding):** the obvious place target — a "clear spot on the pedestal at a different y", e.g. (10.85, 2.7, **0.32**), as the task brief itself suggested — would make a *successful-looking* place (skill.success=True, placed_at reported, weld released) grade the PLACE verify FALSE forever: `placed_count(region)` returns **0**.
- **Why hidden:** every component looks correct — the arm reaches the pedestal-top target, the gripper opens, the object sits where asked, skill.success=True. The failure is silent and lives in the ORACLE's resting-height gate, not in the place motion. `make_placed_count` (arm_sim_oracle.py:220) only counts objects with `z < _LIFT_MIN_Z` (0.10) — "resting on the FLOOR". The green's pedestal top is z=0.28 (object centre 0.32), so a place back onto the pedestal leaves the object ABOVE the gate → counted as "still lifted / in flight" → 0. The brief's own suggested target was infeasible against the existing oracle.
- **Compounding tension:** the D34 kinematics say the Piper reaches FURTHER the HIGHER it goes (~0.49 m fwd at z~0.32 vs ~0.22 m at z~0.25), which biases toward placing HIGH — exactly where placed_count can't ground. So "reach feasibility" and "placed_count semantics" pull opposite ways.
- **Resolved by:** an empirical reach-grid probe (NOT a guess) before writing any code — measured that the FLOOR (z~0.05) IS reachable from the grasp standoff (dog jammed x~10.41) across a broad central corridor (tx 10.55-10.80, ty 2.70-3.40). Place target = floor (10.60, 2.70, 0.05); green settles to z~0.0399 < 0.10 → placed_count((10.45,2.55,10.75,2.85))==1, GROUNDED.
- **Lesson:** a verify oracle encodes IMPLICIT geometric assumptions (here "placed == on the floor"). Before choosing a place target, read the oracle's gate (`_LIFT_MIN_Z`) and MEASURE that a target satisfying BOTH reach AND the oracle exists — never assume the task brief's suggested coordinate is oracle-valid. Do NOT "fix" it by loosening the gate (rule 5: verify only ever stricter). Probe first; the geometry decides the design.

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

## Case 5 — GREEN cylinder INVISIBLE to perception (0 px): the TABLE's near top edge occluded it, not the arm (2026-06-20, fixed by object placement in go2_room.xml)
- SYMPTOM: after R18 moved objects onto a TALL pick pedestal (top z=0.28) to make them arm-reachable, the central GREEN cylinder rendered **0 green pixels** in the d435 head cam while RED/BLUE (same z, same distance) rendered fine. front_object then picked a neighbour/table-sliver. Looked exactly like the D29-31 "arm self-occlusion" symptom again.
- FALSE TRAILS (ruled out by probes): NOT the arm — green stayed 0 px at every arm pose (home / stow / folded). NOT a colour/saturation issue — at green's own projected pixel the depth read **3.708 m** (the far doorway), i.e. the camera saw straight THROUGH where green should be. Green was physically present at (10.82, 3.0, 0.32) (confirmed body xpos) — it just wasn't on that line of sight.
- ROOT CAUSE: the d435 (z~0.38, shallow down-tilt) looks at the table top at a grazing angle. An object within ~6 cm of the table's NEAR TOP EDGE is OCCLUDED by that edge — the sightline to its body grazes the lip. Green at x=10.82 sat 2 cm onto a table whose near edge is 10.80 -> occluded; red/blue at x=10.90 (10 cm on) cleared it. Empirically: green at x<=10.82 -> 0 px; x>=10.88 -> ~1000 px. A TALL table makes this far worse than the old low table (a higher lip grazes more of the object).
- FIX: object placement, not code — keep objects >=8 cm BACK from the near edge (final: near edge 10.80, green at 10.88). Tension with reach (objects must also be <= the EE's forward limit) + with no-knock (objects must be behind the dog's jammed bumper) resolved by a tall pedestal (object centre z=0.32 = reachable height) + 8 cm setback.
- LESSON: when ONE object of several identical ones is invisible, sample the DEPTH at its projected pixel before blaming the robot's own body — depth >> object distance means a static-scene occluder (here the table's own edge), and the differentiator is the object's position relative to that edge, not anything about the robot. A taller support surface trades reach for self-occlusion of its own near edge.

## Case 6 — nav+grasp "never grounds" was a MISSING DECLARED DEP + a model-API shape bug silently degrading EdgeTAM to a box-rect mask (z mislocalized low), NOT an off-axis IK / heading problem (2026-06-23, R39)
- SYMPTOM: the full nav->dock->perceive->grasp chain completed but holding_object stayed False; the perceived grasp-z was LOW (0.13, 0.044 vs true 0.32) so the gripper closed below the can. A focused A/B perceive probe (run with EdgeTAM healthy) showed a clean 2.8cm grasp and pointed the diagnosis at "off-axis lateral IK after the dock" — a red herring.
- FALSE TRAIL: the A/B probe and the end-to-end chain ran the SAME perceive code, so "perception is fine, the residual is IK/standoff" looked airtight. It wasn't — the two runs differed in ONE invisible way: whether EdgeTAM actually segmented.
- ROOT CAUSE (two layers): (1) `timm` was declared in pyproject but absent from `.venv` -> EdgeTAM failed to LOAD -> box-rect fallback mask; the depth centroid then averaged the can with the table surface inside the loose box -> z collapsed toward the table. (2) After installing timm, EdgeTAM LOADED but `float(object_score_logits[i])` raised (transformers>=5 returns (N,1)) -> still box-rect every call. The grep-able log line `[GO2-PERCEPT] EdgeTAM unavailable (...) — box-rect fallback` was the tell, present in the end-to-end log but NOT in the A/B probe log.
- LESSON: when two runs of the SAME perception code disagree, suspect a SILENTLY-DEGRADING optional model path before re-theorizing the geometry. A box-rect (whole-bbox) mask is NOT an adequate substitute for a tight segmentation mask for depth-centroid grasping — it drags z toward the nearest large surface (the table). Two reinforcing guards for R40: (a) make a segmenter-degrade LOUD at the grasp boundary (perception self-reports box-rect; the chain should flag/reject a low-z grasp rather than close on the table), and (b) keep optional model deps env-synced (a declared-but-uninstalled dep degrades quality with zero error at the call site).
