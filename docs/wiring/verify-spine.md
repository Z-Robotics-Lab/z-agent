# verify-spine — how it plugs in

verified-against: e7adec0

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
- VECTOR_VERDICT escapes cli.main via `vector_os_nano/vcli/cli.py::run_one_turn` (the `-p/--json` non-interactive entry, ~line 1841): `_emit` prints `report.to_sentinel_line()` on stdout and returns `report.exit_code()` (0 verified / 2 ran-not-verified / 1 error-or-no-trace). Chat-only / error turns emit `VerdictReport.no_trace` (fail-closed).
- Seam for a new world: register oracles in `World.build_verify_namespace`; a new goal-conditioned bool predicate must ALSO be added to `_PREDICATE_ORACLES` (gate-approved) to GROUND as a bare call.

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
