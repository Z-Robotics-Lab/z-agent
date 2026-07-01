# DEBUG.md — D171 "DeepSeek native floundered on the PLACE compound"

## OBSERVE
- Repro A (direct, in-process): scratchpad/trace_place_native.py builds the in-process
  go2+arm agent (VECTOR_NO_ROS2=1, headless egl), wires DeepSeek (deepseek-chat) backend,
  calls engine.run_turn_native("把绿色的瓶子放到架子上") with an on_progress recorder.
  RESULT: perception_grasp(query='green bottle') -> holding_object('pickable_bottle_green')
  PASS actor=CAUSED -> mobile_place({}) -> resting_on_receptacle() PASS -> finish.
  VERDICT verified=True n_grounded=2. CLEAN two-action compound.
- Repro B (bare REPL acceptance face): scratchpad/repl_accept.py MODE=place
  VECTOR_PROVIDER=deepseek. RESULT: place_verified=None, frames=[]. Raw REPL log
  (/tmp/repl_accept/ds_place_g/repl.raw.log) shows ONLY the sim-start chat turn; the PLACE
  utterance "把绿色的瓶子放到架子上" was NEVER echoed. grep of the cleaned log: 0 hits for
  放到架子上/绿色/perception_grasp/mobile_place/grounded; only 8x"thinking" + 1x"answer" (all
  from sim-start). The place turn never ran; the 300s grounded-expect timed out.
- Recent changes: D171 (5e652e1, 0f7d498) recorded the "flounder" from an UNSAVED terminal
  observation ("ran bash which walk grasp") — no on-disk trace. bash is DROPPED from the
  native robot-world toolset (_MUTATING_CODE_TOOLS), so that description was impossible on the
  native path — a tell the observation was a harness artifact, not a real model trace.

## HYPOTHESIZE
| # | Hypothesis | Category | Evidence |
|---|-----------|----------|----------|
| H1 | DeepSeek tool-caller can't do the PLACE compound ("model-sensitivity") | model | D171 claim |
| H2 | qwen-tuned native compound guidance doesn't generalize to DeepSeek | prompt | D171 A/B |
| H3 | REPL routes place to legacy VGG (is_complex) not native -> "unmatched" FAIL | routing | D171 "unmatched" |
| H4 | repl_accept.py sim-start wait matches the ECHOED command line -> PLACE sent while sim still building/streaming -> input mangled, place turn never runs | harness | Repro B: utterance absent from log; full-timeout runtime; combo-mode had SAME documented bug |

## EXPERIMENT
### H1 — DeepSeek incapable of the compound
Direct run_turn_native on the exact utterance (Repro A) -> verified=True n_grounded=2,
grasp then place, both GT-oracle grounded. **H1 REJECTED.**

### H2 — guidance doesn't generalize to DeepSeek
Same Repro A: deepseek-chat read the CURRENT _native_system_prompt place_guidance and
correctly decomposed to grasp->verify->place->verify->finish. **H2 REJECTED.**

### H3 — REPL routes place to legacy, floundering "unmatched"
Repro B log shows the place utterance never reached ANY producer (native OR legacy) — no
"unmatched" this run. Routing is moot: the turn never ran. With Repro A proving native
handles a place command that DOES reach the turn loop, **H3 REJECTED (turn never ran).**

### H4 — harness sim-start sync bug
Repro B: after sendline("启动带手臂的 go2 仿真"), wait_prompt(120)'s `vector>` regex matches
the just-ECHOED "vector> 启动..." line INSTANTLY (identical to the combo-mode bug the driver's
own comment documents), so PLACE was sent while the sim build + sim-start chat answer were
still streaming; prompt_toolkit ate/garbled the line and the place turn never dispatched. The
utterance's total absence from the log + full-timeout runtime confirm it never became a turn.
**H4 CONFIRMED.**

## CONCLUDE
- Root cause: HARNESS bug in scratchpad/repl_accept.py — the sim-start->action handoff synced
  on the bare `vector>` prompt, which matches the echoed command line immediately, so the
  action command was injected before the REPL finished the sim-start turn and was lost. The
  product (native producer + DeepSeek + compound guidance) is CORRECT (Repro A).
- The D171 "model-sensitivity / DeepSeek floundered / routes to legacy VGG" finding is a
  MISDIAGNOSIS caused by this harness artifact.
- File: scratchpad/repl_accept.py — sim-start wait (was wait_prompt on `vector>`).
- Fix: sync sim-start on the sim tool marker ("sim start go2 ok") THEN drain REPL output until
  quiet before sending the action; drain before EVERY action command so none injects mid-turn.
- Regression guard: re-run bare REPL MODE=place via DeepSeek -> must ground (verified=True).
- Verify: VECTOR_PROVIDER=deepseek python scratchpad/repl_accept.py <fetch> <place> tag place
