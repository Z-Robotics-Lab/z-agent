# Architecture Decisions (consolidated)

One line of history per decision — dot-points only. Full original prose is in git history
(`git log --all -- docs/architecture-decisions/`). Append a new entry at the bottom; never
rewrite an accepted one (record corrections as a new dated line).

---

## D3 — Hardware Abstraction Layer · Accepted 2026-03-25 (live from v2.0)
- Hardware-agnostic: SO-101 and Go2 are interchangeable adapters into one Agent/Skill/LLM pipeline.
- Formalized `BaseProtocol` + `PerceptionProtocol` (alongside `ArmProtocol`/`GripperProtocol`); dict-based `SkillContext`.
- Rejected ad-hoc `base: Any` duck-typing — brittle as hardware variants multiply, blocks capability queries.

## D4 — Web Visualization replaces RViz · Accepted (revised) 2026-04-09
- ROS2 web viz via **Foxglove Studio** (revised away from a self-built Three.js viewer).

## D5 — Isaac Sim Integration · Superseded / Paused
- Docker'd Isaac as a high-fidelity sim backend — **paused/archived** during the v2.4 perception pivot.
- **MuJoCo remains the primary sim** for dev + CI; the in-tree Isaac proxy is an interface/topic contract only (no working Isaac SDK code).

## D6 — Agent Kernel / World-Plugin · Accepted 2026-06-05
- Engine + VGG + tools + backends + session + permissions = a **model-/skill-/hardware-agnostic orchestration KERNEL**; each deployment target = a **world plugin**.
- A world registers exactly 4 things: tools, verify/primitive namespace, decompose vocabulary, persona. **The kernel never imports a world.**
- A default `dev`/`code` world ships in-kernel (a build/test means, not the product); the robot is an optional world plugin. Migration, not rewrite.

## D7 — Open-Loop Compiler → Grounded Closed-Loop Controller · Accepted 2026-06-06 (staged)
- Re-architect VGG from a blind one-shot compiler into a grounded closed-loop controller via 5 bets:
  - **Observation loop:** per-run `Blackboard`; `GoalVerifier` returns `(bool, raw_value)`; `StepRecord.result_data`; `${step.output.path}` binding (no f-strings over data).
  - **Living plan:** control-flow IR (`foreach`/`until`/`if`) + observation-driven mid-tree replan from current `world_context`, not the stale T=0 context.
  - **Single-source action space** from the skill registry (kill the Go2 split-brain vocab + keyword sieves); fail-loud `validation_notes` fed back into replan.
  - **Ground the planner:** typed perception facts, referring-expression resolution, coherent `ObjectMemory`.
  - **Unify planning paths:** merge `VectorEngine` + `VGGHarness` into one controller.
- NOTE: D9 supersedes the bespoke-planner direction — the MODEL, not hand-written decompose/replan code, now owns plan/route/recover (D7's closed-loop *grounding/observation* ideas still hold; its hand-authored planner does not).

## D8 — Playground as a Parallel Track via Seam-as-Contract · Accepted 2026-06-06
- Playground developed as a **separate parallel track**; the kernel/world **seam is the versioned public contract** the tracks integrate across.
- Extend the seam with a **verified-loop observation surface** (GoalTree + per-step StepRecord + replan notes for a front-end to render).
- v1 = **preset scenes** entered via NL (agent owns the long chain once inside; dynamic scene assembly deferred); deterministic sim-oracle verify + VLM perception (generator/verifier independence).
- NOTE: `feat/playground-vln` was later **abandoned** (never merged); `master` is the base (2026-06-18 reframe).

## D9 — Native Model-Driven Tool-Use Producer IS the Orchestration Design · Accepted (CEO ruling) 2026-06-19
- **The native model-driven tool-use producer is the correct design; the legacy hardcoded planner (`should_use_vgg`→`vgg_decompose`→direct skill execution) is WRONG and is being strangled.** Going forward: **use the native producer and optimize it iteratively — never retreat to the legacy planner for any capability.** (CEO ruling.)
- Why: routing/decompose/recover belong to the MODEL (the North Star), not bespoke keyword code; re-implementing planning in code is the drift D7 + the 2026-06-18 reframe identified.
- **Cutover (done in the REPL):** bare `vector-cli` + NL runs native by default — `cli.run_turn_unified` attempts native-first, falls back to legacy ONLY on a zero-action turn; `VECTOR_REPL_NATIVE=0` forces pure-legacy. Legacy VGG stays only as the strangler-fig fallback, pending staged reversible deletion. Merge-to-master = separate CEO gate.
- Mechanism: `vcli/native_loop.py run_turn_native` — the MODEL drives a ReAct loop (world skills + registry code tools + synthetic `verify`/`finish`); assembles an `ExecutionTrace` the honest verify spine grades BYTE-UNCHANGED. Never computes `verified` itself (moat only ever STRICTER, rule 5).
- **Known native improvements (optimize — NOT reasons to retreat to legacy):**
  - **Nav avoidance:** native locomotion uses the open-loop `walk_forward` (no lidar/planner) → `走到坐标 (x,y)` walks straight into obstacles (e.g. `pick_table` @ (11,3), go2 starts (10,3)). NEXT = route native go-to-place through the nav-stack avoidance route (`publish_goal`→FAR/local-planner/lidar); cmd_vel motion grades RAN until actor-causation extends to cmd_vel.
  - **Latency:** native = several LLM round-trips + currently SYNCHRONOUS (blocks the REPL) vs legacy async/responsive → optimize to async + fewer round-trips.

## D10 — Recover-by-retry is FAIL-CLOSED by design (the honest characterization) · Accepted 2026-06-20
- The native producer's RECOVER pillar (north-star #4) is honest BY CONSTRUCTION, proven on real go2 sim via `cli.main` PTY (`tests/vcli/test_native_loop_recover_pty.py`): a fake "done" (finish while the latest verify FAILs) grades RAN/verified False; a never-landing recovery TERMINATES (backend-exhaust `end_turn`, `max_turns=24` never hit) all-RAN; a GENUINE in-turn recovery (walk-short→verify FAIL→walk-again→verify PASS→finish) records `[RAN, GROUNDED]` and grades **verified False** — the all-GROUNDED gate (`trace_store.evidence_passed`) fails CLOSED on the recorded FAIL row (`native_loop` records one StepRecord per verify, no dedup; a verify closes the step and resets the baseline).
- CONSEQUENCE (made explicit, not hidden): a deterministic recover-to-verified-True is UNREACHABLE without a per-sub-goal latest-verify gate that lets a later PASS overwrite a recorded FAIL — that is LOOSER, and rule 5 (verify only ever stricter) forbids it. The spine stays BYTE-UNCHANGED. Recover-to-verified-True is demonstrated ONLY via the LIVE path where the model verifies once after recovering (`test_native_loop_multistep_live_pty`). The moat never falsely greens a recovery; it can only be stricter than the model.
- Goal-authenticity of the verify constant (does the (x,y) match the real task goal) remains the deferred residual — unchanged by this decision.
