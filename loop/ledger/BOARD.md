# Acceptance board (GENERATED — edit the ledger, not this file)

| capability | status | verdict n/m | face | provider | eyes | age (rounds) | commit |
|---|---|---|---|---|---|---|---|
| byo-model.gemini-3.5-flash | superseded | NOT-RUN 0/0 | bare-repl+nl | openrouter:google/gemini-3.5-flash | self-read | 4 | f159306 |
| byo-model.llama-3.3-70b | refuted | RAN 0/2 | bare-repl+nl | openrouter:meta-llama/llama-3.3-70b-instruct | self-read | 4 | f159306 |
| byo-model.mistral-medium-3-5 | superseded | NOT-RUN 0/0 | bare-repl+nl | openrouter:mistralai/mistral-medium-3-5 | self-read | 4 | f159306 |
| byo-model.openai-gpt-4o-mini | superseded | NOT-RUN 0/0 | bare-repl+nl | openrouter:openai/gpt-4o-mini | self-read | 0 | 61fde80 |
| fetch-place.nl-category-only | confirmed | GROUNDED 1/1 | bare-repl+nl | deepseek-chat | self-read | 0 | 61fde80 |
| fetch-place.nl-compound | refuted | RAN 1/4 | bare-repl+nl | deepseek-chat | self-read | 0 | 61fde80 |
| fetch.nl-negated-distractor | confirmed | GROUNDED 1/1 | bare-repl+nl | deepseek-chat | self-read | 0 | 61fde80 |
| fetch.nl-plain-colour | confirmed | GROUNDED 2/2 | bare-repl+nl | deepseek-chat | self-read | 2 | 5aa71cb |
| g1.navigation | confirmed | GROUNDED 2/2 | bare-repl+nl | deepseek-chat | self-read | 0 | 61fde80 |
| g1.perception | confirmed | GROUNDED 1/1 | bare-repl+nl | deepseek-v4-flash | self-read | 8 | 0cc4d5b |
| kernel.model-unavailable-surfacing | confirmed | PASS 3/3 | bare-repl+nl | openrouter (zero credit spent) | self-read | 3 | c59f386 |
| place.nl-plain-colour | confirmed | GROUNDED 3/3 | bare-repl+nl | deepseek-chat | self-read | 2 | 5aa71cb |

## Open refuted / do-not-retry (from experiments.jsonl)
- E1 R150 [confirmed] an append-only DECISIONS ledger can be compacted without losing accepted rulings — retry only if: n/a — folds stay CEO-gated (doc-governance)
- E2 R163 [refuted] in-process --sim-go2/-p numbers (FETCH .93/.87, PLACE 8/8 skill + 3/3 e2e) count as acceptance — retry only if: never — Invariant 2: flag/-p/script-only is never the acceptance face
- E3 R164 [refuted] bare-NL ROS2-stack fetch failure = rclpy startup crash ('cannot schedule new futures') — retry only if: a startup-phase traceback is captured from a PRESERVED run
- E4 R164 [refuted] the 10.6h loop stall = pipeline/timeout wedge — retry only if: n/a — NEVER-KILL-INFRA is a standing hard rule; arbitration lives in the harness, never the round
- E5 R166 [refuted] the single-source in-process builder closes D163 -> bare-REPL fetch/place ground — retry only if: n/a — resolved; regression = repl_accept.py grounding
- E6 R168 [refuted] colourless category NL ('罐子') can ground via raw detector confidence — retry only if: the detector gains colour/shape discrimination for identical geoms
- E7 R169 [refuted] the native producer handles a single-utterance fetch-AND-place compound — retry only if: n/a — fixed; regression = MODE=combo grounded-verdict sync
- E8 R170 [plateau] the acceptance face is runnable this round (qwen brain + qwen3-vl eyes) — retry only if: provider billing restored (external/CEO) or a funded BYO model found (R171 found DeepSeek)
- E9 R171 [refuted] PLACE compound is model-sensitive: DeepSeek native flounders -> legacy VGG (0 verdicts) — retry only if: the R172 ANSI-sync harness fix (26eb171/3b28576) is reverted
- E10 R172 [refuted] bare-REPL acceptance flakiness = model-sensitivity / billing — retry only if: n/a — never sync acceptance harnesses on a raw PTY stream or a model chat claim
- E11 R173 [refuted] red 0/3 (R172) = red-can grasp/IK robustness ceiling — retry only if: grasp_probe.py or repl MODE=fetch red-can regresses
- E12 R175 [refuted] g1 RED perception fails on the face (RAN) because the moat/perception is wrong — retry only if: n/a — regression tests/vcli/test_g1_arm_capability_gate.py
- E13 R177 [refuted] the OpenRouter 3rd-brain 404 = key/network fault — retry only if: n/a — fixed; probe candidate ids before blaming key/network
- E14 R178 [refuted] g1 VLN ('走到红色的东西那里') can ground honestly on the current scene as-is — retry only if: the near_object spine gate is approved (then wire approach + accept on the bare REPL)
- E15 R179 [refuted] gemini-3.5-flash / mistral-medium-3-5 no-tool-call on sim-start = model over-caution — retry only if: provider credit restored AND 402/404 ruled out BEFORE diagnosing model behavior
- E16 R181 [refuted] OpenRouter /key limit_remaining=6.85 = spendable credit (so the D180 billing block was over-called) — retry only if: OpenRouter exposes an explicit balance field; until then always probe with a real paid turn
- E17 R181 [refuted] MODE=both (fetch then place in one session) yields a valid place verdict — retry only if: the harness grades place causation-safely (fresh session or baseline-delta grasp)
- E18 R182 [refuted] tests/unit is safe to run as ONE unbounded pytest process — retry only if: pytest ALWAYS via scripts/run-tests (MemoryMax scope, serial chunks); unbounded never
- E19 R182 [confirmed] 27 structure docs consolidate to ~15 lean files without content loss (CEO: few short files) — retry only if: n/a - future doc growth gated by check.sh allowlist+caps
- E20 R183 [refuted] the 5 backfilled provisional acceptance rows all hold on independent bare-REPL re-run (also red-teams the 14h-loop claims) — retry only if: n/a
