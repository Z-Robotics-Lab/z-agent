"""Unit tests for the perception-VLM billing-confound guard (R231/E54).

R230/E53 found the acceptance harness's weak link: the perception VLM
(look / describe_scene, vlm_go2.py) hits an OpenRouter-402 credit exhaustion that
fails SILENTLY mid-turn — the bare REPL spins to no verdict, indistinguishable from a
hung sim. Two pure guards make every future breadth verdict billing-confound-free:

  1. resolve_local_vlm_env — default the LOCAL Ollama route when VECTOR_VLM_URL is
     unset and Ollama is up; else fail LOUD (never silently fall back to the confounded
     OpenRouter perception route).
  2. detect_perception_402 — spot the perception-VLM 402 signature in the ANSI-stripped
     REPL stream so the driver ABORTS with a distinct VLM-BILLING-402 marker.

Pure/offline: no sim, no network — the canned stream is the real R229 signature.
"""
from __future__ import annotations

import pytest

from tools.acceptance.vlm_guard import (
    DEFAULT_LOCAL_VLM_MODEL,
    DEFAULT_LOCAL_VLM_URL,
    TRACE_ENV_VAR,
    VLM_BILLING_402_MARKER,
    VLMConfoundError,
    budget_timeout,
    detect_perception_402,
    repl_cli_argv,
    resolve_judge_env,
    resolve_local_vlm_env,
)

# The REAL perception-402 line captured from var/evidence/R229/fetch_wh_run1.repl.raw.log,
# ANSI/spinner already stripped (this is what _clean_log yields to the detector).
CANNED_402_STREAM = (
    "native look\n"
    "ERROR:vector_os_nano.skills.go2.look:[LOOK] VLM call failed: "
    'OpenRouter API client error 402: {"error":{"message":"This request requires more '
    'credits, or fewer max_tokens. You requested up to 65536 tokens, but can only afford '
    '582.","code":402}}\n'
)

DESCRIBE_SCENE_402 = (
    "[DESCRIBE_SCENE] VLM call failed: OpenRouter API client error 402: insufficient credit"
)

# The PLANNER brain's graceful 402 (openai_compat) — a DIFFERENT string that recovers by
# downshifting max_tokens. It must NEVER trigger the perception abort.
PLANNER_402_STREAM = "WARNING:...:402 balance cap: max_tokens 8000 unaffordable, retrying at 582"


class TestDetectPerception402:
    def test_look_402_detected(self) -> None:
        assert detect_perception_402(CANNED_402_STREAM) is True

    def test_describe_scene_402_detected(self) -> None:
        assert detect_perception_402(DESCRIBE_SCENE_402) is True

    def test_planner_graceful_402_not_flagged(self) -> None:
        # The planner's recoverable 402 must not abort acceptance.
        assert detect_perception_402(PLANNER_402_STREAM) is False

    def test_clean_grounded_stream_not_flagged(self) -> None:
        assert detect_perception_402("native perception_grasp ... verified=True (1/1 grounded)") is False

    def test_empty_stream(self) -> None:
        assert detect_perception_402("") is False

    def test_marker_is_distinct(self) -> None:
        # The abort marker must be greppable and unmistakable.
        assert VLM_BILLING_402_MARKER == "VLM-BILLING-402"


class TestResolveLocalVlmEnv:
    def test_defaults_local_route_when_unset_and_ollama_up(self) -> None:
        out = resolve_local_vlm_env({}, ollama_probe=lambda: True)
        assert out["VECTOR_VLM_URL"] == DEFAULT_LOCAL_VLM_URL
        assert out["VECTOR_VLM_MODEL"] == DEFAULT_LOCAL_VLM_MODEL

    def test_fail_loud_when_unset_and_ollama_down(self) -> None:
        with pytest.raises(VLMConfoundError) as ei:
            resolve_local_vlm_env({}, ollama_probe=lambda: False)
        # The recipe must be actionable (name the env var + how to bring Ollama up).
        assert "VECTOR_VLM_URL" in str(ei.value)
        assert "ollama" in str(ei.value).lower()

    def test_respects_explicit_url(self) -> None:
        # A caller who already routed perception (local or a funded remote) is untouched.
        env = {"VECTOR_VLM_URL": "http://elsewhere:1234/v1"}
        out = resolve_local_vlm_env(env, ollama_probe=lambda: False)
        assert out == {}

    def test_explicit_remote_optout_when_ollama_down(self) -> None:
        # VECTOR_ALLOW_REMOTE_VLM=1 = knowingly accept the OpenRouter perception route.
        out = resolve_local_vlm_env(
            {"VECTOR_ALLOW_REMOTE_VLM": "1"}, ollama_probe=lambda: False
        )
        assert out == {}


class TestResolveJudgeEnv:
    """R271/E69: the eyes second-witness (vision_judge) auto-routes to the LOCAL gemma4:e4b so
    the acceptance eyes flip self-read → vlm-judge. Stricter-only + fail-SOFT (a down judge
    abstains, never blocks — UNLIKE perception's fail-loud)."""

    def test_defaults_local_judge_when_unset_and_ollama_up(self) -> None:
        out = resolve_judge_env({}, ollama_probe=lambda: True)
        assert out["VECTOR_JUDGE_BASE_URL"] == DEFAULT_LOCAL_VLM_URL
        assert out["VECTOR_JUDGE_MODEL"] == DEFAULT_LOCAL_VLM_MODEL
        assert out["VECTOR_JUDGE_API_KEY"]  # non-empty (ollama ignores it, httpx wants a value)

    def test_fail_SOFT_when_unset_and_ollama_down(self) -> None:
        # A down judge must NOT raise (it is a secondary witness) — it returns {} so the caller
        # leaves VECTOR_JUDGE_* unset and vision_judge.judge() abstains. Self-read stays the floor.
        assert resolve_judge_env({}, ollama_probe=lambda: False) == {}

    def test_local_overrides_stale_inherited_remote_judge(self) -> None:
        # The loop supervisor exports a stale VECTOR_JUDGE_MODEL=qwen3-vl-plus (arreared key).
        # Local-preferred: Ollama up must OVERRIDE it so the eyes actually flip to vlm-judge,
        # not abstain forever against a dead remote.
        env = {"VECTOR_JUDGE_MODEL": "qwen3-vl-plus",
               "VECTOR_JUDGE_BASE_URL": "https://dashscope.aliyuncs.com/compatible-mode/v1"}
        out = resolve_judge_env(env, ollama_probe=lambda: True)
        assert out["VECTOR_JUDGE_MODEL"] == DEFAULT_LOCAL_VLM_MODEL
        assert out["VECTOR_JUDGE_BASE_URL"] == DEFAULT_LOCAL_VLM_URL

    def test_force_remote_opts_out_of_local(self) -> None:
        # A caller who KNOWINGLY wants a funded remote judge sets FORCE_REMOTE=1 → untouched.
        env = {"VECTOR_JUDGE_FORCE_REMOTE": "1", "VECTOR_JUDGE_MODEL": "openai/gpt-4o"}
        assert resolve_judge_env(env, ollama_probe=lambda: True) == {}

    def test_ollama_down_leaves_remote_judge_intact(self) -> None:
        # Ollama down → {} so a configured funded remote judge (or abstain) stands; no raise.
        env = {"VECTOR_JUDGE_MODEL": "openai/gpt-4o"}
        assert resolve_judge_env(env, ollama_probe=lambda: False) == {}

    def test_preserves_caller_api_key(self) -> None:
        out = resolve_judge_env({"VECTOR_JUDGE_API_KEY": "sk-live"}, ollama_probe=lambda: True)
        assert out["VECTOR_JUDGE_API_KEY"] == "sk-live"
        assert out["VECTOR_JUDGE_MODEL"] == DEFAULT_LOCAL_VLM_MODEL

    def test_local_model_overridable_via_distinct_var(self) -> None:
        # A caller can point the LOCAL judge at a STRONGER ollama VLM (a candidate trusted 2nd
        # discriminator — gemma4:e4b is non-deterministic PASS<->ABSTAIN<->FAIL, E72/E102) via
        # VECTOR_JUDGE_LOCAL_MODEL. Default (unset) stays gemma4:e4b for byte-compatibility.
        out = resolve_judge_env({"VECTOR_JUDGE_LOCAL_MODEL": "qwen2.5vl:7b"},
                                ollama_probe=lambda: True)
        assert out["VECTOR_JUDGE_MODEL"] == "qwen2.5vl:7b"
        assert out["VECTOR_JUDGE_BASE_URL"] == DEFAULT_LOCAL_VLM_URL

    def test_local_model_var_is_distinct_from_stale_remote_model(self) -> None:
        # VECTOR_JUDGE_MODEL is the STALE remote the local route deliberately overrides (arreared
        # qwen3-vl-plus); it must NEVER become the local model. VECTOR_JUDGE_LOCAL_MODEL is the
        # ONLY local-model knob, so the two never conflict.
        env = {"VECTOR_JUDGE_MODEL": "qwen3-vl-plus",
               "VECTOR_JUDGE_LOCAL_MODEL": "qwen2.5vl:7b"}
        out = resolve_judge_env(env, ollama_probe=lambda: True)
        assert out["VECTOR_JUDGE_MODEL"] == "qwen2.5vl:7b"


class TestReplCliArgv:
    """R232/E54: --verbose trace toggle so a DEBUG round's warehouse run captures [PGRASP]."""

    def test_default_is_bare_native_loop(self) -> None:
        # No env → byte-identical to the historical spawn (no --verbose leaks in).
        assert repl_cli_argv({}) == ["-m", "vector_os_nano.vcli.cli", "--native-loop"]

    def test_verbose_appended_when_flag_set(self) -> None:
        argv = repl_cli_argv({TRACE_ENV_VAR: "1"})
        assert argv[-1] == "--verbose"
        # base invocation preserved (acceptance face: --native-loop, no -p/--sim-go2)
        assert argv[:3] == ["-m", "vector_os_nano.vcli.cli", "--native-loop"]

    def test_falsey_values_do_not_enable(self) -> None:
        for falsey in ("0", "false", "no", "", "  "):
            assert "--verbose" not in repl_cli_argv({TRACE_ENV_VAR: falsey}), falsey

    def test_truthy_variants_enable(self) -> None:
        for truthy in ("1", "true", "yes", "TRUE", "on"):
            assert "--verbose" in repl_cli_argv({TRACE_ENV_VAR: truthy}), truthy

    def test_never_injects_p_or_sim_flags(self) -> None:
        # Guard the acceptance-face invariant: the trace toggle must not add a behaviour flag.
        argv = repl_cli_argv({TRACE_ENV_VAR: "1"})
        assert "-p" not in argv and "--sim-go2" not in argv


# --- Evidence persistence (R233/E54) -----------------------------------------
# The acceptance driver writes eyes_*.png / verdict_*.png / repl.raw.log into a /tmp SNAP
# dir (fast, but AGENTS.md forbids /tmp for durable evidence and a reboot wipes it). The
# R229/R231 warehouse runs preserved only the .log — the eyes-on-sim FRAMES were lost, so
# "closest seen inf" could not be adjudicated visually (off-frame vs blind-detector). These
# guards make the driver copy every frame + log OUT to a durable, round-scoped dir.
from tools.acceptance.vlm_guard import (  # noqa: E402
    EVIDENCE_ENV_VAR,
    ROUND_ENV_VAR,
    persist_evidence,
    resolve_evidence_dir,
)


class TestResolveEvidenceDir:
    def test_explicit_dir_wins(self) -> None:
        env = {EVIDENCE_ENV_VAR: "/data/ev", ROUND_ENV_VAR: "233"}
        assert resolve_evidence_dir(env, "/repo") == "/data/ev"

    def test_round_number_normalized_to_R_tag(self) -> None:
        assert resolve_evidence_dir({ROUND_ENV_VAR: "233"}, "/repo") == "/repo/var/evidence/R233"

    def test_round_already_R_prefixed(self) -> None:
        assert resolve_evidence_dir({ROUND_ENV_VAR: "R233"}, "/repo") == "/repo/var/evidence/R233"

    def test_none_when_unresolvable(self) -> None:
        # No ROUND_N and no explicit dir → None (driver leaves frames in SNAP, warns loud).
        assert resolve_evidence_dir({}, "/repo") is None

    def test_never_tmp(self) -> None:
        # AGENTS.md: durable evidence never lives under /tmp.
        dest = resolve_evidence_dir({ROUND_ENV_VAR: "9"}, "/home/u/repo")
        assert dest is not None and not dest.startswith("/tmp")


class TestPersistEvidence:
    def _seed(self, snap):
        (snap / "eyes_fetch.png").write_bytes(b"\x89PNG frame")
        (snap / "verdict_1.png").write_bytes(b"\x89PNG verdict")
        (snap / "repl.raw.log").write_text("trace")
        (snap / "session.log").write_text("session")
        (snap / "scratch.txt").write_text("ignore me")  # non-evidence suffix

    def test_copies_frames_and_logs_not_other(self, tmp_path) -> None:
        snap = tmp_path / "snap"; snap.mkdir(); self._seed(snap)
        dest = tmp_path / "ev" / "R233"
        got = persist_evidence(str(snap), str(dest))
        assert got == ["eyes_fetch.png", "repl.raw.log", "session.log", "verdict_1.png"]
        assert (dest / "eyes_fetch.png").read_bytes() == b"\x89PNG frame"
        assert not (dest / "scratch.txt").exists()

    def test_noop_on_falsy_dest(self, tmp_path) -> None:
        snap = tmp_path / "snap"; snap.mkdir(); self._seed(snap)
        assert persist_evidence(str(snap), None) == []
        assert persist_evidence(str(snap), "") == []

    def test_noop_on_missing_snap(self, tmp_path) -> None:
        assert persist_evidence(str(tmp_path / "nope"), str(tmp_path / "ev")) == []

    def test_idempotent(self, tmp_path) -> None:
        snap = tmp_path / "snap"; snap.mkdir(); self._seed(snap)
        dest = tmp_path / "ev"
        first = persist_evidence(str(snap), str(dest))
        second = persist_evidence(str(snap), str(dest))  # re-run must not raise / duplicate
        assert first == second


class TestBudgetTimeout:
    """Round-deadline-aware clamp on the harness's long per-turn expect() timeouts (R296/E87).

    Root cause of the R294->R296 breakage: repl_accept's quantity path waits ``timeout=600``s
    (x2) blind to ROUND_DEADLINE_EPOCH. A brain thrash that never emits ``grounded)`` runs the
    FULL wait; when the round deadline lands mid-wait the supervisor moves on but the harness
    keeps waiting under its own systemd scope, ORPHANING the vcli+MuJoCo sim into the next round
    (observed: ~11min leaked sim -> next round's sim-live warning + stale-BOARD quarantine).
    Clamping the wait to ``deadline - margin`` guarantees the harness reaches its ``finally``
    teardown BEFORE the round ends. Pure/offline — ``now``/``deadline`` are injected ints.
    """

    def test_no_deadline_passes_default_through(self) -> None:
        # Interactive run (no supervisor): byte-compatible with the historical fixed timeout.
        assert budget_timeout(600, now=1000, deadline_epoch=0) == 600
        assert budget_timeout(600, now=1000, deadline_epoch=None) == 600

    def test_ample_budget_keeps_default(self) -> None:
        # Deadline an hour out: min(default, remaining-margin) == default.
        assert budget_timeout(600, now=1000, deadline_epoch=1000 + 3600) == 600

    def test_tight_budget_clamps_below_default(self) -> None:
        # 200s to deadline, 120s margin -> 80s budget < 600 default.
        assert budget_timeout(600, now=1000, deadline_epoch=1000 + 200, margin=120) == 80

    def test_past_deadline_returns_floor_not_negative(self) -> None:
        # Already past (deadline-margin): never a zero/negative expect; fail fast at the floor.
        assert budget_timeout(600, now=1000, deadline_epoch=1000 + 30, margin=120, floor=15) == 15
        assert budget_timeout(600, now=2000, deadline_epoch=1000, margin=120, floor=15) == 15

    def test_floor_is_respected_at_the_boundary(self) -> None:
        # remaining-margin exactly == floor -> floor (>= floor branch), and one below -> floor.
        assert budget_timeout(600, now=1000, deadline_epoch=1135, margin=120, floor=15) == 15
        assert budget_timeout(600, now=1000, deadline_epoch=1134, margin=120, floor=15) == 15

    def test_never_exceeds_default_even_with_huge_budget(self) -> None:
        assert budget_timeout(300, now=0, deadline_epoch=10**9) == 300
