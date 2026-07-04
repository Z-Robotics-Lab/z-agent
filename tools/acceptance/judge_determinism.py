# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""judge_determinism — measure the run-to-run STABILITY of a local VLM vision judge.

The frontier lever (E72/E92/E102): the shipped local judge gemma4:e4b is a RECORDED-not-TRUSTED
second witness because it returns PASS<->ABSTAIN<->FAIL run-to-run on the SAME clear frame at
temperature=0. A TRUSTED discriminator needs a model that answers the frozen rubric
DETERMINISTICALLY. This probe runs `vision_judge.judge` N times on ONE fixed frame per model and
reports the witness distribution + per-item flip count, so a stronger candidate (e.g. qwen2.5vl:7b,
wired via VECTOR_JUDGE_LOCAL_MODEL — R312) can be compared apples-to-apples against gemma4:e4b.

NOT a spine file (lives in tools/, imports the frozen judge read-only). NON-network beyond the
LOCAL ollama endpoint; no billing. Usage:
    python tools/acceptance/judge_determinism.py <frame.png> <model[,model2,...]> [N]
"""
from __future__ import annotations

import collections
import json
import sys

from vector_os_nano.acceptance import vision_judge

LOCAL_URL = "http://localhost:11434/v1"
# Local 7B/9B VLMs are SLOW (cold load 77-93s; a full-res image inference 20-60s) — the frozen
# judge's default 60s httpx timeout spuriously ABSTAINs. Give the local probe a generous ceiling
# and pin the model resident so a mid-probe switch doesn't cold-reload every call.
_CALL_TIMEOUT_S: float = 240.0


def _local_call(image_b64: str, prompt: str, *, model: str, api_key, timeout: float = _CALL_TIMEOUT_S) -> str:
    import httpx

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                ],
            }
        ],
        "max_tokens": 700,
        "temperature": 0,
        "keep_alive": "10m",
    }
    with httpx.Client(timeout=_CALL_TIMEOUT_S) as client:
        resp = client.post(f"{LOCAL_URL}/chat/completions", json=payload,
                           headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"].get("content", "") or ""


def probe(frame: str, model: str, n: int) -> dict:
    """Run the frozen rubric judge n times on frame via the LOCAL ollama endpoint for `model`."""
    witnesses: list[str] = []
    per_item_answers: dict[str, list[str]] = collections.defaultdict(list)
    for i in range(n):
        v = vision_judge.judge(frame, model=model, api_key="ollama", call=_local_call)
        witnesses.append(v.witness)
        for k, a, _why in v.per_item:
            per_item_answers[k].append(a)
        print(f"  [{model}] run {i + 1}/{n}: witness={v.witness}  ({v.reasoning})", flush=True)
    dist = dict(collections.Counter(witnesses))
    flips = {k: len(set(ans)) for k, ans in per_item_answers.items()}
    deterministic = len(dist) == 1 and all(f == 1 for f in flips.values())
    return {
        "model": model,
        "n": n,
        "witness_dist": dist,
        "per_item_distinct_answers": flips,
        "deterministic": deterministic,
    }


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    frame = sys.argv[1]
    models = sys.argv[2].split(",")
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    results = []
    for m in models:
        print(f"== probing {m} x{n} on {frame} ==", flush=True)
        results.append(probe(frame, m.strip(), n))
    print("\nSUMMARY:")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
