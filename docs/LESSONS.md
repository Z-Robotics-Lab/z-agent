# LESSONS — do-not-repeat distillate (ORIENT step 3; one line each, pointer-terminated)

Append one line per lesson (round agents); review rounds consolidate. A line may be dropped
only if its D#/E#/commit pointer resolves in the ledger or git. Details live at the pointer.

## Refuted (do NOT retry unless the stated condition changed)
- "Model-sensitivity ceiling" on fetch was a HARNESS artifact, not the model — control the harness before concluding model capability → D171 refuted by D174.
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
- `placed_count() >= N` is the WRONG go2 quantity-place predicate: it's FLOOR-only (z<_LIFT_MIN_Z
  0.10) so it's STRUCTURALLY 0 for a bin/table place (pickables z=0.320, place_bin top ~0.31) —
  always-FALSE = a structural false-RED. Use the D106 count oracle `resting_on_receptacle() >= N`
  (ungated, same residual as single place) → E35 (extends #Casebook Case 7).
- quantity-place (`把两个瓶子放到架子上`) does NOT ground (deepseek-v4-flash): brain places bottle 1 then
  ABANDONS bottle 2 after its grasp stalls → at_position loop, RAN False 3/4. HONEST RED (moat refused): gap =
  BRAIN DECOMPOSITION of N grasp+place, machinery correct. Retry only after isolating grasp + a guardrail → E36.
- courtyard PLACE composite False is NOT a world-transfer bug: `navigate(10.8,3.0)` is INSIDE the inflated
  pick_table (R=0.28, table x∈[10.80,11.10]) → `plan_path`=None, UNREACHABLE in EVERY world incl HOUSE
  (furniture identical). R246's at_position was a brain-IMPROVISED recovery nav to the bottle pick-loc after
  a `mobile_place` first-nav flake; the place had already succeeded. Do NOT re-diagnose (10.8,3.0) as a
  house-vs-courtyard diff. R247 re-verify grasp itself flaked → PLACE-leg is model-flaky (grasp+nav) → E56/R247.

## Hazards & confirmed constraints
- perception_grasp far-recovery DEAD-BAND blocked HOUSE→warehouse fetch transfer (R234 root cause): the recovery (localize→0.95m standoff→face→re-perceive) fires only after scan→no_detections but was band-gated d∈(1.6,8.0]m — so a dog that nav-stopped CLOSE (0.88m) yet mis-oriented/occluded (front_object_mask=0px, d_min~0.55m facing an obstacle in the compact enclosure) got SKIPPED as 'the self-approach's job', which can't re-approach a target it can't see (world/config + detector were both fine: far-seed localized the bottle at correct coords). FIX: floor 1.6→0.30m (`_RECOVERY_MIN_M`), recover-by-repose from any plausible distance, keep only a d<0.3m degenerate-self-detection guard. ALSO: the sibling Isaac sim (`/workspace/go2w`, different engine) does NOT trip the repo's `pgrep -f "mujoco|vcli"` gate and with RAM/GPU headroom is NOT an Inv-5 blocker — R231-R233 over-read it and burned 3 rounds; run the repo's ACTUAL gate, not "any sim anywhere" → E54 (f437f4e; e2e re-verify pending R235).
- front_object SALIENCY FLOOD blocks HOUSE→warehouse colour fetch (R236 root cause, deeper than R234's dead-band): after the far-recovery fix ENGAGES and the dog reaches the CORRECT 0.9m standoff facing the real bottle (attempt-1 localized (10.86,3.00) right), `front_object_mask` still returns 0px. New mask-gate breakdown (`front_object.mask_gate_breakdown`, logged at the mask_px=0 site) shows WHY: n_salient~99k = ~32% of the warehouse frame passes `sat>=140` (orange racking 0.88/0.45/0.10, yellow safety stripes, steel all vivid), so the green bottle's real green pixels (n_color_hue up to 2917) FUSE into giant background blobs whose MEDIAN hue≠green → the colour-blob resolver picks none → None. The HOUSE world works only because its background is MUTED so the bottle IS the salient blob. The resolver's core assumption (vivid object on a muted scene) is FALSE in an industrial world. FIX direction (NOT yet done): for a colour query gate the colour HUE at PIXEL level BEFORE `_open`/connected-components (isolate green first, THEN find the nearest green blob) — must re-verify it does not regress the confirmed HOUSE red/green/blue/yellow/purple fetches → E54.
- `scripts/sim-teardown` (`rosm nuke`) reaps ONLY ROS2 procs — an in-process `VECTOR_NO_ROS2=1` MuJoCo sim survives it and a not-reaped harness double-drove TWO g1 sims (R217): kill in-process sims by EXACT launched PIDs (never `pkill mujoco`), pgrep clean before relaunch. Also g1 nav verify coords must be probe-checked REACHABLE (`(11,3)`/`(11,4)` are inside obstacles → `plan_path`→inf → `navigate_to` unreachable/moved_m=0 → honest RAN, moat refuses a fake arrival) → E49.
- The round env may select the qwen/dashscope provider, billing-blockable (`Arrearage`) while the deepseek route works — a harness inheriting it aborts at PREFLIGHT; force the deepseek provider (.env.example). The dashscope VLM-judge shares that blocked key → BILLING gate → E49.
- The PERCEPTION VLM (`look`/`describe_scene`, `perception/vlm_go2.py`) defaults to OpenRouter and is 402 CREDIT-EXHAUSTED RIGHT NOW (E28 block, still ACTIVE R230): a go2 fetch that grasp-fails once and lets the brain ESCALATE to `look`/`explore` then 402s SILENTLY mid-turn — the REPL keeps spinning, no verdict, the process looks hung not failed. FIX: every go2 acceptance run MUST export `VECTOR_VLM_URL=http://localhost:11434/v1 VECTOR_VLM_MODEL=gemma4:e4b` (LESSONS recipe). Proven R230: the SAME green-fetch FAILED (402 on `look`) without the local route and GROUNDED 1/1 WITH it (same brain/scene/utterance). Un-routed runs are billing-CONFOUNDED, not model/world failures → E53.
- go2 `describe`/`看到什么` NL is ALIAS-COLLIDED across TWO skills: the generic `DescribeSkill` (`skills/describe.py`, calls `context.perception`=Go2GraspPerception) and the go2 `LookSkill` (`skills/go2/look.py`, calls `context.services['vlm']`=Go2VLMPerception.describe_scene) — which one fires is model/registration-dependent. Go2GraspPerception lacked caption/visual_query → when the generic branch won it raised `AttributeError('visual_query')` and the describe-recovery dead-ended (R247). FIX (R248): Go2GraspPerception.caption/visual_query lazily route to a Go2VLMPerception.describe_scene (the SAME seam LookSkill uses) → no dead-end; 3 unit tests + bare-face courtyard describe (no crash, but the brain took the LookSkill branch so the fixed path was NOT exercised on the face). RESOLVED (R249): removed the colliding `describe`/`what do you see` aliases from LookSkill (intent split: look/看=survey-and-move, describe/看到什么=static scene description) → the deterministic alias_map now unambiguously routes describe→DescribeSkill (RED→GREEN test_describe_look_alias_routing, 4 cases) and the bare-face courtyard describe EXERCISED the R248 path (path_entered=True, [DESCRIBE]+describe-seam both fired, attr_error=False). CAVEAT: an alias edit does NOT make LLM tool-choice exclusive ([LOOK] still fired the same turn); describe has no moat oracle so this is reachability/no-crash, never a grounded win → E56.
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
- APPEND a ledger row as ONE pre-formatted line with `>>`; NEVER load-all→`json.dumps`→write-all:
  default dumps re-serializes EXISTING rows (adds `, ` separators, flips `\uXXXX`↔literal em-dash)
  — byte-identical content but numstat scores it a DELETION → append-only gate FAILS, quarantines
  the NEXT round. Content-preserving reformats are NOT restored (a 2nd rewrite compounds); leave +
  document. The gate caught it correctly — the bug was the write method, not the check → E27.
- ORDINAL/positional NL ("最右边的瓶子") CAN ground: the model resolves rightmost→blue (the
  non-central, dog's-right bottle) via `describe_scene`(VLM)+`detect`, then perception_grasp.
  BUT it is model-STRATEGY-fragile — it only works if the model PRE-RESOLVES the ordinal to a
  colour before the colour-keyed `perception_grasp` (raw "the rightmost bottle" query the CV
  resolver can't parse). `detect_objects` returns names+confidence, NO positions. Ordinal→object
  fidelity is WITNESS-only (D182 gap: oracle certifies held==named, not named==intent) → E25.
- The perception VLM (`look`/describe_scene) IS the ordinal resolver — A/B proved it (R192): VLM DOWN →
  raw ordinal to perception_grasp → 0/5; VLM up → 最左边的瓶子→"green bottle" GROUNDED 1/1. It defaults to
  OpenRouter (`google/gemma-4-31b-it`), 402-exhausted R192 (BILLING gate), silently breaking ordinals → E28.
- Ordinal SELECTION (最左边的瓶子→green) is deterministic+correct but took TWO fixes (VLM-only was a dead
  end): (a) the VLM drops the 瓶子 category (R193 grasped a can) → E30; (b) deterministic `_parse_ordinal`+
  `_resolve_ordinal_target` in perception_grasp was necessary but INSUFFICIENT until an ordinal-PASSTHROUGH
  native_loop prompt stopped the brain pre-resolving to a wrong colour → E31. E2E GROUNDED R197 → E33.
- g1_accept.py full RED+GREEN >10min (GREEN model flails ~14 turns): run BACKGROUND — a foreground Bash-cap timeout SIGTERMs mid-GREEN, orphaning the g1 sim (R217) → R219/R223.
- g1.perception NON-REPRODUCIBLE (R223 RAN 0/17): the oracle unions ALL same-colour seg pixels, but the OLD
  scene had MULTIPLE red geoms (2 stools + a can) → centroid on the cluster while dino boxed ONE → box↔centroid
  >60px ~2/3 of samples. RESOLVED R224 (WORLD config Inv.3; oracle+tol UNCHANGED=Inv.1): inject ONE dominant
  central red target (~18-20k seg px ≫ 920px) → 4-5px match, N=2 GROUNDED. LESSON: a GT-centroid oracle over a UNION of same-colour geoms is ILL-POSED with several in view — give perception ONE target → E50 R224.

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
- Perception VLM off OpenRouter (402/arrears) → route to LOCAL Ollama, plug-and-play, NO credit:
  `VECTOR_VLM_URL=http://localhost:11434/v1 VECTOR_VLM_MODEL=gemma4:e4b` (already-pulled; the code's
  documented local seam). gemma4:e4b resolves L-R ordinals; unblocked the clean ordinal GROUNDED → E28.
- Acceptance-diagnosis two-parter (make the ONE warehouse sim run decisive): (a) non-verbose REPL pins skills/perception loggers to ERROR (cli._QUIET_LOGGERS) so `[PGRASP]` trace never reaches repl.raw.log → `VECTOR_ACCEPT_VERBOSE=1` adds `--verbose` (logging-only, face intact) to capture arrival pose + per-heading detection; (b) the driver wrote `eyes_*.png`/`verdict_*.png` to the ephemeral SNAP scratch dir (reboot-wiped, AGENTS.md forbids it for durable evidence) but never copied them out, so R229/R231 warehouse frames VANISHED and `closest seen inf` was unadjudicable visually — now auto-persisted to `var/evidence/R<ROUND_N>` at end-of-run (`vlm_guard.resolve_evidence_dir`/`persist_evidence`, unit-tested; bare run w/o ROUND_N warns loud). Keep the frame, not just the log. CAVEAT (R238): >1 run in ONE round both persist to `var/evidence/R<N>` root with identical names, so run-2 OVERWRITES run-1's `eyes_fetch.png`/`repl.raw.log` (unique `verdict_<ts>.png` survives) — set `VECTOR_EVIDENCE_DIR` per run or copy frames out to `<tag>_*` and LOOK before the next launch. Also bank a ledger row as the SOLE stdout (`sys.stdout.write(json.dumps(row)+"\n")`), NEVER `print("LABEL:", json[:130])` under `>> ledger.jsonl` (the prefix+truncation lands a corrupt line; validate each appended line parses pre-check.sh) → E54/R238.
- Colour-object resolver in a VIVID scene: gate the target HUE at PIXEL level BEFORE morphology/components, never per-blob MEDIAN hue AFTER — a vivid non-target bg (warehouse racking, ~32% of frame past sat>=140) fuses the target's px into a blob whose median hue != target → None (the R229–R236 warehouse green-fetch transfer gap). Build the mask from target-hue px first so each colour is its OWN component; front_object_mask(color=…) does this, regression test_color_green_survives_saliency_flood → E54.

## Frontier (the ambition horizon — review rounds refresh; STATUS `frontier:` carries the 1-liner)
- Ordinal fetch CONFIRMED (R197/E33, deepseek-v4-flash): `最左边的瓶子`→green AND `最右边的瓶子`→blue
  both GROUNDED verified=True, 0 handover, eyes-confirmed — DIRECTION-sensitive (not lucky green default).
  Built on R195 passthrough + catalog-projection + R196 no-auto-handover (Case 16); witness-only (D182) floor → STATUS next.
- Position-invariance CONFIRMED N=2 (R209/E43 + R210/E44, deepseek-v4-flash): under VECTOR_SCENE_SWAP the SAME
  `最左边的瓶子` grasps BLUE (new leftmost) not frozen GREEN (E31/E33) → resolver reads LIVE positions, not memorized coords (same scene/objects; scene-variant breadth is E51, new-world/embodiment still the bar) → E44.
- Novel-object breadth: fragility is PLACEMENT/FOV-correlated, NOT geometry/plug-in nor a universal brain-flake (R212/E46 + R215/E47 CONFIRMED N=3, deepseek-v4-flash).
  Novel PURPLE BOX (type=box, first non-cylinder, y=2.89 in-FOV) GROUNDED 3/3 fresh sims bare-face (holding_object(box) all 3; eyes: box aloft, RGB remain), while sibling
  yellow (E45→E46, y=3.11) REFUTED 0/2 SAME harness (perception not-visible → brain WANDERED). 5-site plug-in (0 kernel edits) is CORRECT for colour AND geometry;
  R212's "brain-fragile at N=1" REFINED — an IN-FOV grasp-reachable novel object grounds ROBUSTLY. LESSON: promote N=1 novel passes only on N>=2 repro;
  place novel pickables IN the front FOV band; welds/colour maps still HARDCODED (S4/D182). R251/E58: yellow (y=3.11) RECOVERED to GROUNDED N=1 provisional — its initial scan STILL returns no_detections (FOV-margin is REAL) but the warehouse-built R234 far-recovery floor + R237 hue-gate localize→re-pose (10.88,3.11)→mask_px=4184→grasp it; the FOV-margin is now recovery-HANDLED, not a placement dead-end (a 2-world perception fix transferred back to HOUSE free). R252/E59: CONFIRMED N=2 (same brain+VLM across the boundary, grasp (10.877,3.107,0.321) holding_object(bottle_yellow) CAUSED, eyes yellow aloft/RGB+purple remain) — SUPERSEDES the R212 refuted yellow row → E45/E46/E47/E58/E59.
- Cross-embodiment CONFIRMED w/ the CURRENT brain (R216/E48 → R217/E49 adjudicated): deepseek-v4-flash (all recent go2 work) drives the 2nd embodiment g1-humanoid to GROUNDED nav bare-face, 0 kernel edits — refreshes 32-round-stale R183 g1.nav (deepseek-chat), answers R200 critic (all-go2). R217 reproduced it across a round boundary at a NON-MEMORIZED coord (12,3, ≠ R216's 9,3/10,4) actor=CAUSED → not a fixed-pair fluke. Bonus MOAT-FIDELITY win: leg-B (11,4) is inside an obstacle → navigate_to reason=unreachable moved_m=0 → system emitted RAN/False, refusing to fabricate an arrival. Still EXISTING g1 config, NOT a new 3rd embodiment (BYO URDF+driver = S4-gated + multi-round SDD); g1-nav renders no frame → at_position GT pose is the witness → E48/E49. R224→R225: the PERCEPTION axis also GROUNDED and now CONFIRMED (E50, N=3: R224 2/2 + R225 1/1 reproduced across the boundary — the exact test R223 failed on R219's un-hardened bar) after a WORLD-config hardening (dominant central red panel; oracle+tol byte-unchanged, Inv.1). Cross-embodiment spans BOTH axes, 0 kernel edits. LESSON: a GT-centroid oracle over a UNION of same-colour geoms is ILL-POSED with several in view — give perception ONE unambiguous target, never widen tol. Real breadth is still a NEW 3rd embodiment or a 2nd world → E50.
- Scene breadth via CONFIG CONFIRMED (R226 built / R227 verified N=2 / R228 adjudicated, E51): VECTOR_SCENE_CLUTTER injects 5 decorative distractors (incl. a SAME-HUE off-centre green decoy) into the frozen go2 tabletop via the existing `extra_geoms` seam (same one g1's percept_target_red uses), 0 kernel/driver edits (Inv.3); a CONFIRMED green fetch (v4-flash) GROUNDED N=3 — REPRODUCED across the R227→R228 boundary (fresh sim, oracle byte-unchanged, the exact reproducibility gate R219 g1.perception failed) — real bottle grasped (holding_object GT), decoy is contype/conaffinity 0 + no freejoint → weldless/unpickable so a mis-ground yields False → True=discrimination, unfakeable. LESSON: decorative clutter (no collision/weld) is the cheapest honest scene-diversity knob — stresses PERCEPTION without perturbing physics or a fake-verify hole; still ONE room, a NEW WORLD or 3rd embodiment is the deeper bar → E51.
- New WORLD plugs in as CONFIG; a confirmed bar did NOT transfer zero-shot but is now RECOVERED+CONFIRMED via a 2-layer perception fix (R229/E52 SPLIT → R238 CLOSED): go2_warehouse.xml (compact industrial box, distinct enclosure from the 20×14m house) enters via VECTOR_ROOM_TEMPLATE → build_room_scene(room_template_path=) with 0 kernel/driver edits (Inv.3), compiles with the 5 pickables + pick_table + place_bin byte-identical coords (unit 9/9; MjModel: green [10.88,3.0,0.32], dog [10.0,3.0]). BUT green fetch RAN 0/2 on the bare face (v4-flash): run1 wandered (walk fwd 2.0×N → pick 'Cannot locate target object'), run2 perception_grasp×11 never completed. Config verified LIVE + furniture byte-identical ⇒ NOT moved-geometry — perception_grasp/approach does not complete under the new visual+lidar scene. LESSON: a new-world BUILD (compiles, config-only) is a FLOOR, NOT acceptance; the deeper bar is that grasp/perception must TRANSFER, and clutter (E51, same room + decoy geoms) is far cheaper than a new enclosure. Next = Hypothesis-Loop debug → E52. R230 CAVEAT (402-confound) DISPROVEN at N=1: R231 re-ran clean local-VLM route, ZERO 402, still RAN 0/1 — a REAL grasp/perception gap, not billing. R232 OBSERVE ruled out spawn/pose/lighting/bg; root cause (H1 nav-off-frame · H3 approach/grasp · H2 render · H4 scan) sim-blocked, instrumented via VECTOR_ACCEPT_VERBOSE → E54. RESOLVED as a 2-layer perception gap (NOT world/config, NOT the brain): (1) R234 far-recovery DEAD-BAND (recovery band (1.6,8.0]m skipped a dog that nav-stopped CLOSE-but-blind at 0.88m → floor to 0.30m, f437f4e); (2) R236 front_object SALIENCY FLOOD (vivid warehouse bg 8-connects the target's px into off-hue blobs → R237 pixel-level hue gate before _open). Warehouse green fetch then GROUNDED N=2 (R237) and PROMOTED to confirmed N=3 (R238, fresh reproduction across the boundary, holding_object(green) actor=CAUSED, eyes: dog holds green in warehouse). LESSON: a new-world BUILD is a FLOOR; the transfer bar is passed only when grasp+perception complete on the bare face — and here it cost TWO independent perception fixes, each invisible to unit-green → E54/R238. R239: the pixel-hue gate is FULLY colour-agnostic — blue PROMOTED to confirmed (N=2), and PURPLE-box (N=1) + RED-can (N=1, the HARDEST: hue-adjacent to orange racking, mask_px=5132 NOT flooded, d_min=0.569 so Case-14 FOV did not bite) both transferred, eyes-confirmed discrimination. HOUSE plain-colour green re-confirmed (no regression). Only YELLOW(y=3.11) untransferred — blocked by the separate HOUSE FOV issue (E45/E46), NOT the hue gate (R251/E58: yellow later RECOVERED N=1 provisional via the same R234/R237 fixes) → E54/R239. R240 review PROMOTED red+purple to confirmed N=2 (re-run across the boundary, eyes-confirmed discrimination; red mask_px=5133≈R239's 5132, purple grasped first-action) — warehouse colour transfer CLOSED (green N=3, blue N=2, purple N=2, red N=2), provisional queue cleared → E55/R240.
- 3rd WORLD courtyard CONFIRMED zero-shot, ZERO perception fixes (R241 build → R242-R246, E56): go2_courtyard.xml (open-air sandstone courtyard) plugs in as pure CONFIG via VECTOR_ROOM_TEMPLATE=courtyard, 0 kernel edits (Inv.3, 1-line dict entry like warehouse R229), 5 pickables byte-identical at house coords. FETCH green/blue/red/purple ALL PROMOTED confirmed N=2 (each re-run across a round boundary, eyes-confirmed discrimination: target aloft, other 4 remain) — colour AND geometry (purple box = first non-cylinder) transfer. UNLIKE the warehouse (E54 cost 2 perception fixes incl. the HUE-ADJACENT red/orange flood), courtyard needed ZERO: its warm sandstone bg (~25° hue) is FAR from every target hue so the R237 green-hue gate never floods. Now 3 distinct worlds ground go2 fetch (house N=3, warehouse N=3, courtyard green/blue/red/purple N=2). LESSON: a config-only world whose background hue is FAR from the target transfers zero-shot; the warehouse was hard because orange racking is hue-ADJACENT, not because new worlds are inherently hard. BUT the courtyard PLACE-leg did NOT transfer: composite RAN verified=False — grasp + physical place both succeed (eyes: bottle IN place_bin) but the intermediate navigate at_position(10.8,3.0,tol=1.0) ungrounds because (10.8,3.0) is INSIDE the inflated pick_table (R=0.28) → plan_path=None, UNREACHABLE in EVERY world incl HOUSE (see the Refuted courtyard-PLACE line). LESSON: a FETCH transferring zero-shot does NOT imply its multi-step PLACE composite transfers — the nav sub-goal predicate is the fragile link, not perception/grasp → E56/R243-R247. R253/E60: RECOVERED to GROUNDED provisional N=1 (2/2, was R246 2/3) — the ungrounding was NOT the world: the BRAIN improvised the unreachable navigate(10.8,3.0) as a RECOVERY after mobile_place's transient first-nav miss surfaced to it as False; an internal nav-retry (_NAV_RETRIES=1, re-reads pose) keeps a transient miss INSIDE the skill so it never surfaces (a genuinely-unreachable target still fast-fails → honest nav_failed). Retry is unit-tested but did NOT fire this run (first nav landed), so reliability across the flake still owes N>=2 → E60. R255/E60 ADJUDICATION: the N=1 provisional REFUTED — does NOT reproduce (RAN verified=False 1/2: grasp holding_object CAUSED=True but resting_on_receptacle=False; brain '瓶子…掉了'→re-grasp thrash; eyes: empty-armed dog, no bottle placed). Across N=3 real runs courtyard PLACE is FLAKY (R246 2/3, R253 1/1 clean-retry-untriggered, R255 dropped): the residual flake is a MID-WALK DROP (holding_object lost during the mobile_place walk/dock), NOT the nav-MISS _NAV_RETRIES targets — R253's fix is real but insufficient. Do NOT re-credit the nav-retry as the place-reliability fix (E23); a DEBUG round with VECTOR_PLACE_DIAG must localize weld-break-under-locomotion vs off-receptacle drop-release → E60. R256/E60 DEBUG RESOLVED — the "mid-walk drop" framing is REFUTED: in-process (no brain) the grasp weld holds the object at 25–30mm from the EE through the ENTIRE 1.6m walk + Step-6b dock (N=2, 1028 samples, eq_active never flips, never hits floor), and the FULL MobilePlaceSkill lands it RESTING on the courtyard bin (resting_on_receptacle=1, gripper empty). The machinery is SOUND. ROOT CAUSE = BRAIN POST-PLACE MIS-RECOVERY, confirmed from the real R255 repl trace: perception_grasp→verify holding TRUE→mobile_place (legitimately empties the gripper onto the bin)→describe→brain '掉了让我重新抓取它' (misreads the EXPECTED empty gripper as an accidental drop)→navigate→detect→mobile_pick RE-GRASPS the just-placed bottle OFF the bin→thrash→resting=False. The place succeeded; the brain UNDID it. FIX (next round, behavior): a prompt/runner guard that an empty gripper AFTER a successful place is the terminal success state, not a drop to recover (cf. R206 quantity guardrail); owes real-face N>=2. Regr=tests/vcli/test_go2_courtyard_place_machinery.py (machinery rests=1). Do NOT re-diagnose as a weld/mid-walk drop → E60/R256. R257/E60 FIX LANDED + VERIFIED N=2 GROUNDED (provisional): the brain post-place recovery guard = (a) persona place_guidance — after a place an EMPTY gripper is EXPECTED not a drop; verify resting_on_receptacle (never holding_object/describe); do NOT re-grasp; (b) runner NativeStepRunner — a successful place arms `_place_awaiting_verify`; a re-grasp skill (`_GRASP_SKILLS`) is REFUSED until the next verify closes it (bounded by `_MAX_VERIFY_NUDGES`, quantity-safe: an intermediate FAIL verify clears it for the next object). Both bare-face runs (deepseek-v4-flash, MODE=place, in-process) grounded resting_on_receptacle True with NO mobile_pick re-grasp — run1 clean, run2 wandered (look/at_position/repeat-place) but never undid the place; eyes both: green RESTING in bin, gripper empty. Meets the R255-refuted N≥2 bar. RESIDUAL: run2's wander shows the guard kills the DESTRUCTIVE re-grasp only, not all post-place brain flakiness; eyes self-read; N=2 modest → promote next round. Regr=tests/unit/vcli/test_native_loop.py post_place/regrasp tests → E60/R257. R259/E60 PROMOTED confirmed: re-run across the R257→R259 boundary GROUNDED verified=True (2/2), native skill seq CLEAN (perception_grasp→verify holding→mobile_place→verify resting→finish, ZERO mobile_pick re-grasp — the guard held, cleaner than R257 run2's wander), eyes green resting in the courtyard bin gripper empty → courtyard PLACE CLOSED (fetch AND place both transfer zero-config to the 3rd world; 3 clean same-brain GROUNDED total R257×2+R259) → E60/R259.
- Quantity-place: REFUTED v4-flash (R199/E36) → GROUNDED deepseek-chat (R204/E39) — ceiling was BRAIN-SPECIFIC
  not machinery (E38 seq 2/2); model swap moved it ZERO kernel edits (E23-clean, plug-and-play). But NOT deterministic:
  ROBUSTNESS (R205/E40) campaign GROUNDED 2/3 (run1 abandoned obj-2; deepseek-chat FLAKY on 两个) → runner guardrail E40.
- QUANTITY guardrail is a PLANNER-FREE finish-gate, NOT a runner-side decomposer: native_loop is planner-free
  BY CONSTRUCTION (import firewall — a per-object loop/replan bookkeeping IS re-growing the planner, the tell).
  So R206 enforces the prompt's "NEVER finish while latest verify is FAIL" IN THE RUNNER: refuse finish/stop
  while the model's OWN latest verify() is False (bounded, honest-on-exhaustion), model still owns decompose.
  Residual (deferred, goal-authenticity per native_loop._grade): if the brain finishes on a WEAKER passing predicate (holding_object / >=1) the gate can't fire — it only catches the >=N-then-quit mode → E41.
- A world-owned NL→object spatial grounder (positions the model can't author) would make ordinal/relational NL robust instead of model-strategy-fragile — cf. the D182 spine gate → E25.
- g1 GROUNDED navigation (non-gated); VLN GROUNDED accept waits on near_object gate → D176/D178.
- Automated VLM vision-judge — the ONE thing that removes the manual-eyes dependency;
  external-blocked (provider credit) → D181.
- BYO-model family N≥4 (mistral-small ready on OpenRouter) when credit restored → D181.
- Plug-and-play verify-predicates: `_PREDICATE_ORACLES` is a hardcoded kernel list — world-
  declared predicate metadata (stricter-only) is the META gate on the queue → STATUS gates.
- Embodiment ladder: S4 one-generic-driver → S5 policy plugin → S6 capability
  planner-exposure (all CEO-gated) → docs/ARCHITECTURE.md §3.
- AMBITION CRITIC (R230 review, RESOLVED R234-R236): the loop pivoted to real breadth (E48-52) but the
  ACCEPTANCE HARNESS silently swallowed a perception-VLM 402 (indistinguishable from a capability failure),
  so E52's warehouse 0/2 was of unknown provenance. FIXED: repl_accept defaults local Ollama gemma4:e4b; the
  E52 gap is now KNOWN (R236 saliency-flood root cause above), no longer a silent-billing confound → E54.
- AMBITION CRITIC (R240 review): warehouse colour/geometry transfer is CLOSED (4/5 colours + a box, all confirmed) — a domain expert would call more colours/objects in the SAME warehouse a LOCAL HILL, and note verify is still WITNESS-ONLY (D182: the actor authors the target string; only eyes disambiguate "red"). The genuinely-new bars are untouched: (a) a 2nd DISTINCT world (different enclosure again), (b) a NEW 3rd embodiment via BYO URDF (S4-gated), (c) the D182 world-owned NL→object grounder that would make colour/ordinal fidelity robust instead of self-certified. Pivot OFF colour breadth → E55/R240.
- AMBITION CRITIC (R260 review): the R250 pivot recommendation (unblock S4/D182) went UNHEEDED — R250-R259 spent 10 rounds and delivered exactly ONE new confirmed capability (courtyard PLACE, R259) at the cost of 7 rounds + 2 refutations (R255/R256); the rest was HOUSE-yellow RECOVERY (R252, superseded a refuted row, not new breadth). The non-gated frontier is now "place composite on the Nth existing world" (STATUS next#1 = warehouse place) — legitimate as ONE more transfer datapoint (E56 nav-sub-goal is the fragile link, NOT implied by fetch transfer) but the SAME local hill R240/R250 already flagged. Every genuinely-new bar stays GATED and UNANSWERED for ~20 rounds: S4 (3rd embodiment BYO URDF) and D182 (world-owned NL→object grounder, which ALSO makes the self-certified witness-only fidelity robust). RECOMMEND (sharper than R250): run warehouse-place to CLOSE the place-transfer question, then declare the non-gated frontier EXHAUSTED and HOLD at the gates (STATUS phase: blocked) rather than mining a 4th world / more colours — the owner must unblock S4 or D182 to escalate. Skeptic-verified this round: kernel.model-unavailable (~80r, oldest) + HOUSE fetch.nl-plain-colour both RE-CONFIRM on the real face, eyes-discriminated → E61/R260.
- RE-RED-TEAM (R260, R259 "courtyard PLACE CONFIRMED, place transfers zero-config"): SURVIVES with a fidelity refinement — confirmation rests on 4/4 POST-GUARD GROUNDED runs (R257×2 + R259×2) graded by the resting_on_receptacle GT oracle the actor cannot author (moat holds); the pre-guard non-grounds (R246 2/3, R255 0/2) are legitimately the guard's target. HONEST: "zero-config" is WORLD-config (Inv.3: no courtyard place code) — TRUE; but place-composite RELIABILITY required a GENERAL R257 runtime guard that post-dates the HOUSE place.nl-plain-colour confirmation (now ~age 61, STALE, NOT re-verified post-guard — a future skeptic target). No overclaim; caveats were disclosed → E61/R260.
- PLACE-transfer question CLOSED → non-gated NEW-capability frontier EXHAUSTED, HOLD at the gates (R262/E62, executing the R260 critic's plan): warehouse PLACE PROMOTED to confirmed (R261 N=1 + R262 N=1 = E46 N≥2; bare face, VECTOR_ROOM_TEMPLATE=warehouse MODE=place, deepseek-v4-flash + local gemma4:e4b, resting_on_receptacle=place_bin(10.95,4.60) live-AABB GT, native seq CLEAN grasp→hold(green,CAUSED)→place→verify→finish ZERO re-grasp, R257 guard held, launch_explore_seen=False; eyes: green resting in oak receptacle in the concrete/yellow-lane warehouse shell). PLACE now GROUNDED-confirmed on ALL 3 worlds (house + courtyard R259 + warehouse R262); fetch grounds all 3. Per R240/R250/R260 (3 consecutive critics), every remaining NEW bar is a CEO gate — S4 (3rd embodiment BYO URDF, kernel/interface) and D182 (world-owned NL→object grounder, spine-semantics, also fixes witness-only fidelity) — UNANSWERED ~22 rounds; "place-on-Nth-world / more colours / 4th world" is the SAME local hill. STATUS phase→blocked: the loop cannot advance NEW capability without an owner gate decision. Non-gated MAINTENANCE remains (stale confirmed BOARD rows ~55-82r owe a skeptic re-verify; R270 review due) so the loop treads water on hygiene, not new frontier → E62/R262. R263/E63: skeptic re-verified the OLDEST stale row fetch-place.nl-category-only (age 79, orig deepseek-chat) on the CURRENT deepseek-v4-flash+local-gemma4:e4b seam → GROUNDED 1/1, category '罐子'→the only can (pickable_can_red) actor=CAUSED, eyes: red can aloft/4 distractors remain=discrimination — re-confirmed AND provider-refreshed (first v4-flash run of this cap); next stale target = fetch-place.nl-compound (age 76) → E63/R263. R264/E64: skeptic re-verified fetch-place.nl-compound (age 77, R186 GROUNDED 2/2 under OLD native_loop grading) on the current v4-flash+local-gemma4:e4b seam (MODE=combo, '把绿色的瓶子拿过来放到架子上') → does NOT reproduce: RAN verified=False (2/4). The compound decomposes correctly and the place PHYSICALLY succeeds (eyes: green resting on receptacle, gripper empty; GT resting_on_receptacle()>=1 TRUE, unauthorable), but the place-leg CAUSATION is NOT_GRADED in the same single session (mobile_place→resting NOT_GRADED; bare placed_count() UNCAUSED) — the E17-class causation-safety limit; grasp leg still grounds CAUSED. R186's 2/2 predates the stricter causation grader (Inv.1: grading only tightens) so it does not carry forward → the stale green correctly flipped to provisional/red. LESSON: a compound single-utterance PLACE cannot be causation-graded cleanly in one session; a "confirmed" compound row from an era of looser grading is a prime skeptic target — its place leg is witness-real but not actor-attributable. Next stale target = fetch.nl-ordinal-spatial (age 67) → E64/R264. R268/E65-66: skeptic re-verified fetch.nl-ordinal-spatial (age69, R197 2/2) on the v4-flash+local-gemma4:e4b seam (MODE=fetch '把最左边的瓶子拿过来') → does NOT reproduce: RAN verified=False (0/5). perception_grasp found NO object — mask_px=0, none-plausible across all 6 scan steps, green n_hue_anywhere~27-56 (green not in front-cam view) → nothing held → all verify legs UNCAUSED; scene DID load (24 objs) so not empty-sim. R197 confirmed by MEMORISING leftmost→green from that round's layout (see ordinal lines above: the ordinal is PRE-RESOLVED to a colour, then a plain colour-grasp) — when the memorised colour isn't in front-cam view the grasp finds 0px → REFUTED, supersedes R197. CONTROL (E66): re-verified fetch.nl-negated-distractor (age68, R200 1/1) on the SAME seam/session → GROUNDED 1/1 actor=CAUSED, eyes: gripper holds RED can, blue/green/yellow distractors untouched → proves the 0px failure is ORDINAL-specific (memorised-colour-not-in-view), NOT a systemic perception regression. LESSON: an ordinal 'confirmed' row is doubly fragile — it depends on BOTH the VLM pre-resolving the ordinal AND that colour landing in the front camera; a stale ordinal green is a prime skeptic target. Next stale target = place.nl-plain-colour (age68, MODE=place) → E65/E66/R268. R269/E67: skeptic re-verified place.nl-plain-colour (age68, R200 2/2) on the v4-flash+local-gemma4:e4b seam (MODE=place '把绿色的瓶子放到架子上') — the FIRST re-check since the R257 post-place re-grasp guard landed (R260 red-team flagged it STALE-not-verified-post-guard) → RE-CONFIRMED GROUNDED verified=True (2/2): perception_grasp→holding_object(bottle_green) actor=CAUSED, mobile_place→resting_on_receptacle()>=1 GT-True, native seq CLEAN ZERO mobile_pick re-grasp so the R257 guard HELD without regressing plain-colour place; eyes green resting in receptacle/gripper empty/red+purple remain=discrimination. supersedes R200. NOTE: the default qwen routing brain is now in ARREARAGE (400) — MUST force the deepseek provider (Hazards L35). Next stale target = quantity-place.nl-isolation (age64, MODE=place) → E67/R269.
- EvolvingLoop as an explicit, visualizable, standalone protocol/product — deferred by CEO until this repo's internal doc problems are fixed (2026-07-01 direction).

## Casebook — hidden bugs (symptom pointed away from cause; newest first; cap 15 cases, overflow folds oldest to one line under ### Folded)
Compressed from docs/tricky-bugs.md (removed 2026-07-02); full original prose in git history.
Only IMPLICIT bugs belong here — symptom pointed away from cause, survived a green suite, or hid behind "every component correct in isolation". Routine bugs → git history.

- **Case 16 (ordinal "grasp miss" = handover-releases-hold, 2026-07-02)** — R194/R195 recorded the
  ordinal fetch `把最左边的瓶子拿过来` as a grasp-EXECUTION miss ("green knocked to the floor",
  verified=False), and 4 rounds chased grasp geometry / the ordinal→colour path. Real cause: the
  grasp SUCCEEDED (grasp_probe grounds green ordinal 5/5; R195b's own log says "The grasp
  succeeded") — then the brain (deepseek-v4-flash) read `拿过来`=bring-to-user and routed a
  `handover`, which RELEASES the weld, so the terminal `holding_object` verdict read False. The
  floor frame was the handed-over bottle, not a miss. Model variance (deepseek-CHAT grasped the
  IDENTICAL utterance and STOPPED→GROUNDED; cf Case 15 / E9/E10/E23 — never trust a pass-rate
  delta across a model change). Fix: native_loop "BRING IS COMPLETE AT THE HOLD" (a bare 拿过来
  finishes at the hold; handover only on explicit 递给我/给我) → 3/3 GROUNDED on v4-flash. Lesson:
  a verified=False on a manipulation predicate can be a LATER action UNDOING a real success — read
  the full action trace to the verdict, not just the failing predicate. → E32/R196
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
### Folded (oldest cases compressed to one line each; full prose in git at the hash)
- **Case 0** (casadi missing, 2026-06-18) — [PASS]/odom-count/nav-flag all green but dog stays put; casadi
  omitted from the `[all]` extra, imported lazily → qp_fail 149/149 → zero torque. LESSON: NEVER certify
  motion from PASS/odom/nav — measure the position DELTA; hard deps ship in their install set or fail loud
  at connect, never a lazily-imported solver failing silently every tick. → 45798a2
- **Case 1** (two-clock skew, 2026-06) — explore gait limped (飘/瘸腿) though every component was byte-identical
  in isolation; physics ran ~0.65× real-time while `_follow_path` ramped on a 20 Hz WALL timer → profile
  slewed ~1.5× in sim-time → MPC destabilized. LESSON: a wall-clock controller commanding a sim must integrate
  by sim-dt. → d7e158b
- **Case 2** (swallowed MPC errors, 2026-06) — dog stood but never walked, no error: a bare `except: pass` ate
  a per-tick QP failure (external convex_mpc broke on numpy 2.x (N,1)→scalar → threw every tick → PD-hold only).
  LESSON: `except: pass` on a control path converts loud failure into silent wrong behavior — "0 failures" must
  be provable. → git history
