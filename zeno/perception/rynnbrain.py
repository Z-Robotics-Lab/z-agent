# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""RynnBrain embodied-VLM client — local perception oracle over HTTP.

RynnBrain (Alibaba DAMO, Qwen3.5 backbone) runs as a local service on the GPU
workstation (`start_rynn.sh`, model choice lives in the script). This client
speaks its JSON sidecar:

    POST {base_url}/infer   {"image": <base64 jpeg>, "text": str, "think": bool}
                            -> {"reply": str}
    GET  {base_url}/health  -> {"ok": true, "model": <name>}

Coordinates in replies are [0,1000]-normalized: ``<object>(x1,y1),(x2,y2)``
boxes, ``<affordance>(x,y)`` points. Parsing is a PURE function (hermetic
tests, no network).

Design notes (mirrors :mod:`zeno.perception.vlm_go2`):
- httpx (already a core dependency) with explicit timeouts; ONE retry on
  transport errors only; 4xx never retried.
- ``read_env("RYNNBRAIN_URL")`` — ZENO_ first, VECTOR_ fallback; default
  localhost:8786 (NUC deployments point it at the workstation LAN IP).
- PIL is imported lazily (Pillow lives in the [perception] extra) with a
  readable error when missing.
- The caller passes a raw (H, W, 3) uint8 RGB frame; encoding happens here.
"""

from __future__ import annotations

import base64
import logging
import re
from io import BytesIO
from typing import Any

import httpx

from zeno.vcli.env import read_env

logger = logging.getLogger(__name__)

_DEFAULT_URL = "http://127.0.0.1:8786"
_TIMEOUT_S = 20.0        # grounding (think off) measures ~1s on the 4090
_TIMEOUT_THINK_S = 45.0  # thinking-mode QA measures 5-8s
_JPEG_QUALITY = 85       # local LAN — keep detail for grounding, cost is moot
_MAX_DIM = 640

_BOX_RE = re.compile(
    r"\(\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)")
_POINT_RE = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")

_BOX_PROMPT = (
    "Find ONE {desc}; box exactly one object. Generate coordinates for one "
    "object bounding box. Constraints: x1,y1,x2,y2 ∈ [0,1000]. Response "
    "must be in the format: <object> (x1, y1), (x2, y2) </object>")

# Degenerate "full-frame" grounding (real-dog measurement, 2026-07-29): the 2B
# model answers groundings of ABSENT objects with one constant origin-anchored
# box spanning the model's full image width — (0,0),(~648,~290) on the 640x480
# D435i frame, identical for chair/keyboard/person/bottle/monitor over a scene
# containing none of them. Such a box carries no localization signal.
_DEGEN_AREA_FRAC = 0.85    # covers >= 85% of a frame reading
_DEGEN_ANCHOR_FRAC = 0.02  # "origin-anchored": x1,y1 within 2% of the frame
_DEGEN_SPAN_FRAC = 0.90    # "full width": x-span >= 90% of the frame width


def parse_boxes(reply: str) -> list[tuple[tuple[int, int], tuple[int, int]]]:
    """All ``(x1,y1),(x2,y2)`` box pairs in a reply ([0,1000] coords).

    Pure function: prose around the pairs is ignored; a lone point (no paired
    second corner) is NOT a box; malformed/empty replies give ``[]``.
    """
    if not reply:
        return []
    return [(((int(m.group(1))), int(m.group(2))),
             (int(m.group(3)), int(m.group(4))))
            for m in _BOX_RE.finditer(reply)]


def sent_size(width: int, height: int) -> tuple[int, int]:
    """(W, H) of the JPEG actually sent to the service (_encode_frame rule)."""
    if max(width, height) <= _MAX_DIM:
        return width, height
    scale = _MAX_DIM / max(width, height)
    return int(width * scale), int(height * scale)


def is_degenerate_box(
    box: tuple[tuple[int, int], tuple[int, int]],
    image_wh: tuple[int, int] | None = None,
) -> bool:
    """True when a grounding box is a full-frame refusal artifact.

    Checked under TWO coordinate readings, because the degenerate mode emits
    pixel coords of the model's input image while legit replies are
    [0,1000]-normalized: the nominal (1000, 1000) frame and ``image_wh`` (the
    sent JPEG size, see :func:`sent_size`). Degenerate iff, under either
    reading, the box covers >= 85% of the frame area OR is origin-anchored
    and spans >= 90% of the frame width. Reject-biased on purpose (this also
    rejects a legit origin-anchored full-width band): a false "not found"
    costs one re-query; a false bearing poisons every downstream decision.
    """
    (x1, y1), (x2, y2) = box
    frames = [(1000.0, 1000.0)]
    if image_wh is not None and image_wh[0] > 0 and image_wh[1] > 0:
        frames.append((float(image_wh[0]), float(image_wh[1])))
    for fw, fh in frames:
        span_x = min(float(x2), fw) - max(float(x1), 0.0)
        span_y = min(float(y2), fh) - max(float(y1), 0.0)
        if span_x <= 0 or span_y <= 0:
            continue
        if span_x * span_y >= _DEGEN_AREA_FRAC * fw * fh:
            return True
        if (x1 <= _DEGEN_ANCHOR_FRAC * fw and y1 <= _DEGEN_ANCHOR_FRAC * fh
                and span_x >= _DEGEN_SPAN_FRAC * fw):
            return True
    return False


def parse_points(reply: str) -> list[tuple[int, int]]:
    """All ``(x,y)`` pairs in a reply ([0,1000] coords) — affordance points."""
    if not reply:
        return []
    return [(int(m.group(1)), int(m.group(2)))
            for m in _POINT_RE.finditer(reply)]


class RynnBrainClient:
    """Thin, stateless-per-call HTTP client for the RynnBrain service."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or read_env("RYNNBRAIN_URL")
                         or _DEFAULT_URL).rstrip("/")

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def locate(self, frame: Any, description: str) -> str:
        """Ground ONE object description; returns the raw model reply.

        The caller parses boxes via :func:`parse_boxes` (kept separate so the
        raw reply stays available for honest error messages).
        """
        prompt = _BOX_PROMPT.format(desc=description)
        return self._infer(frame, prompt, think=False)

    def ask(self, frame: Any, question: str, think: bool = True) -> str:
        """Free-form scene QA (thinking mode by default — better answers)."""
        return self._infer(frame, question, think=think)

    def available(self) -> bool:
        """Best-effort health probe; never raises."""
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=3.0)
            return r.status_code == 200 and bool(r.json().get("ok"))
        except Exception:  # noqa: BLE001 — liveness probe, never raise
            return False

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _infer(self, frame: Any, text: str, think: bool) -> str:
        payload = {"image": self._encode_frame(frame), "text": text,
                   "think": think}
        timeout = _TIMEOUT_THINK_S if think else _TIMEOUT_S
        last_exc: Exception | None = None
        for attempt in (1, 2):  # one retry, transport errors only
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(f"{self.base_url}/infer",
                                           json=payload)
                if 400 <= response.status_code < 500:
                    raise RuntimeError(
                        f"RynnBrain client error {response.status_code}: "
                        f"{response.text[:200]}")
                response.raise_for_status()
                return str(response.json().get("reply", ""))
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                logger.warning("RynnBrain call failed (attempt %d/2): %s",
                               attempt, exc)
                last_exc = exc
        raise RuntimeError(
            f"RynnBrain service unreachable at {self.base_url} "
            f"(last error: {last_exc})")

    @staticmethod
    def _encode_frame(frame: Any) -> str:
        """(H, W, 3) uint8 RGB ndarray -> base64 JPEG string."""
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover — env guidance
            raise RuntimeError(
                "Pillow is required for perception "
                "(pip install -e '.[perception]')") from exc
        pil_image = Image.fromarray(frame)
        w, h = pil_image.size
        if sent_size(w, h) != (w, h):
            pil_image = pil_image.resize(sent_size(w, h), Image.LANCZOS)
        buf = BytesIO()
        pil_image.save(buf, format="JPEG", quality=_JPEG_QUALITY)
        return base64.b64encode(buf.getvalue()).decode("ascii")
