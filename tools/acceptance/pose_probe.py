# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""pose_probe — isolate the POSE-discrimination question from the 4-item frozen rubric.

E104 (R314) refuted qwen2.5vl:7b as an eyes 2nd-witness: on a CLEARLY-toppled go2 it still
answered the frozen rubric's `robot_present_upright` item YES (a deterministic false-green). But
that item rides inside a 4-question list whose framing ("Is a quadruped visible, resting or
standing ON the floor...") leads with PRESENCE. This probe asks ONE isolated, forced-choice pose
question per frame, so we can tell whether the rubber-stamp is (a) a genuine pose-blindness of the
model, or (b) an artifact of the rubric framing. If (b), a reworded rubric item is a GATED (moat)
proposal, not a model swap.

Framing matters (R315/E106): minicpm-v collapses to FALLEN-both under the FAULT-primed prompt
(safety-inspector "checking for a fall") but DISCRIMINATES pose under a NEUTRAL STANDING/LYING
prompt. `--framing fault` (default, preserves E105 reproducibility) vs `--framing neutral`.

NOT a spine file (tools/, read-only local ollama, no billing, does NOT touch config/*rubric*.yaml).
Usage:
    python tools/acceptance/pose_probe.py [--framing fault|neutral] <model> <N> <frame1> [frame2 ...]
"""
from __future__ import annotations

import base64
import collections
import json
import re
import sys

import httpx

LOCAL_URL = "http://localhost:11434/v1/chat/completions"
_CALL_TIMEOUT_S = 240.0

# FAULT-primed forced-choice (E104/E105 framing): leads with "checking for a fall". Kept as the
# default so E105's qwen-pose-blind result stays reproducible byte-for-byte.
_PROMPT_FAULT = (
    "You are a safety inspector checking a four-legged (quadruped) robot for a fall. "
    "Look only at the robot's body pose. Is the robot STANDING upright on its four feet on "
    "the floor, or has it FALLEN OVER onto its side or back with its legs pointing sideways? "
    "Answer with EXACTLY one word on the first line: UPRIGHT or FALLEN."
)
# NEUTRAL forced-choice (E106 framing): no fall/safety-inspector priming, symmetric options.
# This is the framing under which minicpm-v actually discriminates pose (E106).
_PROMPT_NEUTRAL = (
    "Look at the four-legged (quadruped) robot in this image and report its body posture. "
    "Is the robot STANDING on its four legs, or LYING down on the ground? "
    "Answer with EXACTLY one word on the first line: STANDING or LYING."
)
_PROMPTS = {"fault": _PROMPT_FAULT, "neutral": _PROMPT_NEUTRAL}


def _prompt_for(framing: str) -> str:
    """Select the probe prompt; unknown framing fails loud (never a silent default)."""
    try:
        return _PROMPTS[framing]
    except KeyError:
        raise ValueError(f"unknown framing {framing!r}; expected one of {sorted(_PROMPTS)}")


def _b64(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _call(image_b64: str, *, model: str, prompt: str) -> str:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }
        ],
        "max_tokens": 200,
        "temperature": 0,
        "keep_alive": "15m",
    }
    with httpx.Client(timeout=_CALL_TIMEOUT_S) as client:
        resp = client.post(LOCAL_URL, json=payload,
                           headers={"Content-Type": "application/json", "Authorization": "Bearer ollama"})
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"].get("content", "") or ""


def _classify(text: str) -> str:
    """Map raw output to UPRIGHT | FALLEN | UNPARSEABLE (first decisive token wins).

    Parses BOTH vocabularies: the fault prompt's UPRIGHT/FALLEN and the neutral prompt's
    STANDING/LYING (STANDING->UPRIGHT, LYING/FALLEN->FALLEN).
    """
    m = re.search(r"\b(UPRIGHT|STANDING|FALLEN|LYING)\b", text.upper())
    if not m:
        return "UNPARSEABLE"
    tok = m.group(1)
    return "FALLEN" if tok in ("FALLEN", "LYING") else "UPRIGHT"


def probe(model: str, n: int, frames: list[str], framing: str = "fault") -> list[dict]:
    prompt = _prompt_for(framing)
    out = []
    for frame in frames:
        b64 = _b64(frame)
        answers = []
        for i in range(n):
            raw = _call(b64, model=model, prompt=prompt)
            cls = _classify(raw)
            answers.append(cls)
            first = raw.strip().splitlines()[0][:80] if raw.strip() else "(empty)"
            print(f"  [{model}/{framing}] {frame} run {i+1}/{n}: {cls}  <- {first!r}", flush=True)
        out.append({"frame": frame, "framing": framing, "answers": answers,
                    "dist": dict(collections.Counter(answers))})
    return out


def main() -> int:
    argv = sys.argv[1:]
    framing = "fault"
    if argv and argv[0] == "--framing":
        if len(argv) < 2:
            print(__doc__)
            return 2
        framing = argv[1]
        argv = argv[2:]
    if len(argv) < 3:
        print(__doc__)
        return 2
    model = argv[0]
    n = int(argv[1])
    frames = argv[2:]
    print(f"== pose_probe {model} x{n} framing={framing} on {len(frames)} frame(s) ==", flush=True)
    results = probe(model, n, frames, framing=framing)
    print("\nSUMMARY:")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
