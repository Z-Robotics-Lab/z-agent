# LESSONS — do-not-repeat distillate (ORIENT step 3; one line each, pointer-terminated)

Append one line per lesson (round agents); review rounds consolidate. A line may be dropped
only if its D#/E#/commit pointer resolves in the ledger or git. Details live at the pointer.

## Refuted (do NOT retry unless the stated condition changed)
- "Model-sensitivity ceiling" on fetch was a HARNESS artifact, not the model — control the
  harness before concluding model capability → D171 refuted by D174.
- "Red grasp-robustness ceiling" was a one-campaign transient (8/8 after); 0/3 in a single
  campaign is never a ceiling — re-run with the correct NL term + skill-direct probe → D172
  refuted by D173/DEBUG.md.
- "BYO-model over-caution blocks tool-calls" — refuted by a positive control; gemini/mistral
  no-tool-call is model behaviour, not plumbing (tools passed, llama tool-called same path)
  → D179 refuted by D180, fb6ae77.
- OpenRouter `/key` `limit_remaining` is rate-limit headroom, NOT deposited credit — probe
  balance with one real turn before concluding "funded" → D181.
- Any rate measured through `-p`/`--sim-go2` flag paths is NOT a bare-REPL face number; all
  pre-D163 acceptance rates were downgraded wholesale for this → D163/D164.

## Hazards & confirmed constraints
- repl_accept MODE=both cross-contaminates verdicts between fetch and place phases — run
  single-mode campaigns for acceptance numbers → D181 red-team.
- The grasp oracle `holding_object(target)` certifies held==NAMED, not named==HUMAN-INTENT:
  the actor authors the target string, so adversarial-NL colour fidelity is witness-certified
  only (queued spine gate: world-owned NL→object grounder) → D182.
- grounding-dino is not colour-selective on the VLN mat: GROUNDED VLN acceptance needs the
  GT-backed `near_object` predicate (queued CEO gate), not the raw box → D178.
- An in-process acceptance claim must show `launch_explore` was never seen (proves the
  in-process path actually ran) → D181.
- ONE sim at a time, tear down via scripts/sim-teardown, never `pkill mujoco`, never kill
  supervisor/siblings → docs/RULES.md sim-safety (10.6h wedge, 2026-06-30).
- A green unit suite, a PASS timer, an odom count, a nav flag — none of them certify motion;
  measure the position/state DELTA → #Casebook Case 0.
- A `claude -p` round can die MID-FLIGHT on an API disconnect; the protocol contains it:
  bank-at-VERIFY keeps the results, post-check quarantines, next agent adopts per ROUND.md
  §1a. Rounds must bank rows the moment they exist — prose can always be reconstructed → R183.
- NEVER run pytest unbounded: tests that patch time.sleep turn wall-clock loops into
  full-speed spins and MagicMock call-recording grows ~GB/s (test_isaac_sim_proxy nav class
  OOM'd the 64G host 2026-07-01); ALWAYS `scripts/run-tests` (MemoryMax scope) → E18.
- The ledger is append-only, so a provisional row's `status` is NEVER rewritten; §1b
  adjudication = APPEND a later row whose `supersedes` points back. checks_schema.py's
  provisional age-check must exempt an already-superseded row or it nags forever and wedges
  every future round once age>2 (R187: R184 row superseded R186, flagged R187) → E24/D183.
- ORDINAL/positional NL ("最右边的瓶子") CAN ground: the model resolves rightmost→blue (the
  non-central, dog's-right bottle) via `describe_scene`(VLM)+`detect`, then perception_grasp.
  BUT it is model-STRATEGY-fragile — it only works if the model PRE-RESOLVES the ordinal to a
  colour before the colour-keyed `perception_grasp` (raw "the rightmost bottle" query the CV
  resolver can't parse). `detect_objects` returns names+confidence, NO positions. Ordinal→object
  fidelity is WITNESS-only (D182 gap: oracle certifies held==named, not named==intent) → E25.
- g1_accept.py GREEN honest-negative (no groundable green in g1's spawn view) is CORRECT (0/14,
  verified=False, NO false-green) but the model FLAILS ~14 detect/navigate/verify turns before
  `finish` → blows a 400s harness budget (R190 skeptic re-run timed out on the GREEN turn; RED
  GROUNDED 1/1 was fine). The honest-negative is right; the give-up LATENCY is the cost — cap
  turns or prompt an earlier honest-stop before the next g1 skeptic re-run → R190.

## Recipes (proven invocations — copy, don't re-derive)
- Bare-REPL NL acceptance, in-process sim: `VECTOR_NO_ROS2=1 MUJOCO_GL=egl` +
  `tools/acceptance/repl_accept.py` (MODE=fetch|place|neg|combo); env from .env.example → D181/D182.
- g1 headless under the bare-REPL face needs `MUJOCO_GL=egl` (suppresses the GLFW viewer)
  → 010a998.
- Verdict-time frames: render an isolated MjData copy with a fresh Renderer ON the emit
  thread; a snapshot must never crash the verdict → #Casebook Case 11.
- Skill-direct probes (bypass LLM) isolate mechanism from model: 4/4 skill-direct + 4/4
  bare-REPL localizes a failure to the layer between → DEBUG.md D172 method.
- Test suites via `scripts/run-tests` in serial chunks (subdirs first, sim-heavy files
  last); measured chunk peaks 0.2–3.7G, so the default 12G cap is generous → E18.

## Frontier (the ambition horizon — review rounds refresh; STATUS `frontier:` carries the 1-liner)
- Harder find-fetch NL: ORDINAL resolution confirmed (最右边→blue, 2/2, E25) but not yet a
  clean GROUNDED (handover + grasp-miss confounds); next = a clean ordinal GROUNDED (red-can
  target, non-handover utterance), then quantity ("两个"), ambiguity ("那个"/"它") → STATUS next.
- A world-owned NL→object spatial grounder (positions the model can't author) would make
  ordinal/relational NL robust instead of model-strategy-fragile — cf. the D182 spine gate → E25.
- g1 GROUNDED navigation, non-gated build first; VLN GROUNDED accept waits on the
  near_object gate → D176/D178.
- Automated VLM vision-judge — the ONE thing that removes the manual-eyes dependency;
  external-blocked (provider credit) → D181.
- BYO-model family N≥4 (mistral-small ready on OpenRouter) when credit restored → D181.
- Plug-and-play verify-predicates: `_PREDICATE_ORACLES` is a hardcoded kernel list — world-
  declared predicate metadata (stricter-only) is the META gate on the queue → STATUS gates.
- Embodiment ladder: S4 one-generic-driver → S5 policy plugin → S6 capability
  planner-exposure (all CEO-gated) → docs/ARCHITECTURE.md §3.
- EvolvingLoop as an explicit, visualizable, standalone protocol/product — deferred by CEO
  until this repo's internal doc problems are fixed (2026-07-01 direction).
- AMBITION (R190 review): grounding cadence has slowed — the last NEW confirmed GROUNDED was
  R186 (compound); R187-R190 were META (checker fix / adjudication / doc fold / skeptic re-run).
  The North Star (plug-and-play across robots/policies/skills) is GATE-BLOCKED: the world-owned
  spatial grounder (D182 spine), near_object VLN (D178), and the S4/S5/S6 embodiment ladder are
  ALL CEO-gated, so ungated frontier is narrowing to single-robot NL polish. Not yet a hard
  plateau, but the highest-leverage next step needs a deliberate CEO gate decision → STATUS gates.

## Casebook — hidden bugs (symptom pointed away from cause; newest first; cap 15 cases, overflow folds oldest to one line under ### Folded)
Compressed from docs/tricky-bugs.md (removed 2026-07-02); full original prose in git history.
Only IMPLICIT bugs belong here — symptom pointed away from cause, survived a green suite, or
hid behind "every component correct in isolation". Routine bugs → git history.

- **Case 15 (compound place-leg walk-loop, 2026-07-02)** — a single-utterance fetch-AND-place
  (`放到架子上`) grasped fine but the PLACE leg walk-looped to a self-invented `at_position(10,5)`
  and never placed (RAN 1/4). Symptom looked like a nav/mobile_place bug; real cause was PROMPT
  cross-talk — `_native_system_prompt` locomotion_guidance framed navigate as the route to
  "REACH a **place** or coordinate", colliding with the place clause; the unbounded navigate-
  RECOVER loop burned all 24 turns. Fix: place_guidance forbids navigate/walk for a place clause;
  locomotion_guidance scopes navigate to an explicit user-given coordinate. → E21/49d6e0c
  CORRECTION (E23/R186): the A/B (OLD pre-fix prompt + SAME deepseek-v4-flash) also grounds
  2/2 — so the fix was NOT what drove 1/4→3/3; the MODEL was (deepseek-chat→v4-flash). Fix is
  correct+harmless but not the cause. Model-sensitivity trap (cf E9/E10): never credit a code
  fix for a pass-rate delta while the model also changed — isolate first. → E23/R186
- **Case 14 (FOV, 2026-06-29)** — far fetch grounds green/blue BOTTLES but red returns no_detections at
  re-perceive; red HSV suspected — yet red mask fired ~1000 px @3.9 m and the seed localized. Root: the red
  object is a CAN, shorter — mask 1000@3.9m → 0 at the ~0.9 m standoff: a close short object falls BELOW the
  head cam's downward vertical FOV. Fix seed: raise tilt / widen standoff. LESSON: "detected far, lost near"
  is a FOV/geometry signature — check object HEIGHT vs camera pitch and the near-field vertical frustum
  before touching the colour gate.
- **Case 13 (mobile_pick, 2026-06-29)** — far fetch `nav_failed`, dog drives to ~(0.5,0.15)=ORIGIN, bottle at
  (13.86,3.0) — looked like nav/frame. Root (detect.py): DetectSkill defaults x,y,z=0,0,0; a FAR object
  yields no depth → the (0,0,0) SENTINEL was stored as a TARGETABLE object; mobile_pick navigated to it.
  Fix: additive `ObjectState.has_position` (default True), False for 2D-only; pick skips position-less →
  honest object_not_found. LESSON: "drives to origin/nav_failed" is often a DEFAULT-SENTINEL leak —
  separate EXISTENCE from HAS-A-USABLE-POSITION.
- **Case 12 (far-fetch, 2026-06-29)** — `把绿色的瓶子拿过来` (VECTOR_FETCH_FAR=1) intermittently RAN/
  no_detections → pointed at perception/colour; but a skill-direct repro GROUNDED (2073 green px) and the
  failing run masked 0 at near-identical depth ⇒ out of frame. Root: FAR `navigate_to` has NO terminal-
  heading control + one-directional ~200° scan (6×0.6 rad, +vyaw only) → bottle in the uncovered ~160° arc
  never faced. Fix: turn to face the known seed xy via `_grasp_ready_repose` before re-perceive; 3/3.
  LESSON: identical depth + different mask ⇒ framing/heading, not detector; when you KNOW target xy, face
  it, don't search.
- **Case 11 (snapshot SIGSEGV, 2026-06-26, ADR-002 S1)** — verdict-time snapshot hook (VECTOR_SNAPSHOT_DIR)
  killed the bare-cli turn exit=-11 before VECTOR_VERDICT on BOTH ROS2 and in-process paths; hook-OFF control
  run clean ⇒ the render itself. Root: MuJoCo GL context is THREAD-BOUND (persistent renderers made on a
  worker thread, touched from emit thread) AND a control thread steps live mjData → torn read. Fix: fresh
  `mj.Renderer` ON the emit thread over an isolated MjData copy; hook failure returns None. LESSON: never
  reuse a renderer across threads or render live data — copy qpos into a throwaway MjData; isolate with a
  hook-OFF control before blaming context count.
- **Case 10 (fakeable grasp, 2026-06-24, D69)** — NL grasp graded verified=True with the gripper EMPTY:
  model wrote grabbed.txt via `file_write`, verified `file_exists`. Every gate fired correctly for the wrong
  reason — the false-green was the ABSENCE of a gate binding a physical-GRASP goal to a GT manipulation
  oracle (cf. D15/D16 coord). Fix (D69): robot world drops file_write/edit/bash; `evidence_passed` requires
  a NECESSARY holding_object/placed_count conjunct. LESSON: an oracle honest for one domain is a FABRICATION
  VECTOR for another — bind goal CATEGORY to an un-authorable GT oracle; a generic dev tool is not a
  generic ACTION.
- **Case 9 (IK base-sync, 2026-06-24, S3b)** — no symptom in unit/spike (green, compiled model
  byte-identical), but grasp silently targets the WRONG frame once the dog moves off-spawn: under
  `MjSpec.attach` the room's pickable freejoints occupy [0:21], go2 at [21], so the literal `live_qpos[0:19]`
  copied PICKABLES → IK FK on a stale base (matched at spawn only). Fix: DofLayout-derived
  `_lo = root_qpos_adr; _n = 7 + num_actuated`. LESSON: byte-identical compiled MODEL ≠ byte-identical qpos
  ORDER — blast-radius-grep ALL absolute qpos[N]/qvel[N] reads in CONSUMERS and e2e a MOVED (not spawn) pose.
- **Case 8 (arm-stow nq guard, 2026-06-24, S3b)** — bare-go2 connect() raised `broadcast (8,) into shape (0,)`
  at arm-stow after attach flipped the scene-build; legacy build was in-bounds + all-zeros = SILENT no-op.
  Root: `nq >= 27` assumed "arm ⇒ nq≥27"; the room's 3 pickable freejoints put BARE go2 at nq=40 in BOTH
  builds — nq is a SCENE property. Fix: gate on `model.nu >= 19` (nu=12 bare / 19 arm); slice at
  joint_qpos_start + num_actuated. LESSON: never discriminate robot morphology by nq — use nu or a
  named-element probe; an in-bounds all-zeros write is the textbook silent latent bug.
- **Case 7 (placed_count gate, 2026-06-21)** — latent, caught by design-probe: a pedestal-top place (~z=0.32)
  looks successful but `placed_count(region)`=0 forever — `make_placed_count` counts only z < _LIFT_MIN_Z
  (0.10) = "on the floor"; D34 kinematics reach further the higher it goes, biasing exactly where it can't
  ground. Resolved by an empirical reach-grid probe: floor place (10.60, 2.70, 0.05) settles z~0.04 < 0.10 →
  GROUNDED. LESSON: a verify oracle encodes IMPLICIT geometry — read its gate and MEASURE that a target
  satisfies BOTH reach AND the oracle; never loosen the gate (verify only ever stricter).
- **Case 6 (EdgeTAM degrade, 2026-06-23, R39)** — nav→grasp chain completes but holding_object False;
  grasp-z 0.13/0.044 vs true 0.32; an A/B probe's clean 2.8 cm made "off-axis lateral IK" look airtight.
  Root (two layers): `timm` declared but absent from .venv → EdgeTAM failed to LOAD → box-rect fallback →
  depth centroid averaged can+table; then `float(object_score_logits[i])` raised (transformers≥5 returns
  (N,1)). Tell: `[GO2-PERCEPT] EdgeTAM unavailable — box-rect fallback` in the e2e log, NOT the A/B log.
  LESSON: when two runs of the SAME perception code disagree, suspect a SILENTLY-degrading optional model
  path before re-theorizing geometry; make segmenter-degrade LOUD; env-sync optional model deps.
- **Case 5 (table-edge occlusion, 2026-06-20)** — on a tall pedestal (top z=0.28) the central GREEN rendered
  0 px while RED/BLUE (same z/distance) were fine → looked like arm self-occlusion; but depth at green's
  projected pixel read 3.708 m = the far doorway (camera saw THROUGH it). Root: the d435 (z~0.38, shallow
  down-tilt) grazes the tabletop — objects within ~6 cm of the near TOP EDGE are occluded by the lip
  (x≤10.82 → 0 px, x≥10.88 → ~1000 px). Fix: placement, objects ≥8 cm back (green at 10.88). LESSON: when
  ONE identical object is invisible, sample DEPTH at its projected pixel — depth ≫ object distance means a
  static-scene occluder.
- **Case 4 (blob fusion, 2026-06-20)** — deictic grasp ~12 cm off (a 116px brown table sliver) only with the
  Piper arm connected; 3 rounds chased self-occlusion. The arm only nudges the settle by mm, shifting WHICH
  sliver wins an already-broken selection. Root: `front_object._SAT_MIN=140` is BELOW the table's saturation
  (p90~146, max~160) → 1-3px chains FUSE cylinders+table into one blob → "most-central blob" grabs a sliver.
  Fix: morphological OPENING (3×3) before connected-components; front=755px GREEN, grasp 2.3 cm (was 12.2).
  LESSON: a threshold overlapping background is a connected-component TOPOLOGY bug — dump candidate blobs
  (area/centroid/colour); fix the topology, not the threshold.
- **Case 3 (dead PYTHONPATH, 2026-06, 13a9429)** — explore "worked" but on system python3 (mujoco 3.6)
  instead of the repo venv (mujoco 3.9) where the MPC fix was verified: the uv rebuild renamed
  `.venv-nano`→`.venv`; Python SILENTLY ignores nonexistent PYTHONPATH entries; hardcoded in 12+ scripts.
  Fix: scripts prefer `.venv` with `.venv-nano` fallback, single source. LESSON: PYTHONPATH to a missing dir
  fails silent — print `module.__file__` to verify WHICH copy loaded.
- **Case 2 (swallowed MPC errors, 2026-06)** — dog stands but never walks, no error anywhere: the per-tick QP
  fallback was a bare `except Exception: pass` eating the SAME exception every tick. Root: external
  `convex_mpc` written for numpy<2; numpy 2.x hard-errors on (N,1)→scalar → solver threw every tick →
  PD-hold only. Fix: shape fixes at source; except clauses count+log (VECTOR_MPC_LOG). LESSON:
  `except: pass` on a control path converts loud failures into silent wrong behavior — "0 failures" must
  be provable.
- **Case 1 (two-clock skew, 2026-06, d7e158b)** — explore gait unstable/limping (飘/瘸腿), worse on a loaded
  machine; single `walk` fine; every component correct in isolation (byte-identical gait/bridge, one cmd
  source @19 Hz, 2645/2645 QP ok). Root: physics ran ~0.65× real-time while `_follow_path` ramped by fixed
  per-tick increments on a 20 Hz WALL timer → profile slewed ~1.5× faster in sim-time → MPC destabilized;
  cracked by VECTOR_PHYS_LOG printing sim/wall≈0.65×. Fix: integrate every ramp against sim-dt (`sim_clock`
  + `get_sim_time()`). LESSON: a wall-clock controller commanding a sim must integrate by sim-dt — "sim
  slower than real-time" silently changes the meaning of every per-tick constant.
### Folded (oldest cases compressed to one line each; full prose in git at the hash)
- **Case 0** (casadi missing, 2026-06-18) — [PASS]/odom-count/nav-flag all green but dog stays put; casadi
  omitted from the `[all]` extra, imported lazily → qp_fail 149/149 → zero torque. LESSON: NEVER certify
  motion from PASS/odom/nav — measure the position DELTA; hard deps ship in their install set or fail loud
  at connect, never a lazily-imported solver failing silently every tick. → 45798a2
