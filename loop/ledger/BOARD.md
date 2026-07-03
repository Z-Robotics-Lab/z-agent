# Acceptance board (GENERATED — edit the ledger, not this file)

| capability | status | verdict n/m | face | provider | eyes | age (rounds) | commit |
|---|---|---|---|---|---|---|---|
| byo-model.gemini-3.5-flash | superseded | NOT-RUN 0/0 | bare-repl+nl | openrouter:google/gemini-3.5-flash | self-read | 45 | f159306 |
| byo-model.llama-3.3-70b | refuted | RAN 0/2 | bare-repl+nl | openrouter:meta-llama/llama-3.3-70b-instruct | self-read | 45 | f159306 |
| byo-model.mistral-medium-3-5 | superseded | NOT-RUN 0/0 | bare-repl+nl | openrouter:mistralai/mistral-medium-3-5 | self-read | 45 | f159306 |
| byo-model.openai-gpt-4o-mini | superseded | NOT-RUN 0/0 | bare-repl+nl | openrouter:openai/gpt-4o-mini | self-read | 41 | 61fde80 |
| fetch-place.nl-category-only | confirmed ⚠ STALE | GROUNDED 1/1 | bare-repl+nl | deepseek-chat | self-read | 41 | 61fde80 |
| fetch-place.nl-compound | confirmed ⚠ STALE | GROUNDED 2/2 | bare-repl+nl | deepseek-v4-flash | self-read | 38 | HEAD-R186 |
| fetch.nl-negated-distractor | confirmed | GROUNDED 1/1 | bare-repl+nl | deepseek-v4-flash | self-read | 24 | pending |
| fetch.nl-novel-geometry-purple-box | confirmed | GROUNDED 3/3 | bare-repl+nl | deepseek-v4-flash | self-read | 9 | pending |
| fetch.nl-novel-object-yellow | refuted | RAN 0/1 | bare-repl+nl | deepseek-v4-flash | self-read | 12 | pending |
| fetch.nl-ordinal-position-invariance | confirmed | GROUNDED 2/2 | bare-repl+nl | deepseek-v4-flash | self-read | 14 | pending |
| fetch.nl-ordinal-spatial | confirmed | GROUNDED 2/2 | bare-repl+nl | deepseek-v4-flash | self-read | 27 | pending |
| fetch.nl-plain-colour | confirmed ⚠ STALE | GROUNDED 1/1 | bare-repl+nl | deepseek-chat | self-read | 34 | HEAD-R190 |
| g1.navigation | confirmed | GROUNDED 1/2 | bare-repl+nl | deepseek-v4-flash | self-read | 7 | pending |
| g1.perception | provisional | GROUNDED 2/2 | bare-repl+nl | deepseek-v4-flash | self-read | 0 | pending |
| kernel.model-unavailable-surfacing | confirmed ⚠ STALE | PASS 3/3 | bare-repl+nl | openrouter (zero credit spent) | self-read | 44 | c59f386 |
| place.nl-plain-colour | confirmed | GROUNDED 2/2 | bare-repl+nl | deepseek-v4-flash | self-read | 24 | pending |
| quantity-place.nl | confirmed | GROUNDED-FLAKY 2/3 | bare-repl+nl | deepseek-chat | self-read | 19 | pending |
| quantity-place.nl-guardrail | confirmed | REFUTED 0/1 | bare-repl+nl | deepseek-chat | self-read | 15 | pending |
| quantity-place.nl-isolation | confirmed | GROUNDED 2/2 | bare-repl+nl | deepseek-v4-flash | self-read | 20 | pending |
| quantity-place.nl-robustness | superseded | GROUNDED 1/1 | bare-repl+nl | deepseek-chat | self-read | 18 | pending |

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
- E21 R184 [inconclusive] compound PLACE leg walk-loops because _native_system_prompt routes the place clause to navigate (H1), not because mobile_place is broken (H3) — retry only if: R185 A/B (old prompt + v4-flash) isolates fix-vs-model before promotion
- E22 R182 [confirmed] E18 mechanism = nav probe loop spinning under no-op time.sleep — retry only if: never blanket-mock builtins.open around config-reading code; never no-op time.sleep on wall-clock loops
- E22 R184 [confirmed] E18's MagicMock hot-loop is defusable at the TEST layer (fake clock advancing time + _nav stub) without touching product code — retry only if: n/a — regression: the test file itself + _FakeClock max_sleeps guard
- E23 R186 [confirmed] R184 E21: the native_loop.py prompt fix (place-clause is-not-a-nav-goal) CAUSED the compound combo 1/4->3/3 improvement — retry only if: never credit a code fix for a pass-rate delta while the model also changed (E9/E10/E21 model-sensitivity trap) — isolate first
- E24 R187 [confirmed] the R184 fetch-place.nl-compound provisional age-FAIL wedging preflight/check.sh is an un-adjudicated row (H1), OR a checker bug: the age-check has no supersession-awareness (H2) — retry only if: n/a — regression: tests/unit/test_checks_schema_provisional.py
- E25 R188 [inconclusive] harder-NL ORDINAL/positional find-fetch grounds to the spatially-correct object on the bare-REPL face, past D182 negated-distractor — retry only if: ordinal RESOLUTION confirmed (2/2 correct non-default target); a clean GROUNDED needs a non-handover utterance + grasp-reliable target (red can)
- E26 R190 [confirmed] R190 review: the 2 oldest confirmed BOARD rows still hold on the real bare-REPL face, the R188 ordinal provisionals adjudicate cleanly, and no headline claim from the last 10 rounds overclaims — retry only if: n/a - review round
- E27 R191 [confirmed] the R190 post-check quarantine (acceptance+experiments.jsonl deletions w/o CEO-APPROVED) is real data loss OR benign in-place re-serialization — retry only if: n/a - LESSONS hazard: append ONE preformatted line, never load-all+dumps+write-all
- E28 R192 [inconclusive] a clean ordinal GROUNDED (past R188/R190 confounds) is reachable via grasp-reliable GREEN + an opposite-direction ordinal (最左边的瓶子) — retry only if: promote next-round after a boundary+red-team; robustness (N runs) is the follow-up
- E30 R194 [refuted] R192 ordinal GROUNDED (把最左边的瓶子->green) is robust across N runs — retry only if: next: WIRE _resolve_ordinal_target into perception_grasp + sim-verify N>=3
- E31 R195 [inconclusive] wiring _resolve_ordinal_target into perception_grasp fixes E30 ordinal robustness (把最左边的瓶子->green N>=3) — retry only if: next: isolate grasp-execution miss on ordinal->colour path, then 把最左边的瓶子->green N>=3 GROUNDED
- E32 R196 [inconclusive] R194/R195 ordinal 'grasp miss/green to floor' is a grasp-execution defect on the ordinal->colour path — retry only if: bare-REPL '拿过来' fetch still routes handover after the fix
- E33 R197 [confirmed] R196 ordinal fetch GROUNDED survives a round boundary + red-team and is genuinely spatial (not a lucky green default) — retry only if: n/a - confirmed; frontier moves to quantity/anaphora.
- E34 R197 [inconclusive] quantity NL (两个/两瓶) needs new verify machinery vs reusing an existing oracle — retry only if: next: frame quantity as placed_count>=2 place task; check if D168 place gate blocks before sim.
- E35 R198 [refuted] R197/E34 scope: go2 quantity-place predicate is placed_count() >= 2 — retry only if: NEVER placed_count for go2 quantity-place; R199 verify 把两个瓶子放到架子上 -> resting_on_receptacle()>=2
- E36 R199 [refuted] R198 machinery grounds quantity-place 把两个瓶子放到架子上 -> resting_on_receptacle()>=2 on the bare face (deepseek-v4-flash) — retry only if: isolate green-2nd-grasp vs planning, then a native_loop QUANTITY decomposition guardrail (E23: no prompt-fix credit across a model change)
- E37 R200 [confirmed] R200 review: 2 oldest confirmed BOARD rows still hold on the real bare face; R199 quantity-place provisional adjudicates; gates/tokens clean. — retry only if: n/a - review round
- E38 R203 [confirmed] E36 isolation: R199 quantity-place 2nd-object stall is BRAIN DECOMPOSITION (cant self-split 两个), NOT grasp-execution of a 2nd object — retry only if: land native_loop QUANTITY decomposition guardrail, re-verify quantity utterance (E23: no prompt-fix credit across model change)
- E39 R204 [confirmed] E38 follow-up: R199 quantity 2nd-object stall is BRAIN-SPECIFIC — a different brain self-decomposes 两个 into 2 grasp+place legs where v4-flash abandoned obj-2 — retry only if: robustness N>=3 deepseek-chat, OR test if v4-flash needs a QUANTITY guardrail
- E40 R205 [confirmed] R204/E39 quantity-place GROUNDED (把两个瓶子放到架子上, deepseek-chat) is ROBUST across N>=3 — retry only if: quantity determinism needs a runner QUANTITY guardrail OR pivot to breadth (2nd scene/world, D182 grounder)
- E43 R209 [inconclusive] 最左边的瓶子 reads LIVE positions: under VECTOR_SCENE_SWAP the SAME utterance grasps BLUE (new leftmost) not the frozen GREEN (E31/E33) — retry only if: promote next-round after boundary+red-team; robustness N>=3 swap follow-up
- E44 R210 [confirmed] R210 review: the E43 position-invariance provisional reproduces on the real bare face across a round boundary; the 2 oldest confirmed BOARD rows + wiring/lessons hold — retry only if: n/a - review round
- E45 R211 [inconclusive] a NOVEL 4th object (yellow bottle) added as CONFIG+driver+skill, zero kernel edits, grounds an NL colour-fetch on the real bare face -- object-diversity breadth past the frozen RGB triple — retry only if: promote next round after boundary+red-team
- E46 R212 [refuted] R211/E45 novel-object yellow GROUNDED 1/1 reproduces on the real bare face across a round boundary (§1b adjudication) — retry only if: N=1 fetch passes provisional-only; promote only on N>=2 same-brain reproduction, or a more reliable brain / D182 grounder lands
- E47 R212 [inconclusive] a NOVEL non-cylinder GEOMETRY (purple box, 5th pickable) added as CONFIG+driver+skill zero kernel edits grounds an NL fetch on the real bare face -- geometry breadth past R211 colour-only — retry only if: promote next round only after N>=2 same-brain reproduction (E46 lesson)
- E47 R215 [confirmed] the R212/E47 purple-box GROUNDED (1/1) reproduces N>=2 same-brain (deepseek-v4-flash) on the bare face, past the E46 sibling-yellow fragility -> confirm or refute the provisional — retry only if: the purple-box scene config / weld tuple / HSV band changes, or deepseek-v4-flash routing changes
- E48 R216 [inconclusive] the CURRENT brain (v4-flash, all recent go2 work) also drives the 2nd embodiment g1-humanoid to GROUNDED nav bare-face 0 kernel edits — refreshing the 32-round-stale R183 g1.nav deepseek-chat row (cross-embodiment breadth, non-gated slice of next#1) — retry only if: n/a - promote next round; NEW 3rd embodiment (BYO URDF+driver) is S4-gated + multi-round SDD
- E49 R217 [confirmed] R216/E48 g1.navigation cross-embodiment (current brain drives 2nd embodiment to GROUNDED nav) reproduces across a round boundary at NON-MEMORIZED coords — retry only if: n/a - confirmed. For a clean 2/2 pick TWO probe-verified REACHABLE non-memorized coords; (11,3)/(11,4) are obstacle-blocked
- E50 R219 [inconclusive] the current brain (deepseek-v4-flash) still drives the 2nd embodiment g1 (camera-only) to a GROUNDED perception match on the bare face 0 kernel edits — refreshing the 29-round-stale R190 g1.perception deepseek-chat row (non-gated proxy per STATUS next#1) — retry only if: promote to confirmed R220; NEW 3rd embodiment is S4-gated + multi-round SDD
- E50 R223 [refuted] Adjudicate R219 E50: does g1.perception GROUNDED reproduce across a round boundary? Re-run g1_accept RED+GREEN foreground x2. — retry only if: g1 head-cam re-framed to center the red stool OR seg-centroid tol widened+justified
- E50 R224 [inconclusive] STATUS next#1: HARDEN g1.perception (R223 refuted RAN 0/17) into a RELIABLE bar via a WORLD-config re-frame (Inv.3), NOT verify-loosening (Inv.1). — retry only if: promote to confirmed R225 after boundary+red-team; NEW 3rd embodiment S4-gated
