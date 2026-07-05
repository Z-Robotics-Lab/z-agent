# WIRING — subsystem plug maps (overwrite the section in the SAME commit that changes its wiring)

## verify-spine — how it plugs in

verified-against: 437e09d

**frozen — GATE-APPROVED required** (Invariant 1): every file below is honest-verify spine; do NOT edit without the CEO gate.

- A turn becomes an `ExecutionTrace` (frozen dataclasses in `vector_os_nano/vcli/cognitive/types.py`): the native producer `native_loop.py::run_turn_native` (or the legacy VGG executor) records one `StepRecord` per (action-chain → verify) pair and assembles the trace via `NativeStepRunner.build_trace`.
- The trace is graded — never re-derived — by `vector_os_nano/vcli/cognitive/trace_store.py::evidence_passed`: True iff ≥1 checked step AND every step classifies GROUNDED, plus the coordinate-goal (STEP-15) and object-goal (D17) turn gates, which can only REJECT.
- Per-step grading single source: `trace_store.py::classify_step_evidence` → FAILED / RAN / GROUNDED. Feeds BOTH the done-gate and the bandit reward gate (`trace_store.py::step_evidence_ok`) — no split-brain.
- A verify string is structurally graded by `vector_os_nano/vcli/cognitive/evidence_classifier.py::classify_verify_expr`: GROUNDED only when a world oracle's result GATES the verdict (`evidence_classifier.py::_is_grounded_node`, recursive AST walk; rejects `... or True`, tautologies, bare state oracles, literal-container burials).
- `_PREDICATE_ORACLES` lives in `evidence_classifier.py` (module-level frozenset: at_position, facing, visited, holding_object, arm_at_home, file_exists, path_contains, resting_on_receptacle). It gates which BARE calls count as evidence — a bare call of any other (state) oracle is RAN unless compared against a constant.
- Live oracle names are single-sourced by `trace_store.py::verify_oracle_names` from `engine._build_verifier_namespace(agent)` (merges `World.build_verify_namespace` on top). Empty set fails CLOSED — everything classifies RAN.
- World oracles are factories in `vector_os_nano/vcli/worlds/go2_sim_oracle.py::make_at_position` / `make_facing` / `make_visited` (plus arm_sim_oracle.py, g1_perception_oracle.py::make_detection_matches_gt) — bound over live sim GT the actor cannot author.
- Actor-causation channels (R2b): `vector_os_nano/vcli/cognitive/actor_causation.py::grade` — BASE (cmd_motion counter + planar/yaw displacement, channel-split per predicate), ARM (ctrl_motion + joint delta), GRIPPER (weld 0→1). Baseline via `actor_causation.py::capture` BEFORE the step's first skill; `ActorCaused.UNCAUSED` downgrades GROUNDED→RAN inside `classify_step_evidence`. `actor_causation.py::is_robot_predicate` decides whether a step is graded at all.
- The machine verdict: `vector_os_nano/vcli/verdict.py::VerdictReport.from_trace(trace, oracle_names)` delegates `verified` VERBATIM to `evidence_passed` (contract-test-pinned). `VERDICT_SENTINEL` = "VECTOR_VERDICT".
- VECTOR_VERDICT escapes cli.main via `vector_os_nano/vcli/cli.py::run_one_turn` (the `-p/--json` non-interactive entry, ~line 1857): `_emit` prints `report.to_sentinel_line()` on stdout and returns `report.exit_code()` (0 verified / 2 ran-not-verified / 1 error-or-no-trace). Chat-only / error turns emit `VerdictReport.no_trace` (fail-closed).
- Seam for a new world (plug-and-play, Inv-3/4): register oracles in `World.build_verify_namespace` — that merge is single-sourced into `verify_oracle_names`, so a BYO name REACHES the grader with ZERO kernel edits. It then GROUNDS a goal two ways, NO gate: `pred() == True` (a bare-bool predicate made goal-explicit) or `state() == <const>` (E116; guard `tests/vcli/test_plug_and_play_boundary.py`). ONLY the bare `pred()` idiom needs the name in `_PREDICATE_ORACLES` — a gate-approved, first-party affordance (why the go2 quartet G-323-1 edits that set), NOT a requirement for a BYO contributor.

```
anchors:
vector_os_nano/vcli/cognitive/trace_store.py::evidence_passed
vector_os_nano/vcli/cognitive/trace_store.py::classify_step_evidence
vector_os_nano/vcli/cognitive/trace_store.py::verify_oracle_names
vector_os_nano/vcli/cognitive/trace_store.py::step_evidence_ok
vector_os_nano/vcli/cognitive/evidence_classifier.py::classify_verify_expr
vector_os_nano/vcli/cognitive/evidence_classifier.py::_PREDICATE_ORACLES
vector_os_nano/vcli/cognitive/evidence_classifier.py::_is_grounded_node
vector_os_nano/vcli/cognitive/actor_causation.py::grade
vector_os_nano/vcli/cognitive/actor_causation.py::capture
vector_os_nano/vcli/cognitive/actor_causation.py::is_robot_predicate
vector_os_nano/vcli/verdict.py::VerdictReport
vector_os_nano/vcli/verdict.py::VERDICT_SENTINEL
vector_os_nano/vcli/cli.py::run_one_turn
vector_os_nano/vcli/worlds/go2_sim_oracle.py::make_at_position
vector_os_nano/vcli/worlds/g1_perception_oracle.py::make_detection_matches_gt
```

## embodiments — how it plugs in

verified-against: 437e09d

- Invariant 3: embodiments are CONFIG, not code — a robot enters via `vector_os_nano/embodiments/<id>/robot.yaml` (go2/, g1/ today), never a kernel or driver edit.
- A robot.yaml is parsed fail-loud into frozen dataclasses by `vector_os_nano/embodiments/config.py::load_embodiment_config` → `config.py::parse_embodiment_config` → `EmbodimentConfig` (model / spawn / stance / sensors / policy / capabilities / grasp). Frozen dataclasses change ADDITIVELY only (new field last + default, Invariant 7).
- The sim drivers stand the body up and stash the manifest: `vector_os_nano/hardware/sim/mujoco_go2.py::MuJoCoGo2` and `mujoco_g1.py::MuJoCoG1` each call `load_embodiment_config("<id>")` at connect and store it as `self._config` — the handle `capability_profile._declared_profile` reads back at runtime.
- Drivers implement the duck-typed contract `vector_os_nano/hardware/base.py::BaseProtocol` (connect/walk/set_velocity/get_position/get_heading/get_lidar_scan/…) — the agent binds one as `agent._base` (plus `_arm`/`_gripper`/`_perception`).
- The DofLayout seam: `vector_os_nano/embodiments/dof_layout.py::DofLayout(model, root_body, num_actuated)` introspects the root freejoint's qpos/qvel slice addresses from the COMPILED model (replaces per-driver literals; g1's `mujoco_g1.py::_G1Offsets` is now a thin adapter subclass). `dof_layout.py::build_stance_vector` builds the nominal stance FROM the manifest's `stance:` dict in model joint order; `dof_layout.py::build_robot_geom_set` gives the lidar self-filter geom set.
- Capabilities: `config.py::CapabilityProfile` (has_base/has_arm/has_gripper/camera/lidar) is declared in robot.yaml, but the ONE runtime resolver is `vector_os_nano/embodiments/capability_profile.py::resolve_capability_profile(agent)`.
- Resolver authority split: GATED flags (has_base, camera) are runtime-presence-authoritative (byte-identical to the old `agent._base is not None` probes); ENRICHMENT flags (has_arm/has_gripper/lidar) reconcile runtime-OR-declared (honest go2+Piper runtime attach). `agent is None` (dev world) → all False.
- Its three consumers (all gates single-sourced, can't drift): `vector_os_nano/vcli/native_loop.py::_build_motor_tools` (navigate gate on has_base; manipulation-skill gate on has_arm), `vector_os_nano/vcli/worlds/robot.py::_agent_has_camera` (detector registration), `vector_os_nano/vcli/engine.py::init_vgg` (`_has_base` → nav decompose vocab, ~line 428).
- g1 example: camera-bearing, has_arm:false → native loop drops `_ARM_REQUIRING_SKILLS`, detect verifies via `detection_matches_gt` (g1_perception_oracle.py).
- Pending stages (docs/ARCHITECTURE.md ladder): **S4** = ONE generic driver class + embodiment registry replacing the per-driver `MuJoCoGo2`/`MuJoCoG1` classes (CEO-gated); **S5** = policy plugin (the `policy.ref/spec` block becomes a loadable plugin instead of driver-interpreted); **S6** = capability planner-exposure (shift GATED flags' authority to the DECLARED manifest — a behavior change when declared and runtime diverge, deliberately deferred).
- Adding a robot today: write robot.yaml (+ model assets) and a driver honoring BaseProtocol; after S4 the driver disappears — manifest only.

```
anchors:
vector_os_nano/embodiments/config.py::load_embodiment_config
vector_os_nano/embodiments/config.py::parse_embodiment_config
vector_os_nano/embodiments/config.py::EmbodimentConfig
vector_os_nano/embodiments/config.py::CapabilityProfile
vector_os_nano/embodiments/capability_profile.py::resolve_capability_profile
vector_os_nano/embodiments/capability_profile.py::_declared_profile
vector_os_nano/embodiments/dof_layout.py::DofLayout
vector_os_nano/embodiments/dof_layout.py::build_stance_vector
vector_os_nano/embodiments/dof_layout.py::build_robot_geom_set
vector_os_nano/hardware/base.py::BaseProtocol
vector_os_nano/hardware/sim/mujoco_go2.py::MuJoCoGo2
vector_os_nano/hardware/sim/mujoco_g1.py::MuJoCoG1
vector_os_nano/hardware/sim/mujoco_g1.py::_G1Offsets
vector_os_nano/vcli/engine.py::init_vgg
```

## native-loop — how it plugs in

verified-against: 437e09d

- The model-driven ReAct producer: `vector_os_nano/vcli/native_loop.py::run_turn_native(engine, user_message, …)` drives `engine._backend.call(messages, tools, system)` in a loop (cap `_MAX_NATIVE_TURNS=24`) and returns an `ExecutionTrace`. It NEVER computes `verified` — the caller `vector_os_nano/vcli/cli.py::run_one_turn` feeds the trace to `VerdictReport.from_trace`.
- Trace assembly: `native_loop.py::NativeStepRunner` — `dispatch_skill` captures the actor-causation baseline before a step's FIRST skill; `handle_verify` evaluates the model's expr via the live GoalVerifier, grades causation (`NativeStepRunner._grade`), and appends EXACTLY ONE StepRecord per (action-chain → verify) pair; `build_trace` finishes.
- Synthetic tools the runner OWNS (never wrapped from a skill): `verify(expr)` + `finish` (`VERIFY_TOOL`/`FINISH_TOOL`); D23 nudges (`_MAX_VERIFY_NUDGES=2`) refuse a finish riding on an unverified action.
- Post-place re-grasp guard (R257, E60; plug-and-play classifier R385/E174): a successful place step arms `NativeStepRunner._place_awaiting_verify`; while armed, a grasp call is REFUSED with `_POST_PLACE_REGRASP_NUDGE` (bounded by `_MAX_VERIFY_NUDGES`; the next `verify` clears it — an intermediate FAIL clears it for the NEXT object so quantity-place stays safe) so the brain can't misread the EXPECTED empty post-place gripper as a drop and re-grasp the just-placed object. "Is this a place / a grasp?" is classified by `native_loop._skill_is_place` / `_skill_is_grasp` = the curated `_PLACE_SKILLS`/`_GRASP_SKILLS` name-lists UNIONed with the skill's OWN structured metadata (`SkillWrapperTool._releases_object` = precond `gripper_holding_any` + gripper-emptying effect; `_is_grasp` = precond `gripper_empty`) so the guard is complete for a BYO place/grasp skill the kernel never named. Grasp side is byte-identical to the name-list on shipped skills; place side additionally guards shipped `handover` (empties the gripper — same `掉了` risk, was un-listed). Paired with the `_native_system_prompt` `place_guidance` block (empty gripper after a place is terminal success → verify `resting_on_receptacle`, never re-grasp). Fixes the R255 courtyard-place `掉了` thrash with NO weld/physics change (R256 refuted the mid-walk-drop theory). GRASP-SIDE SIBLING of the same `掉了` family (R386/E175): `core/agent.py::execute_skill` appends a `home` step (HomeSkill UNCONDITIONALLY opens the gripper) after a dispatched skill UNLESS the skill must keep its end-state gripper — suppressed for `pick(mode='hold')`/`gripper_close`/`gripper_open`/`home` (name/param) UNIONed with `core/agent.py::_skill_ends_holding` (the skill's OWN effect `gripper_state=='holding'` OR non-None `held_object`), so a BYO grasp-and-hold skill (and shipped `pick_top_down`/`mobile_pick`/`perception_grasp`, all effect `holding`) is not auto-homed into dropping what it just grasped; `pick` (effect open) is unaffected.
- Finish-on-fail guard (R206/E41, regression-pinned R309/E99): when the model's OWN latest `verify()` returned FALSE, a `finish`/stop is REFUSED with `_FINISH_ON_FAIL_NUDGE` (bounded by `_MAX_VERIFY_NUDGES`, then the run TERMINATES grading `verified=False` — never a forced green) and the brain is nudged toward the next action (for a multi-object place, grasp+place the NEXT object). Planner-free finish-gate: the model still owns decomposition; the runner only forbids quitting on a self-declared FAIL. Catches only the `>=N-then-quit` mode (a finish on a weaker passing predicate is out of scope — E41 residual). Regression: `tests/unit/vcli/test_native_loop.py` (FakeToolScriptBackend, no sim). This is the machinery the quantity-place ledger rests on (E38 seq / E99).
- Degenerate-spin guard (R274/E74 + goal-aware R279/E76): a flaky routing brain can issue action skills (perception_grasp/navigate/detect) turn after turn WITHOUT ever calling `verify`, burning the `_MAX_NATIVE_TURNS=24` budget on ZERO verdicts (~15min, nothing grounds, the eyes-judge never fires). The loop (`run_turn_native` body) counts consecutive turns with no MEASURABLE PROGRESS: soft nudge at `_UNPRODUCTIVE_NUDGE_AT=6` (`_UNPRODUCTIVE_SPIN_NUDGE` forces a verify), honest break at `_MAX_TURNS_WITHOUT_VERIFY=12` (trace grades RAN/empty, NEVER a forced green). R279 made it GOAL-AWARE: a verify counts as progress only if its `(normalized-expr, result)` is NOVEL vs the loop's `seen_verify_outcomes` set — re-reading an already-known outcome (an off-goal `at_position` verify interleaved to pin the counter) is NOT progress, so a thrash that dodges by re-verifying one sub-check still climbs to the break instead of the 24-cap. Keys on `NativeStepRunner.last_verify_result`; planner-free (no goal parse). Distinct from the finish-on-fail guard (which fires only when the model DID verify and it was FALSE).
- Tool injection lives in `native_loop.py::_build_motor_tools`: (a) engine registry's `code`-category tools via `_code_tools_from_registry` — in a robot world `_MUTATING_CODE_TOOLS` (file_write/file_edit/bash) are DROPPED (D17 fakeable-grasp prong 1); (b) coordinate `navigate` (`_NativeBaseNavigateTool`, FAR-planner avoidance route) gated on has_base; (c) learned detector `_NativeDetectTool` from the world-registered `detect` capability (`_registered_capability`, same instance `worlds/robot.py::register_capabilities` bound — no second model load); (d) world skills via `vector_os_nano/vcli/tools/skill_wrapper.py::wrap_skills` (`SkillWrapperTool` wraps each Skill; the world's own `navigate` skill is excluded).
- Capability gates single-source `embodiments/capability_profile.py::resolve_capability_profile`: `has_base` → navigate tool; `has_arm` False → `_ARM_REQUIRING_SKILLS` (pick/place/scan/describe/…) dropped so an armless g1 never chains a doomed pick.
- Verify vocab is single-sourced: oracle names from `trace_store.py::verify_oracle_names` (the SAME `engine._build_verifier_namespace` the spine reads) flow into `_verify_tool_schema` + the system prompt; `at_position` tol read live from go2_sim_oracle via `native_loop.py::_at_position_tol`.
- System prompt: assembled in `native_loop.py::_native_system_prompt` — verify vocab, scene object names (`_scene_object_names`, from `arm.get_object_positions()` keys, the holding_object canonical vocab), fetch-and-place + multi-object + locomotion/recovery guidance. The chat-path PERSONA is separate: `worlds/robot.py::persona_blocks` returns `ROBOT_ROLE_PROMPT`/`ROBOT_TOOL_INSTRUCTIONS` from `vcli/prompt.py` — the native loop does NOT use it.
- Routing pre-gate: `native_loop.py::should_attempt_native` — "does `_build_motor_tools` expose ≥1 tool"; fail-OPEN; still SHADOW (not wired into live routing).
- Firewall BY CONSTRUCTION: this module imports ONLY the spine (actor_causation, trace_store, skill_wrapper, the engine-passed verifier) — NEVER goal_decomposer/goal_executor/strategy_selector/vgg_harness; pinned by `tests/unit/vcli/test_native_loop_import_firewall.py`.
- navigate's cmd_vel runs on the ROS2 bridge thread, gated OUT of the actor-causation counter → a navigate step honestly grades UNCAUSED→RAN (moat never loosens); only `walk` carries the causation signal.

```
anchors:
vector_os_nano/vcli/native_loop.py::run_turn_native
vector_os_nano/vcli/native_loop.py::NativeStepRunner
vector_os_nano/vcli/native_loop.py::handle_verify
vector_os_nano/vcli/native_loop.py::_build_motor_tools
vector_os_nano/vcli/native_loop.py::_native_system_prompt
vector_os_nano/vcli/native_loop.py::should_attempt_native
vector_os_nano/vcli/native_loop.py::_NativeBaseNavigateTool
vector_os_nano/vcli/native_loop.py::_NativeDetectTool
vector_os_nano/vcli/native_loop.py::_ARM_REQUIRING_SKILLS
vector_os_nano/vcli/native_loop.py::_MUTATING_CODE_TOOLS
vector_os_nano/vcli/native_loop.py::_GRASP_SKILLS
vector_os_nano/vcli/native_loop.py::_PLACE_SKILLS
vector_os_nano/vcli/native_loop.py::_POST_PLACE_REGRASP_NUDGE
vector_os_nano/core/agent.py::execute_skill
vector_os_nano/core/agent.py::_skill_ends_holding
vector_os_nano/vcli/native_loop.py::_UNPRODUCTIVE_NUDGE_AT
vector_os_nano/vcli/native_loop.py::_MAX_TURNS_WITHOUT_VERIFY
vector_os_nano/vcli/native_loop.py::seen_verify_outcomes
vector_os_nano/vcli/native_loop.py::last_verify_result
vector_os_nano/vcli/tools/skill_wrapper.py::wrap_skills
vector_os_nano/vcli/tools/skill_wrapper.py::SkillWrapperTool
vector_os_nano/vcli/worlds/robot.py::persona_blocks
vector_os_nano/vcli/worlds/robot.py::register_capabilities
vector_os_nano/vcli/cli.py::run_one_turn
```
