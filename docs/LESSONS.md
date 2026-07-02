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
  supervisor/siblings → docs/rules/sim-safety.md (10.6h wedge, 2026-06-30).
- A green unit suite, a PASS timer, an odom count, a nav flag — none of them certify motion;
  measure the position/state DELTA → tricky-bugs Case 0.

## Recipes (proven invocations — copy, don't re-derive)
- Bare-REPL NL acceptance, in-process sim: `VECTOR_NO_ROS2=1 MUJOCO_GL=egl` +
  `tools/acceptance/repl_accept.py` (MODE=fetch|place|neg|combo); env from .env.example → D181/D182.
- g1 headless under the bare-REPL face needs `MUJOCO_GL=egl` (suppresses the GLFW viewer)
  → 010a998.
- Verdict-time frames: render an isolated MjData copy with a fresh Renderer ON the emit
  thread; a snapshot must never crash the verdict → tricky-bugs Case 11.
- Skill-direct probes (bypass LLM) isolate mechanism from model: 4/4 skill-direct + 4/4
  bare-REPL localizes a failure to the layer between → DEBUG.md D172 method.

## Frontier (the ambition horizon — review rounds refresh; STATUS `frontier:` carries the 1-liner)
- Harder find-fetch NL: single multi-clause combo ("把红色的拿过来放到架子上"), ambiguity
  ("那个"), quantity, ordinals; push N-to-first-failure per phrasing → STATUS next.
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
