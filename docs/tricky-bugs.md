# Tricky Bugs — hidden-bug casebook

Records the IMPLICIT/hidden bugs only — the ones whose symptom pointed AWAY from the cause,
that survived a green test suite, or hid behind "every component is correct in isolation".
Append-only, newest first. Entries are terse dot-points (symptom → why hidden → root → fix →
lesson) — key facts only. Routine bugs (typos, missing imports, obvious config) do NOT belong
here; git history covers them, and covers the full prose of these once trimmed.
Cap: ≤15 cases. On overflow, fold the OLDEST case to one line + its commit hash under a
trailing `## Folded` list.

---

## Case 14 (FOV) — a short object masks at 3.9 m but VANISHES at the 0.9 m grasp standoff (camera FOV, not colour) (2026-06-29, arch/plug-and-play)
- Symptom: far fetch grounds for the green/blue BOTTLES but the red object returns no_detections at re-perceive; instinct: "the HSV red wrap-around hue gate is the weak one".
- False trail (ruled out by the depth+mask log): the red HSV mask fired ~1000 px on the red object at 3.9 m AND the seed localized it AND the facing turn fired. Red hue is fine.
- Root cause: the red object is a CAN — physically SHORTER than the bottles. mask_px went 1000@3.9m → 0 at the ~0.9 m standoff: a close, short object falls BELOW the head camera's downward vertical FOV (the camera looks OVER it). So the mask VANISHES as the dog gets CLOSER — counter to intuition.
- Fix direction (seed, not yet done): for short objects raise camera tilt or widen the grasp standoff to keep them in the vertical FOV at grasp range.
- Lesson: "detected far, lost near" is a FOV/geometry signature, not a detector/colour weakness — check object HEIGHT vs camera pitch and the near-field vertical frustum before touching the colour gate. Mask px rising with range then dropping to 0 as you approach localizes it to FOV.

## Case 13 (mobile_pick) — far flail to the ORIGIN was a position-less detection stored at (0,0,0), not a nav bug (2026-06-29, arch/plug-and-play)
- Symptom: a model-routed far fetch that picked `mobile_pick` failed `nav_failed`, dog driving toward ~(0.5, 0.15) = the ORIGIN, nowhere near the bottle at (13.86, 3.0). "nav_failed"+"drives to origin" pointed at navigation/frame.
- False trail (ruled out by code-read): `_populate_pickables_from_mjcf` only runs under the heavy ROS2 GT path, not the VECTOR_NO_ROS2 rig the probe used.
- Root cause (detect.py): DetectSkill defaults `x,y,z=0,0,0; has_3d=False`, then tries to read a 3D pose; a FAR object yields no depth → x,y,z stay at the (0,0,0) SENTINEL, and the object was ADDED to world_model ANYWAY. mobile_pick's `_resolve_target` found that phantom and navigated to origin. A 2D-only detection was stored as a TARGETABLE object at the origin.
- Fix: additive `ObjectState.has_position` (default True); DetectSkill sets it False for a 2D-only detection and preserves any prior position; pick skips position-less objects → fast honest `object_not_found`.
- Lesson: a "drives to origin / nav_failed" symptom is often a DEFAULT-SENTINEL leak — a struct field left at its 0-init default and then USED as if real. Never store a position-less observation as a positioned, targetable one; separate EXISTENCE from HAS-A-USABLE-POSITION.

## Case 12 (far-fetch) — "no_detections" was a nav TERMINAL-HEADING bug, not perception/colour (2026-06-29, arch/plug-and-play)
- Symptom: model-routed far fetch (`把绿色的瓶子拿过来`, VECTOR_FETCH_FAR=1) intermittently ended `RAN / no_detections`. The string `no_detections` + "grounding-dino is English" history pointed at perception/colour.
- False trails (ruled out by a logged probe): seed colour/query localized the real bottle every time; backend was MPC (casadi+pinocchio present); far-table geom byte-identical to the near table that masks fine.
- Decisive probe: a faithful skill-direct repro with the CLI's EXACT sim config GROUNDED (2073 green px at standoff); the failing cli run masked 0 at a near-identical depth profile → the only thing that flips an identical-depth frame to 0 is the bottle being out of frame = a different arrival HEADING.
- Root cause: FAR's `navigate_to` has NO terminal-heading control, so the dog arrives at an arbitrary heading; the re-perceive relies on a one-directional ~200° scan (6×0.6 rad, +vyaw only) → a bottle in the uncovered ~160° arc is never faced → mask=0 → no_detections. Grounds-or-not = luck of arrival heading.
- Fix: the recovery KNOWS the target xy (the seed) — deterministically TURN TO FACE it via `_grasp_ready_repose` before re-perceiving (skill-level; kernel/moat untouched). 3/3 skill-direct.
- Lesson: a perception-shaped error string can be a NAV-pose bug. When a "can't see it" failure is intermittent at a fixed location, suspect arrival HEADING before colour/detector/occlusion — prove it by comparing depth profiles (identical depth + different mask ⇒ framing/heading). When you KNOW the target xy, face it, don't search.

## Case 11 — a verdict-time snapshot SIGSEGV'd the whole bare-cli turn: MuJoCo GL is THREAD-BOUND + a control thread was stepping live mjData (2026-06-26, ADR-002 Stage 1)
- Symptom: adding a same-process snapshot hook in cli `_emit` (env-gated by `VECTOR_SNAPSHOT_DIR`) made a real `--sim-go2 --native-loop` turn die with exit=-11 (SIGSEGV) BEFORE `VECTOR_VERDICT`, on BOTH the ROS2 and in-process paths.
- False trails (ruled out): NOT the heavy ROS2 stack (in-process crashed too); NOT "a 4th EGL context". Decisive probe: a CONTROL run with the hook OFF emitted a clean verdict → the segfault was specifically MY render.
- Root cause (two thread-safety violations): (1) MuJoCo's GL context is THREAD-BOUND — the persistent `_cam_renderer`/`_seg_renderer` were created on a worker thread, so touching them from the emit (main) thread = cross-thread GL → segfault. (2) a control thread keeps stepping the LIVE `mjData`; rendering it concurrently = torn read → segfault.
- Fix: render from an ISOLATED `MjData` copy with a FRESH `mj.Renderer` created ON the emit thread; wrap the hook so any failure returns None (a snapshot must never crash the verdict).
- Lesson: when adding ANY render/observe call into an existing sim process, assume there is already a GL context owned by another thread AND a thread mutating `mjData`. Never reuse a renderer across threads, never render live data — copy `qpos` into a throwaway `MjData` and render that on your own thread. Isolate the crash with a hook-OFF CONTROL run before blaming context count.

## Case 10 — Fakeable grasp graded GROUNDED by a self-written marker file, not the gripper (2026-06-24, D69)
- Symptom: bare-cli NL grasp on go2+arm graded verified=True with the gripper empty — model wrote `grabbed.txt` via `file_write`, verified `file_exists('grabbed.txt')`.
- Why hidden: every gate fired correctly for the WRONG reason. `file_exists` is a legit PREDICATE oracle → GROUNDED; actor-causation correctly NOT_GRADED (not a robot predicate); the coord turn-gate failed OPEN (no coord goal). The false-green was the ABSENCE of a gate, not a bug in any present one.
- Root cause: (1) the kernel dev tool `file_write` was offered as a motor tool in the robot world; (2) no gate bound a physical-GRASP goal to a GT manipulation oracle the way D15/D16 bind a coord goal to `at_position`.
- Fix (D69): robot world DROPS file_write/edit/bash from the action surface + persona "never fake a physical action with a file/shell"; stricter object-goal turn-gate in `evidence_passed` requires a NECESSARY `holding_object`/`placed_count` conjunct.
- Lesson: an oracle honest for one domain is a FABRICATION VECTOR for another — bind the goal CATEGORY to an oracle only true if THAT work happened, and make an un-authorable GT oracle MANDATORY per goal class (mirror the coord D15/D16 pattern). A generic dev tool is not a generic ACTION.

## Case 9 — Piper IK base-sync read a LITERAL `qpos[0:19]`; broke when attach moved the go2 freejoint 0→21 (2026-06-24, S3b)
- Symptom: none in unit/spike (all green, compiled model byte-identical) — but the grasp silently targets the WRONG frame once the dog moves off-spawn under the new attach scene.
- Why hidden: a byte-identical COMPILED-MODEL check (nq/nv/names/defaults) cannot see a runtime absolute-qpos-INDEX assumption in a CONSUMER. Under `MjSpec.attach` the room's 3 pickable freejoints occupy [0:21] and go2 sits at [21], so `live_qpos[0:19]` copied PICKABLES → IK ran FK on a stale base. At spawn both matched (default), so it only bites AFTER motion.
- Fix: `_lo = go2._mj.layout.root_qpos_adr; _n = 7 + num_actuated; ik_data.qpos[_lo:_lo+_n] = live_qpos[_lo:_lo+_n]` (DofLayout-derived; byte-identical for legacy, lo=0).
- Lesson: byte-identical compiled MODEL ≠ byte-identical qpos ORDER. After any layout change, blast-radius-grep ALL absolute `qpos[N]`/`qvel[N]` reads in CONSUMERS (not just the driver) and e2e a MOVED (not spawn) pose — a spawn-only test passes even when broken.

## Case 8 — arm-stow guarded on `model.nq >= 27` mis-fired for BARE go2 — room pickables inflate nq (2026-06-24, S3b)
- Symptom: surfaced only when attach flipped the scene-build — bare-go2 connect() raised `broadcast (8,) into shape (0,)` at arm-stow. Blamed the new attach build.
- Why hidden: under the legacy `<include>` build the slice was in-bounds and `_PIPER_STOW_QPOS` is all-zeros → a SILENT no-op (zeroed pickable qpos that get re-placed). Attach's reorder moved it out of bounds → the latent bug became a hard crash.
- Root cause: `nq >= 27` assumed "arm ⇒ nq≥27". FALSE: the room's 3 `pickable_*` freejoints (7 qpos each) put BARE go2 at nq=40 in BOTH builds — qpos count is a SCENE property, not a robot-morphology discriminator.
- Fix: gate on `model.nu >= 19` (arm adds exactly 7 ACTUATORS; nu=12 bare / 19 arm, scene-independent); address the slice as `joint_qpos_start + num_actuated`.
- Lesson: never discriminate ROBOT morphology by `nq` (contaminated by scene freejoints) — use `nu` or a named-element probe. An in-bounds + all-zeros write is the textbook silent latent bug.

## Case 7 — placed_count never grounds on the pedestal: `_LIFT_MIN_Z=0.10` excludes the z=0.32 table top (2026-06-21)
- Symptom (latent, caught by a design-probe before coding): the obvious place target (a clear spot on the pedestal top, ~z=0.32, as the brief itself suggested) makes a successful-LOOKING place (skill.success, weld released) grade the PLACE verify FALSE forever — `placed_count(region)` returns 0.
- Why hidden: every component looks correct (arm reaches, gripper opens, object sits where asked). The failure lives in the ORACLE's resting-height gate: `make_placed_count` counts only objects with `z < _LIFT_MIN_Z` (0.10) = "on the floor"; a pedestal-top place stays above the gate → 0.
- Compounding: D34 kinematics reach FURTHER the HIGHER it goes → biases toward placing high, exactly where placed_count can't ground.
- Resolved by: an empirical reach-grid probe (not a guess) → the floor (z~0.05) IS reachable from the grasp standoff; place target = floor (10.60, 2.70, 0.05) settles to z~0.04 < 0.10 → placed_count==1, GROUNDED.
- Lesson: a verify oracle encodes IMPLICIT geometry ("placed == on the floor"). Read the oracle's gate and MEASURE that a target satisfying BOTH reach AND the oracle exists — never trust the brief's suggested coordinate. Do NOT loosen the gate (rule 5: verify only ever stricter); probe first, geometry decides the design.

## Case 6 — nav+grasp "never grounds" = a MISSING declared dep + a model-API shape bug degrading EdgeTAM to a box-rect mask (2026-06-23, R39)
- Symptom: the full nav→dock→perceive→grasp chain completed but holding_object stayed False; perceived grasp-z was LOW (0.13/0.044 vs true 0.32) so the gripper closed below the can. An A/B perceive probe showed a clean 2.8 cm grasp → pointed at "off-axis lateral IK", a red herring.
- False trail: the A/B probe and the e2e chain ran the SAME perceive code, so "perception fine, residual is IK" looked airtight — they differed in ONE invisible way: whether EdgeTAM actually segmented.
- Root cause (two layers): (1) `timm` declared in pyproject but absent from `.venv` → EdgeTAM failed to LOAD → box-rect fallback → depth centroid averaged can+table → z collapsed. (2) After installing timm, `float(object_score_logits[i])` raised (transformers≥5 returns (N,1)) → still box-rect. Tell: grep-able `[GO2-PERCEPT] EdgeTAM unavailable — box-rect fallback`, present in the e2e log but NOT the A/B log.
- Lesson: when two runs of the SAME perception code disagree, suspect a SILENTLY-degrading optional model path before re-theorizing geometry. A box-rect mask is not an adequate substitute for a tight segmentation for depth-centroid grasping. Guards: make a segmenter-degrade LOUD at the grasp boundary; keep optional model deps env-synced.

## Case 5 — GREEN cylinder INVISIBLE (0 px): the TABLE's near top edge occluded it, not the arm (2026-06-20)
- Symptom: after objects moved onto a tall pedestal (top z=0.28), the central GREEN rendered 0 px in the head cam while RED/BLUE (same z/distance) rendered fine → looked like arm self-occlusion again.
- False trails (ruled out by probes): NOT the arm (green 0 px at every arm pose); NOT colour/saturation (depth at green's projected pixel read 3.708 m = the far doorway, i.e. camera saw THROUGH it). Green was physically present, just not on that line of sight.
- Root cause: the d435 (z~0.38, shallow down-tilt) grazes the table top; an object within ~6 cm of the near TOP EDGE is occluded by the lip. Green at x=10.82 (2 cm on) → occluded; red/blue at x=10.90 (10 cm on) → clear. Empirically x≤10.82 → 0 px, x≥10.88 → ~1000 px.
- Fix: object placement (not code) — keep objects ≥8 cm back from the near edge (final: near edge 10.80, green at 10.88).
- Lesson: when ONE of several identical objects is invisible, sample DEPTH at its projected pixel before blaming the robot — depth ≫ object distance means a static-scene occluder (here the table's own edge). A taller support surface trades reach for self-occlusion of its own near edge.

## Case 4 — Grasp picked a brown table sliver, not the green cylinder: saturation-bridge blob FUSION (2026-06-20)
- Symptom: the deictic grasp aimed ~12 cm off (a 116px brown sliver) only when the Piper arm was connected. 3 rounds chased it as robot SELF-OCCLUSION (arm in head cam) — every fix a no-op.
- Why hidden: the symptom CORRELATED with connecting the arm, so it looked like an arm-view problem. It wasn't: the arm only nudges the dog's settle by mm, shifting WHICH brown sliver wins an already-broken selection. Green was lost in BOTH configs; one render let green win, faking a "go2-only works" contrast.
- Root cause: `front_object._SAT_MIN=140` is BELOW the brown table's saturation (p90~146, max~160) → the table passes the mask in 1-3px chains that 8-connectivity FUSES cylinders+table into one blob, so central green stops being its own component and the "most-central blob" fallback grabs a table sliver.
- Fix: morphological OPENING (erode→dilate, 3×3) on the salient mask before connected-components — severs sub-kernel bridges threshold-independently. Full-config: front=755px GREEN, grasp 2.3 cm (was 12.2).
- Lesson: when a saliency THRESHOLD overlaps the background, the failure is a connected-component TOPOLOGY bug (blobs fuse), and the wrong winner drifts with tiny scene changes, faking "config A works, B doesn't". Dump the candidate blobs (area/centroid/colour); the central object simply not being in the list is the tell. Fix the topology, not the threshold.

## Case 3 — Explore stack silently ran on the WRONG interpreter: dead PYTHONPATH (2026-06, `13a9429`)
- Symptom: none at first — explore "worked", but on system python3 (mujoco 3.6) instead of the repo venv (mujoco 3.9) where the MPC fix was verified.
- Why hidden: the uv rebuild renamed `.venv-nano`→`.venv`; scripts' PYTHONPATH pointed at the deleted dir. Python SILENTLY ignores nonexistent path entries and falls back to system site-packages. Venv path was hardcoded in 12+ scripts with no existence check.
- Fix: all launch/test scripts prefer `.venv` with a `.venv-nano` fallback; single source.
- Lesson: PYTHONPATH to a missing dir fails silent — when debugging "version mismatch" symptoms, print `module.__file__` to verify WHICH copy loaded.

## Case 2 — MPC "stands but won't walk": errors swallowed by `except: pass` (2026-06)
- Symptom: the dog stood but never walked. No error, no warning, anywhere.
- Why hidden: the per-tick QP fallback was a bare `except Exception: pass` — it ate the SAME exception every tick, so a hard dependency break presented as silent physical misbehavior, not a stack trace.
- Root cause: external `convex_mpc` was written for numpy<2; the rebuilt venv had numpy 2.x, which hard-errors on `(N,1)`→scalar assignment → the solver threw every tick → PD-hold only.
- Fix: shape-only fixes at source; the except clauses now count+log failures (`VECTOR_MPC_LOG`).
- Lesson: `except: pass` on a control path converts loud failures into silent wrong behavior. Always count/log swallowed exceptions — "0 failures" must be provable.

## Case 1 — Go2 explore gait instability (飘/瘸腿): two-clock skew (2026-06, `d7e158b`)
- Symptom: during explore the gait went unstable/limping; worse on a loaded machine (GUI+RViz); single `walk` commands looked fine.
- Why hidden: every component correct in isolation; ruled out BY DATA (byte-identical gait/bridge, single cmd source @19 Hz, one physics daemon, identical dynamics libs, 2645/2645 QP ok).
- Root cause: a CROSS-DOMAIN interaction invisible in either domain alone — the physics daemon ran at ~0.65× real-time while `_follow_path` ramped velocity by fixed per-tick increments on a 20 Hz WALL timer, so the profile slewed ~1.5× faster in sim-time than tuned for → MPC destabilized.
- Cracked by: measuring before theorizing (`VECTOR_PHYS_LOG` printed sim/wall≈0.65×; the ratio WAS the diagnosis).
- Fix: integrate every ramp/accumulator against actual sim-dt (`sim_clock` + `get_sim_time()`); sim/wall=1 → byte-identical.
- Lesson: a wall-clock controller commanding a simulation must integrate by sim-dt. "Sim slower than real-time" silently changes the meaning of every per-tick constant — no unit test catches it, each side is correct alone.

## Case 0 — Go2 won't walk (walk/explore "PASS" but dog stays put): casadi missing — `[all]` omitted `[go2]` (2026-06-18)
- Symptom: every `walk`/`explore` returns [PASS] but the dog doesn't move (~0.15 m for a ~1 m command). Looked like a TARE/nav problem.
- Why hidden: judged by the WRONG signals — `walk` PASSes on a timer, `odom=N` is a message count (not motion), `nav=ON` regardless of movement, the MPC error was swallowed per-tick. The whole stack reported success while the robot sat still (certified "gait works" twice off PASS/odom before measuring position).
- Root cause: convex-MPC needs `casadi` (its QP solver), pinned only in the `[go2]` extra, but `all=[sim,perception,ik,mcp]` OMITTED `go2` → `.[all]` venv had no casadi. casadi imports LAZILY on first solve, so connect() set `_use_mpc=True` then the QP threw EVERY tick (qp_fail=149/149) → zero torque.
- Fix: `all` now includes `go2`; `_init_mpc_stack` imports casadi EAGERLY (fails loud at connect, clean fallback); fallback log names the cause + install cmd.
- Lesson: NEVER certify robot motion from PASS/odom-count/nav-flag — measure the actual position/state DELTA (ground truth). A capability's hard dep must be in the install set it ships in, or fail loud at connect — never a lazily-imported solver that fails silently every tick.
