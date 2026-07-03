"""Perception-VLM billing-confound guards for the bare-REPL acceptance driver.

R230/E53 diagnosed the acceptance harness's weak link. The perception VLM
(look / describe_scene → vlm_go2.py) is a SEPARATE model seam from the planner brain.
When it hits an OpenRouter-402 credit exhaustion (the E28 block, still ACTIVE) the error
is caught upstream and the brain silently re-plans (perception_grasp → navigate → explore
→ look → 402 → …), so the bare REPL spins to NO verdict — indistinguishable from a hung
sim. That silent spin is very likely what made the R229/E52 warehouse run read 0/2, i.e.
recent breadth "refutations" are of UNKNOWN provenance.

Two guards make every future breadth verdict billing-confound-free. Both are PURE and
importable so ``repl_accept.py`` stays unit-testable (no sim, no network in the tests):

  1. ``resolve_local_vlm_env`` — when ``VECTOR_VLM_URL`` is unset, default the LOCAL Ollama
     route iff Ollama is up (probe ``/api/tags``); otherwise fail LOUD with the recipe.
     Never silently fall back to the 402-confounded OpenRouter perception route.
  2. ``detect_perception_402`` — scan the ANSI-stripped REPL stream for the perception-VLM
     4xx signature (unique to ``vlm_go2.py``) so the driver ABORTS with a distinct
     ``VLM-BILLING-402`` marker instead of a silent no-verdict spin.
"""
from __future__ import annotations

import os
import re
import shutil
import urllib.error
import urllib.request

# Local Ollama perception route (LESSONS recipe; gemma4:e4b resolves ordinals, R192/E28).
DEFAULT_LOCAL_VLM_URL: str = "http://localhost:11434/v1"
DEFAULT_LOCAL_VLM_MODEL: str = "gemma4:e4b"
_OLLAMA_TAGS_URL: str = "http://localhost:11434/api/tags"

# The distinct, greppable marker the driver prints when it aborts on a perception 402.
VLM_BILLING_402_MARKER: str = "VLM-BILLING-402"

# Signature is UNIQUE to the perception VLM: ``OpenRouter API client error <4xx>`` is raised
# ONLY by vector_os_nano/perception/vlm_go2.py:_call_vlm on a non-retried 4xx. The planner
# brain's own 402 uses a different string ("402 balance cap") and RECOVERS by downshifting
# max_tokens — it must never trip this. Any 4xx here is the same silent-spin confound.
_PERCEPTION_4XX_RE = re.compile(r"OpenRouter API client error 4\d\d")

_RECIPE = (
    "perception VLM is UNROUTED and Ollama is DOWN — refusing to run a billing-confounded "
    "acceptance (an OpenRouter-402 look/describe_scene fails silently → no-verdict spin, "
    "R230/E53). FIX one of:\n"
    f"  (a) start Ollama and `ollama pull {DEFAULT_LOCAL_VLM_MODEL}` "
    f"(then this driver auto-routes VECTOR_VLM_URL={DEFAULT_LOCAL_VLM_URL}); or\n"
    f"  (b) export VECTOR_VLM_URL={DEFAULT_LOCAL_VLM_URL} "
    f"VECTOR_VLM_MODEL={DEFAULT_LOCAL_VLM_MODEL} yourself; or\n"
    "  (c) export VECTOR_ALLOW_REMOTE_VLM=1 to KNOWINGLY use the OpenRouter perception "
    "route (only if that key has perception credit — else you get the silent 402 spin)."
)


class VLMConfoundError(RuntimeError):
    """Raised when perception is unrouted AND Ollama is down — the confounded configuration.

    Carries the actionable recipe as its message so the driver can fail loud verbatim.
    """


def detect_perception_402(stream_text: str) -> bool:
    """True iff the ANSI-stripped REPL ``stream_text`` shows a perception-VLM 4xx failure.

    Matches the look/describe_scene signature only; the planner brain's graceful,
    recoverable 402 ("402 balance cap") does NOT match.
    """
    return bool(_PERCEPTION_4XX_RE.search(stream_text))


def ollama_up(timeout: float = 3.0) -> bool:
    """Probe the local Ollama ``/api/tags`` endpoint. True iff it answers 200."""
    try:
        with urllib.request.urlopen(_OLLAMA_TAGS_URL, timeout=timeout) as resp:  # noqa: S310
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def resolve_local_vlm_env(environ, ollama_probe=ollama_up) -> dict[str, str]:
    """Return the VLM-route env vars to INJECT (empty dict = leave the caller's env as-is).

    - ``VECTOR_VLM_URL`` already set → respect the caller's explicit route (return {}).
    - ``VECTOR_ALLOW_REMOTE_VLM=1`` → caller knowingly accepts the OpenRouter route (return {}).
    - unset + Ollama up → default the local Ollama route.
    - unset + Ollama down → raise :class:`VLMConfoundError` (fail loud; never silent-spin).

    ``ollama_probe`` is injectable so the unit test runs offline.
    """
    if environ.get("VECTOR_VLM_URL"):
        return {}
    if environ.get("VECTOR_ALLOW_REMOTE_VLM") == "1":
        return {}
    if ollama_probe():
        return {
            "VECTOR_VLM_URL": DEFAULT_LOCAL_VLM_URL,
            "VECTOR_VLM_MODEL": DEFAULT_LOCAL_VLM_MODEL,
        }
    raise VLMConfoundError(_RECIPE)


JUDGE_FORCE_REMOTE_VAR: str = "VECTOR_JUDGE_FORCE_REMOTE"


def resolve_judge_env(environ, ollama_probe=ollama_up) -> dict[str, str]:
    """Return the VECTOR_JUDGE_* env vars to INJECT so the eyes second-witness (vision_judge)
    runs on the LOCAL Ollama VLM whenever Ollama is up — flipping the acceptance eyes
    self-read → vlm-judge (R271/E69). The judge is a SECONDARY witness (stricter-only,
    Invariant 1): it can only DOWNGRADE/flag a frame, never manufacture a PASS; any error abstains.

    PRECEDENCE (local-preferred, deliberately):
    - ``VECTOR_JUDGE_FORCE_REMOTE=1`` → respect the caller's remote judge untouched (return {}).
    - Ollama up → route the LOCAL gemma4:e4b judge, OVERRIDING any inherited remote judge env.
      This is intentional: the loop supervisor exports a stale ``VECTOR_JUDGE_MODEL=qwen3-vl-plus``
      whose DashScope key shares the ARREARED routing brain (dead), so honouring it would abstain
      forever and never flip the eyes. The local witness is zero-credit and always reachable.
    - Ollama down → return {} (leave the caller's env as-is: a configured funded remote judge is
      used if present, else vision_judge simply ABSTAINS). Fail-SOFT — a down witness must NEVER
      block or fabricate a verdict (UNLIKE perception, whose absence silent-spins); self-read floor.

    The judge model (gemma4:e4b, the perception seam) DIFFERS from the routing/planner brain
    (deepseek-v4-flash), so generator≠evaluator holds; the rubric is ORTHOGONAL (render /
    upright / intact / workspace-in-frame), never "did the task succeed". ``ollama_probe`` is
    injectable so the unit test runs offline.
    """
    if environ.get(JUDGE_FORCE_REMOTE_VAR) == "1":
        return {}
    if ollama_probe():
        return {
            "VECTOR_JUDGE_BASE_URL": DEFAULT_LOCAL_VLM_URL,
            "VECTOR_JUDGE_MODEL": DEFAULT_LOCAL_VLM_MODEL,
            "VECTOR_JUDGE_API_KEY": environ.get("VECTOR_JUDGE_API_KEY") or "ollama",
        }
    return {}


# The bare-REPL invocation the acceptance driver spawns. --native-loop only (the acceptance
# face is bare cli + NL: NO -p / --sim-go2). --verbose is a LOGGING-only flag (cli._setup_logging):
# it restores vector_os_nano.skills / .perception loggers to full output WITHOUT changing any
# behaviour (planner, perception, verify all run identically), so the face stays intact.
_BASE_REPL_ARGV: tuple[str, ...] = ("-m", "vector_os_nano.vcli.cli", "--native-loop")
TRACE_ENV_VAR: str = "VECTOR_ACCEPT_VERBOSE"


def repl_cli_argv(environ) -> list[str]:
    """Argv for the bare-REPL spawn; append ``--verbose`` iff ``VECTOR_ACCEPT_VERBOSE`` is truthy.

    R232/E54: R231's warehouse run read ``closest seen inf`` (perception found nothing at ALL
    scan headings) but the raw log carried ZERO ``[PGRASP]`` lines — the per-scan-heading
    detection trace is ``logger.info`` under ``vector_os_nano.skills`` / ``.perception``, which
    the non-verbose REPL pins to ERROR (cli._QUIET_LOGGERS). Setting this env makes a DEBUG round's
    single warehouse sim run DECISIVE: it captures arrival pose + per-heading detection counts, so
    we can tell framing (dog elsewhere) from detection (dog faces green, still None). Default off →
    every existing run is byte-identical to before.
    """
    argv = list(_BASE_REPL_ARGV)
    val = str(environ.get(TRACE_ENV_VAR, "")).strip().lower()
    if val and val not in ("0", "false", "no"):
        argv.append("--verbose")
    return argv


# --- Durable evidence persistence (R233/E54) ---------------------------------
# The driver writes eyes_*.png / verdict_*.png / repl.raw.log / session.log to a /tmp SNAP
# dir (fast). But AGENTS.md §State-files forbids /tmp for durable evidence, and a reboot
# wipes it — so the R229/R231 warehouse runs preserved only the hand-copied .log and LOST
# the eyes-on-sim FRAMES. That is why "closest seen inf" stayed unadjudicated: with a frame
# you SEE whether the dog is off-frame (H1/H4) or facing the green bottle yet blind (H2).
# These pure helpers let the driver copy every frame + log OUT to a durable, round-scoped
# dir at end-of-run, so the next warehouse sim window yields eyes, not just logs.
EVIDENCE_ENV_VAR: str = "VECTOR_EVIDENCE_DIR"
ROUND_ENV_VAR: str = "ROUND_N"
_EVIDENCE_SUFFIXES: tuple[str, ...] = (".png", ".log")


def resolve_evidence_dir(environ, repo_root: str) -> str | None:
    """Durable, non-/tmp destination for acceptance evidence, or ``None`` to skip.

    Priority: explicit ``VECTOR_EVIDENCE_DIR`` > ``<repo>/var/evidence/R<ROUND_N>`` when the
    supervisor set ``ROUND_N`` > ``None`` (interactive run with neither set — the driver then
    warns and leaves frames in SNAP). ``ROUND_N`` is R-space and may arrive bare (``233``) or
    prefixed (``R233``); normalise to the ``R233`` dir naming the ledger already uses.
    """
    explicit = str(environ.get(EVIDENCE_ENV_VAR, "")).strip()
    if explicit:
        return explicit
    rn = str(environ.get(ROUND_ENV_VAR, "")).strip()
    if rn:
        tag = rn if rn.upper().startswith("R") else f"R{rn}"
        return os.path.join(repo_root, "var", "evidence", tag)
    return None


def persist_evidence(snap: str, dest: str | None) -> list[str]:
    """Copy durable artifacts (frames + logs) out of the /tmp ``snap`` dir into ``dest``.

    Persists every ``*.png`` (eyes/verdict frames — the eyes-on-sim moat) and ``*.log`` file.
    Best-effort and idempotent: a per-file ``OSError`` is skipped (a persist glitch must never
    sink an acceptance that already ran), re-runs overwrite in place. Returns the sorted
    basenames persisted. ``dest`` falsy or ``snap`` missing → ``[]`` (no-op, no raise).
    """
    if not dest or not os.path.isdir(snap):
        return []
    os.makedirs(dest, exist_ok=True)
    persisted: list[str] = []
    for name in sorted(os.listdir(snap)):
        if not name.endswith(_EVIDENCE_SUFFIXES):
            continue
        try:
            shutil.copy2(os.path.join(snap, name), os.path.join(dest, name))
        except OSError:
            continue
        persisted.append(name)
    return persisted
