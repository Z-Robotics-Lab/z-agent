# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D180 — BYO-MODEL seam HARDENED + D179 "over-caution" REFUTED (positive control). Both
provider paths were billing-blocked this round (DashScope Arrearage on qwen-max + qwen3-vl-plus eyes; OpenRouter
down to ~$0.0007 residual), so full sim acceptance was externally gated → pivoted to the non-gated seam frontier
and did code-only, error-path-verifiable work. ZERO credit spent (all failures reject pre-generation).
- REFUTED D179: `mistral-small-3.2-24b-instruct` (a MISTRAL family model) tool-calls the sim-start NL PERFECTLY on
  the identical prompt. gemini-3.5-flash / mistral-medium-3-5 fail with `402 "Prompt tokens limit exceeded 1114>428"`
  = the PROMPT exceeds residual credit; the model never ran. "over-caution" was drained-credit/stale-id, NOT behavior.
- BUILT (TDD, non-gate; grade()/spine byte-unchanged): `ModelUnavailableError` (subclass of APIStatusError) turns the
  3 non-recoverable BYO failures (402 hard credit-exhaustion · 404 no-endpoints · 400 invalid model id) into ONE clean
  line "Model '<id>' unavailable via <provider>: <reason>. Check VECTOR_MODEL and credits." Recoverable 402 STILL
  downshifts once then escalates. Closes the cli.py:497 swallow that made D179 misread balance failures as no-action.
- REAL-VERIFIED on the BARE REPL (scratchpad/model_unavailable_accept.py, PTY, no flag): 3 shapes × both routes
  (native "model unavailable:" + legacy "Error:") surface the clean message; NO raw JSON/traceback; red-teamed.
  73 backend + 93 cli/native unit tests green.

goal:    PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/CAPABILITY/MODEL; plan·route·verify·recover.
         Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   BYO-MODEL seam robust (clean unavailable-surfacing, 3 shapes). N=3 accepted families stands; N≥4 blocked ONLY
         by external credit (mistral-small ready). VLN GROUNDED accept still CEO-gated (near_object spine allowlist).
owns:    vcli/backends/openai_compat.py (ModelUnavailableError) + cli.py native catch + tests/unit/vcli/test_backends.py.
blocked: BILLING (external, CEO): DashScope arrears (qwen orchestration + qwen3-vl eyes down) + OpenRouter ~$0.0007
         residual → full sim acceptance + N≥4 gated on a top-up. PRE-EXISTING: test_config_deepseek_provider.py 3 fails.
next:
  1. [EXTERNAL/CEO] Credit top-up (OpenRouter + DashScope) is the ONLY blocker to (a) earning N≥4 acceptance
     (mistral-small-3.2-24b proven tool-calls) and (b) any full-sim REAL-VERIFY round. Queue for Yusen.
  2. [FRONTIER, non-gated] verify-expr robustness — a weak model dropping `==True` / malforming the expr is the #2
     BYO failure; connects to the plug-and-play-predicate META gate (below). Buildable + unit-verifiable now.
  3. [FRONTIER, non-gated] arm-free `describe` for g1 via VLM caption + GT-backed `describe_scene` state-oracle —
     BLOCKED on a working VLM (qwen3-vl down, OpenRouter VLM needs credit). Defer until billing restored.
  4. [GATE-THEN-BUILD] VLN GROUNDED accept on near_object approval (see gate queue). Root cause = hardcoded kernel
     `_PREDICATE_ORACLES` (evidence_classifier.py:52) → META plug-and-play-predicate gate subsumes it.

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **BILLING (external, NEW)**: OpenRouter credit exhausted (~$0.0007) + DashScope arrears — blocks all full-sim
  acceptance + N≥4. Not a code fix; needs an account top-up. Batch into the return exec summary.
- **META: plug-and-play verify-predicates** — `_PREDICATE_ORACLES` is a hardcoded kernel list
  (evidence_classifier.py:52 self-flags "R2 should derive from metadata"); every new predicate (D178 near_object,
  D169 near) is a spine gate → VIOLATES "bring a verify-predicate — no kernel edits". Resolution: world-declared
  predicate metadata (stricter-only). ONE decision subsumes the per-predicate gates below. Spine-semantics gate.
- **D178 near_object VLN predicate** (CONFIRMED gate, exec summary in DECISIONS D178): world-side GT oracle + kernel
  allowlist entry; same category as `resting_on_receptacle` (D106-approved). grade() byte-unchanged. → go/no-go.
- **D176 cmd_motion driver seam** (likely non-gate): enables g1 nav GROUNDED; grade() spine byte-unchanged.
- **D168 place-oracle** resting_on_receptacle object-BLIND+absolute-count → harden to identity+delta. LOAD-BEARING. → go/no-go.
- **S8** retire legacy keyword producer (READY): delete IntentRouter/StrategySelector/_DIR_MAP + legacy GoalDecomposer;
  rewire 4 should_use_vgg → should_attempt_native (D74); keep VECTOR_LEGACY_TURN hatch. → go/no-go.
- **relational-place near(a,b)** (D169): NEW verify predicate → spine-semantics gate (subsumed by META above).
- **Stage gates:** S4 embodiment-registration · S5 ControlPolicy + convex_mpc dep · S6 capability perm/security ·
  nav→FAR causation (D14) · strategy_params (D52) · explore TARE · VLN SysNav. New deps/interfaces/hw/sec here.
