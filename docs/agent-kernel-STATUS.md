# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D179 — BYO-MODEL boundary MAPPED (red-teamed). VLN #1 stays CEO-gated (near_object spine
allowlist), so this round pivoted to the non-gated frontier "N≥4 BYO-MODEL" and honestly bounded it: the MODEL
seam is zero-kernel-edit for 3 more families, but end-to-end acceptance is model-capability-bound. The moat held.
- SEAM (proven, ZERO code changed): llama-3.3-70b, gemini-3.5-flash, mistral-medium-3-5 each plug into the bare
  `vector-cli` REPL with only `VECTOR_PROVIDER=openrouter VECTOR_MODEL=<id>` — no kernel/driver edit.
- ACCEPTANCE (honest negative, `scratchpad/g1_accept.py`, g1 in-process, RED-grounds/GREEN-refutes):
  * llama-3.3-70b — starts g1 by NL, chains detect→verify, but emits a MALFORMED verify (`detection_matches_gt(`,
    unclosed) → SyntaxError → RAN (2/2 runs, systematic). Moat REFUSED it, no false green.
  * gemini-3.5-flash & mistral-medium-3-5 — won't emit the sim-start tool call by NL (chat/ask, 4 retries) → g1
    never starts. Root cause (over-caution vs OpenRouter tool-schema translation) NOT isolated (llama DID tool-call).
- MOAT held CROSS-MODEL: no weak/malformed model faked a GROUNDED verdict (invariant 1, empirically). N=3 accepted
  families (Anthropic · DeepSeek · OpenAI gpt-4o-mini) stands; N≥4 NOT earned. No overclaim.

goal:    PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/CAPABILITY/MODEL; plan·route·verify·recover.
         Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   VLN GROUNDED accept gated (near_object spine allowlist). BYO-MODEL seam proven ×6 families, end-to-end
         acceptance ×3 (moat gates the weaker 3). BYO-ROBOT go2+g1.
owns:    docs only this round (DECISIONS D179 + STATUS). No code touched. Evidence in /tmp/g1_accept/{llama,llama2,gemini,mistral}.
blocked: qwen/DashScope ARREARS → Qwen3-VL EYES down (OpenRouter is the substitute VLM path). NOT loop-blocking.
         PRE-EXISTING: tests/unit/vcli/test_config_deepseek_provider.py 3 fails (provider naming drift) — untouched.
next:
  1. [FRONTIER, non-gated] Robustify BYO-MODEL tool-calling across families so N≥4 EARNS acceptance:
     (a) diagnose why gemini/mistral don't tool-call sim-start by NL — is it model over-caution (fix: persona /
     tool-instructions nudge, re-verify the passing 3 don't regress) or the openrouter tool-schema path? llama
     DID tool-call, so isolate. (b) verify-expr robustness — a weak model dropping `==True` or malforming the
     expr is the #2 failure; connects to the plug-and-play-predicate gate (below).
  2. [GATE-THEN-BUILD] VLN GROUNDED accept on near_object approval (see gate queue). The RECURRING gate root cause
     is `_PREDICATE_ORACLES` being a hardcoded KERNEL list (evidence_classifier.py:52 flags R2) — the North-Star-
     aligned fix is world-declared predicate metadata (one meta-decision resolves D178 near_object + D169 near +
     the D179 verify-expr brittleness). Fold into ONE exec summary when Yusen returns; it's a spine gate — don't cross.
  3. [FRONTIER, non-gated] arm-free `describe` for g1 (native_loop.py:109 flags it) via OpenRouter VLM caption +
     a GT-backed g1 `describe_scene` oracle (state-oracle, NON-gated — not a new _PREDICATE_ORACLES name).
  4. [SPINE] D168 place-oracle identity+delta — LOAD-BEARING (D174 place leans on it). CEO gate, queue for Yusen.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **META (recommended framing): plug-and-play verify-predicates** — `_PREDICATE_ORACLES` is a hardcoded kernel list
  (evidence_classifier.py:52 self-flags "R2 should derive from metadata"); every new predicate (D178 near_object,
  D169 near) is therefore a spine gate, which VIOLATES the North Star "bring a verify-predicate — no kernel edits".
  Proposed resolution: world-declared predicate metadata (stricter-only; worlds already register verify bindings).
  ONE decision subsumes the per-predicate gates below. Spine-semantics gate → go/no-go.
- **D178 near_object VLN predicate** (CONFIRMED gate, EXEC SUMMARY in DECISIONS D178): world-side
  `near_object(colour,radius)` GT oracle + list in kernel allowlist `_PREDICATE_ORACLES`. Same category as
  `resting_on_receptacle` (D106-approved). grade() byte-unchanged, stricter-only. → go/no-go.
- **D176 cmd_motion driver seam** (flagged, likely non-gate): enables g1 nav GROUNDED; grade() spine byte-unchanged.
- **D168 place-oracle** resting_on_receptacle object-BLIND + absolute-count → harden to identity+delta (stricter-only). LOAD-BEARING. → go/no-go.
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg → should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go.
- **relational-place near(a,b) predicate** (D169): NEW verify predicate for "放到X旁边" → spine-semantics gate (subsumed by META above).
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
