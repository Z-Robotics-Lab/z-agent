# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics
"""VisionJudge — the visual SECOND WITNESS for the honest acceptance gate (ADR-002).

Looks at a rendered frame and answers an ORTHOGONAL perceptual rubric — questions the deterministic
GT oracle is structurally blind to (is the robot upright vs floating, did the scene actually render
vs black, is the body intact, is the workspace in frame). It NEVER asks "did the task succeed" (the
oracle's job; re-asking re-imports VLM hallucination). It can only DOWNGRADE/flag — the gate
(``gate.py``) never lets a vision PASS override a GT fail.

FAIL-CLOSED: any 'no' -> FAIL; any 'abstain'/unparseable/API-down -> ABSTAIN (never PASS).
Non-replayable by design (live VLM API + model drift): the frame + prompt + model id + raw response
are an AUDIT artifact, never folded into the deterministic verdict.
"""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# The judge model MUST differ from the routing brain (generator != evaluator). Default gpt-4o.
_JUDGE_MODEL = os.environ.get("VECTOR_JUDGE_MODEL", "openai/gpt-4o")
_RUBRIC_PATH = Path(__file__).resolve().parents[2] / "config" / "visual_acceptance_rubric.yaml"
_TEMPORAL_RUBRIC_PATH = Path(__file__).resolve().parents[2] / "config" / "visual_temporal_rubric.yaml"

PASS = "PASS"
FAIL = "FAIL"
ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class VisionVerdict:
    """The witness verdict. ``witness`` is PASS | FAIL | ABSTAIN; per_item is ((key, ans, why), …)."""

    witness: str
    per_item: tuple
    reasoning: str
    model: str
    raw: str = ""


def _load_rubric_file(p: Path) -> list[dict]:
    import yaml

    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not items:
        raise ValueError(f"rubric has no items: {p}")
    return items


def load_rubric(path: str | os.PathLike | None = None) -> list[dict]:
    """Load the frozen single-frame rubric items. Fails LOUD on a missing/bad file."""
    return _load_rubric_file(Path(path) if path else _RUBRIC_PATH)


def load_temporal_rubric(path: str | os.PathLike | None = None) -> list[dict]:
    """Load the frozen TEMPORAL (montage) rubric items (ADR-002 Stage 3)."""
    return _load_rubric_file(Path(path) if path else _TEMPORAL_RUBRIC_PATH)


def _encode_full_res(image_path: str | os.PathLike) -> str:
    """Base64 JPEG at the frame's NATIVE resolution (NOT the 160px naming downscale — gripper/
    contact gaps and floating/clipping vanish at thumbnail size)."""
    import cv2

    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"unreadable frame: {image_path}")
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
    if not ok:
        raise ValueError("jpeg encode failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")


def _build_prompt(items: list[dict]) -> str:
    lines = [
        "You are a STRICT visual inspector of a single robotics-simulator frame. Answer ONLY about",
        "what is VISIBLE in the image. Do NOT judge whether any task succeeded. For EACH check answer",
        "exactly 'yes', 'no', or 'abstain' (use 'abstain' if the image is unclear or you are unsure),",
        "with a one-sentence justification.",
        'Return ONLY a JSON object: {"items": {"<key>": {"answer": "yes|no|abstain", "why": "..."}}}.',
        "Checks:",
    ]
    for it in items:
        lines.append(f'- {it["key"]}: {" ".join(str(it["question"]).split())}')
    return "\n".join(lines)


def _call_vlm(image_b64: str, prompt: str, *, model: str, api_key: str | None, timeout: float = 60.0) -> str:
    """POST one image+prompt to OpenRouter chat/completions; return the raw text content."""
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
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(f"{_OPENROUTER_BASE_URL}/chat/completions", json=payload, headers=headers)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"].get("content", "") or ""


def _parse(raw: str, items: list[dict]) -> tuple:
    """Extract per-item (key, answer, why); any missing/invalid answer -> 'abstain' (fail-closed)."""
    parsed: dict = {}
    m = re.search(r"\{.*\}", raw or "", re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            if isinstance(obj, dict):
                parsed = obj.get("items", obj)
        except Exception:  # noqa: BLE001
            parsed = {}
    results = []
    for it in items:
        k = it["key"]
        node = parsed.get(k, {}) if isinstance(parsed, dict) else {}
        if isinstance(node, dict):
            ans = str(node.get("answer", "abstain")).strip().lower()
            why = str(node.get("why", ""))
        else:
            ans, why = "abstain", ""
        if ans not in ("yes", "no", "abstain"):
            ans = "abstain"
        results.append((k, ans, why))
    return tuple(results)


def _fold(per_item: tuple) -> str:
    """FAIL-CLOSED fold: any 'no' -> FAIL; any 'abstain' (or empty) -> ABSTAIN; all 'yes' -> PASS."""
    answers = [a for _, a, _ in per_item]
    if not answers:
        return ABSTAIN
    if any(a == "no" for a in answers):
        return FAIL
    if any(a == "abstain" for a in answers):
        return ABSTAIN
    return PASS


def judge(
    image_path: str | os.PathLike,
    *,
    items: list[dict] | None = None,
    model: str | None = None,
    api_key: str | None = None,
    call=None,
) -> VisionVerdict:
    """Grade ``image_path`` against the rubric via the judge VLM. ``call`` is injectable for tests.

    Returns a VisionVerdict; on ANY failure (encode / API / network) returns ABSTAIN, never PASS.
    """
    items = items if items is not None else load_rubric()
    model = model or _JUDGE_MODEL
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    call = call or _call_vlm
    try:
        b64 = _encode_full_res(image_path)
        prompt = _build_prompt(items)
        raw = call(b64, prompt, model=model, api_key=api_key)
    except Exception as exc:  # noqa: BLE001 — fail-closed: never a PASS on error
        return VisionVerdict(witness=ABSTAIN, per_item=(), reasoning=f"judge unavailable: {exc}", model=model)
    per = _parse(raw, items)
    reasoning = "; ".join(f"{k}={a}" for k, a, _ in per)
    return VisionVerdict(witness=_fold(per), per_item=per, reasoning=reasoning, model=model, raw=raw)


def _build_temporal_prompt(items: list[dict]) -> str:
    lines = [
        "You are a STRICT inspector of a MONTAGE of ordered robotics-simulator frames. Read them",
        "left-to-right then top-to-bottom = EARLIER to LATER in time. Judge the robot's MOTION ACROSS",
        "the frames. Do NOT judge whether any task succeeded. For EACH check answer exactly 'yes',",
        "'no', or 'abstain' (abstain if unclear), with a one-sentence justification.",
        'Return ONLY a JSON object: {"items": {"<key>": {"answer": "yes|no|abstain", "why": "..."}}}.',
        "Checks:",
    ]
    for it in items:
        lines.append(f'- {it["key"]}: {" ".join(str(it["question"]).split())}')
    return "\n".join(lines)


def judge_temporal(montage_path, *, items=None, model=None, api_key=None, call=None) -> VisionVerdict:
    """Grade a MONTAGE of ordered frames against the temporal rubric (ADR-002 Stage 3 — the SOFT
    motion narrator). Same fail-closed contract as ``judge``; never PASS on error."""
    items = items if items is not None else load_temporal_rubric()
    model = model or _JUDGE_MODEL
    api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
    call = call or _call_vlm
    try:
        b64 = _encode_full_res(montage_path)
        raw = call(b64, _build_temporal_prompt(items), model=model, api_key=api_key)
    except Exception as exc:  # noqa: BLE001 — fail-closed: never a PASS on error
        return VisionVerdict(witness=ABSTAIN, per_item=(), reasoning=f"judge unavailable: {exc}", model=model)
    per = _parse(raw, items)
    reasoning = "; ".join(f"{k}={a}" for k, a, _ in per)
    return VisionVerdict(witness=_fold(per), per_item=per, reasoning=reasoning, model=model, raw=raw)
