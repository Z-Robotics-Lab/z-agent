"""D180 bare-REPL acceptance: a BYO model that CANNOT run must be surfaced clearly.

Drives the ACTUAL bare `vector-cli` REPL under a PTY (NO -p, NO flag) with an
ACTIONABLE NL command, using VECTOR_PROVIDER=openrouter + a model that fails
NON-recoverably. Expects the REPL to print `model unavailable: ...` (D180) instead
of silently degrading to legacy. Both cases are rejected PRE-generation => FREE (no
credit spent), so this verifies under the OpenRouter credit-exhaustion block.

  case 404 : VECTOR_MODEL=vector/does-not-exist-xyz  -> "No endpoints" (unknown id)
  case 402 : VECTOR_MODEL=google/gemini-3.5-flash    -> prompt > residual credit

Usage: python model_unavailable_accept.py <case:404|402>
"""
from __future__ import annotations

import os
import re
import sys
import time

import pexpect

ROOT = "/home/yusen/Desktop/zeno"
CASE = sys.argv[1] if len(sys.argv) > 1 else "404"
MODEL = {
    "400": "vector/does-not-exist-xyz",      # invalid model id
    "404": "google/gemini-2.0-flash-001",    # valid format, no endpoints
    "402": "google/gemini-3.5-flash",        # prompt exceeds residual credit
}[CASE]
# NL selects the route: a fetch (use_vgg) -> native producer (_repl_attempt_native,
# prints "model unavailable:"); a sim-start -> legacy tool_use (prints "Error: <msg>").
# BOTH must surface the clean ModelUnavailableError message. Override via argv[2].
NL = sys.argv[2] if len(sys.argv) > 2 else "把绿色的瓶子拿过来"

env = dict(os.environ)
env.update(
    VECTOR_PROVIDER="openrouter",
    VECTOR_MODEL=MODEL,
    VECTOR_NO_ROS2="1",
    VECTOR_REPL_NATIVE="1",  # ensure default native cutover is ON (the _repl_attempt_native path)
    TERM="xterm",
)
LOG = f"/tmp/model_unavail_{CASE}.log"
os.system(f"rm -f {LOG}")

print(f"[driver] case={CASE} model={MODEL!r} — spawning BARE vector-cli REPL (no flag)", flush=True)
child = pexpect.spawn(
    f"{ROOT}/.venv/bin/python", ["-m", "zeno.vcli.cli"],
    cwd=ROOT, env=env, encoding="utf-8", timeout=120, dimensions=(40, 160),
)
child.logfile = open(LOG, "w", encoding="utf-8")

try:
    child.expect(r"vector>", timeout=60)
    child.sendline(NL)
    # Wait for the turn to settle (quiet gap), then inspect the cleaned log.
    waited = 0.0
    while waited < 90:
        try:
            child.expect(r".+", timeout=3.0)
            waited = 0.0
        except pexpect.TIMEOUT:
            break
        except pexpect.EOF:
            break
        waited += 3.0
    child.sendline("/quit")
    time.sleep(1)
except Exception as e:  # noqa: BLE001
    print(f"[driver] pexpect error: {type(e).__name__}: {e}", flush=True)
finally:
    try:
        child.close(force=True)
    except Exception:  # noqa: BLE001
        pass

raw = open(LOG, encoding="utf-8", errors="replace").read()
clean = re.sub(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][0-9;]*|\x1b", "", raw)
clean = re.sub(r"[⠀-⣿]", "", clean)
# The clean, actionable message — surfaced with prefix "model unavailable:" (native
# catch) OR "Error:" (legacy handler). Assert the reason-scoped body, prefix-agnostic.
hit = re.search(r"Model '.*?' unavailable via .*", clean)
print("=" * 70, flush=True)
print(f"[result:{CASE}] 'model unavailable' line present: {bool(hit)}", flush=True)
if hit:
    print(f"[result:{CASE}] -> {hit.group(0).strip()[:200]}", flush=True)
else:
    # Show the tail so a miss is diagnosable (did it degrade to legacy silently?).
    print(f"[result:{CASE}] MISS — cleaned tail:\n{clean[-600:]}", flush=True)
sys.exit(0 if hit else 1)
