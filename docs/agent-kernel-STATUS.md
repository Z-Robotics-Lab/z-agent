# Vector OS — STATUS (resume anchor · SNAPSHOT, not a log)

Read FIRST. GOAL=[../CLAUDE.md](../CLAUDE.md) North Star · design=[ARCHITECTURE.md](ARCHITECTURE.md) ·
decisions=[DECISIONS.md](DECISIONS.md) · hidden bugs=[tricky-bugs.md](tricky-bugs.md). Round history → DECISIONS + git.

updated: 2026-07-01 · D181 — D163 RE-ACCEPTED on the bare-REPL NL face (in-process fetch+place, 3 colours, N=5, eyes-confirmed, red-teamed).
- ACCEPTANCE (honest): bare `vector-cli` REPL + NL (repl_accept.py, PTY, no flag), orchestration = DeepSeek-direct
  `deepseek-chat` (an ACCEPTED family), in-process VECTOR_NO_ROS2=1. 5/5 GROUNDED True, ALL launch_explore_seen=False
  (= D163 in-process path took, no ROS2 stack). Eyes = the SAME offscreen verdict render, read back per turn:
  green+red grasped (fetch True 1/1); green+red+blue placed on receptacle (place True 2/2, MODE=place fresh session →
  grasp CAUSED). Colour tracked the NL every run → perception colour-selective + load-bearing.
- RED-TEAM caught a real trap: MODE=both place verdict was untrustworthy (bottle pre-held from fetch → identical eyes
  frame, uncaused grasp) → re-ran MODE=place (fresh) for the 3 honest place groundings. Moat held: no false green.
- BILLING re-read (corrects D180 optimism): OpenRouter `/api/v1/key` `limit_remaining` is WEEKLY RATE-LIMIT headroom,
  NOT credit balance — a live turn still 402'd "out of credit". OpenRouter + DashScope credit ARE exhausted. BUT
  DeepSeek-direct (DEEPSEEK_API_KEY) is REACHABLE + FUNDED + tool-calls the FULL fetch+place verify path → the core
  acceptance is NOT billing-blocked. D180 seam confirmed LIVE too: gpt-4o-mini(OpenRouter) surfaced a clean
  "model unavailable: ... out of credit ... Check VECTOR_MODEL and provider credits." (no traceback).

goal:    PLUG-AND-PLAY runtime for physical AI — BYO robot/policy/skill/CAPABILITY/MODEL; plan·route·verify·recover.
         Bare `vector-cli` + NL is the ONLY acceptance face; honest-verify spine frozen (stricter-only).
phase:   D163 CLOSED — in-process fetch+place RE-ACCEPTED (3 colours, N=5, DeepSeek, eyes-confirmed, red-teamed).
owns:    verify round — no code change (D163 code already at 4d8da99/adcd04b). Harness: scratchpad/repl_accept.py.
blocked: NONE for core acceptance (DeepSeek funded). OpenRouter+DashScope credit exhausted → blocks OpenRouter-N≥4
         (mistral-small) + the automated VLM vision-judge witness ONLY. PRE-EXISTING: test_config_deepseek_provider.py 3 fails.
next:
  1. [FRONTIER] robust find-fetch-place: harder NL (MODE=combo "把X拿过来放到架子上"; distractor colours; ambiguity/negation),
     push N per colour to failure — go past the clean 3-colour floor. DeepSeek funded → runnable now.
  2. [FRONTIER] 2nd embodiment g1 GROUNDED nav — do the non-gated g1 build; VLN GROUNDED accept stays CEO-gated (near_object).
  3. [BYO-MODEL] N≥4 mistral-small-3.2-24b ready on OpenRouter the moment its credit is restored (external).

## Pending CEO gates (decision queue — terse; do NOT cross autonomously)
- **BILLING (external, DOWNGRADED)**: OpenRouter + DashScope credit exhausted. NO LONGER blocks core acceptance
  (DeepSeek-direct is funded). Blocks only OpenRouter-N≥4 + the automated VLM vision-judge. Batch into return exec summary.
- **META: plug-and-play verify-predicates** — `_PREDICATE_ORACLES` hardcoded kernel list (evidence_classifier.py:52) →
  every new predicate is a spine gate → VIOLATES "bring a verify-predicate — no kernel edits". World-declared metadata (stricter-only).
- **D178 near_object VLN predicate** · **D176 cmd_motion driver seam** · **D168 place-oracle harden** · **S8 retire legacy** ·
  **relational near(a,b)** · Stage gates S4/S5/S6/nav-FAR/strategy_params/explore-TARE/VLN-SysNav. New deps/interfaces/hw/sec here.
