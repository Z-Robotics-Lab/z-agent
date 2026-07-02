# native-loop — how it plugs in

verified-against: e7adec0

- The model-driven ReAct producer: `vector_os_nano/vcli/native_loop.py::run_turn_native(engine, user_message, …)` drives `engine._backend.call(messages, tools, system)` in a loop (cap `_MAX_NATIVE_TURNS=24`) and returns an `ExecutionTrace`. It NEVER computes `verified` — the caller `vector_os_nano/vcli/cli.py::run_one_turn` feeds the trace to `VerdictReport.from_trace`.
- Trace assembly: `native_loop.py::NativeStepRunner` — `dispatch_skill` captures the actor-causation baseline before a step's FIRST skill; `handle_verify` evaluates the model's expr via the live GoalVerifier, grades causation (`NativeStepRunner._grade`), and appends EXACTLY ONE StepRecord per (action-chain → verify) pair; `build_trace` finishes.
- Synthetic tools the runner OWNS (never wrapped from a skill): `verify(expr)` + `finish` (`VERIFY_TOOL`/`FINISH_TOOL`); D23 nudges (`_MAX_VERIFY_NUDGES=2`) refuse a finish riding on an unverified action.
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
vector_os_nano/vcli/tools/skill_wrapper.py::wrap_skills
vector_os_nano/vcli/tools/skill_wrapper.py::SkillWrapperTool
vector_os_nano/vcli/worlds/robot.py::persona_blocks
vector_os_nano/vcli/worlds/robot.py::register_capabilities
vector_os_nano/vcli/cli.py::run_one_turn
```
