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
    detect_perception_402,
    repl_cli_argv,
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
