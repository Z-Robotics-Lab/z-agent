# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""GroundingDinoDetector — query->prompt mapping (pure) + a REAL-weights probe test.

The prompt-mapping tests are pure (no torch). The integration test loads the REAL
cached grounding-dino-tiny and runs it on the saved d435 probe frame
(/tmp/probe_d435.png — the red/green/blue cylinders). It is GATED on the weights +
frame being present so CI without them stays green, but it actually RUNS on this box.
"""
from __future__ import annotations

import os

import numpy as np
import pytest

from vector_os_nano.perception.grounding_dino import (
    GroundingDinoDetector,
    get_shared_detector,
    query_to_prompt,
)

_PROBE = "/tmp/probe_d435.png"
_HF_CACHE = os.path.expanduser(
    "~/.cache/huggingface/hub/models--IDEA-Research--grounding-dino-tiny"
)


def _torch_available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        return False
    return True


# --- pure prompt mapping (no torch) -----------------------------------------


def test_zh_noun_maps_to_english_phrase():
    assert query_to_prompt("拿起那个罐子") == "a can."
    assert query_to_prompt("抓瓶子") == "a bottle."
    assert query_to_prompt("杯子") == "a cup."


def test_english_query_becomes_lowercase_period_phrase():
    assert query_to_prompt("the can") == "a the can."
    assert query_to_prompt("RED CUP") == "a red cup."
    # punctuation stripped, trailing period guaranteed
    assert query_to_prompt("bottle!").endswith(".")
    assert "!" not in query_to_prompt("bottle!")


def test_empty_or_generic_query_falls_back_to_generic_prompt():
    assert query_to_prompt("") == "a can. a bottle. a cylinder."
    assert query_to_prompt(None) == "a can. a bottle. a cylinder."


def test_shared_singleton_is_same_instance():
    a = get_shared_detector()
    b = get_shared_detector()
    assert a is b
    assert isinstance(a, GroundingDinoDetector)


def test_detect_rejects_non_image_without_loading_model():
    # ValueError is raised BEFORE _ensure_loaded (no torch needed).
    det = GroundingDinoDetector()
    with pytest.raises(ValueError):
        det.detect(None, "a can.")  # type: ignore[arg-type]
    assert det._model is None  # model was never loaded


# --- REAL-weights integration (gated, but runs on this box) -----------------


@pytest.mark.integration
@pytest.mark.skipif(
    not os.path.exists(_PROBE), reason="probe frame /tmp/probe_d435.png absent"
)
@pytest.mark.skipif(
    not os.path.isdir(_HF_CACHE), reason="grounding-dino-tiny weights not cached"
)
@pytest.mark.skipif(not _torch_available(), reason="torch/transformers not installed")
def test_real_detector_localizes_cylinders_on_probe_frame():
    """REAL grounding-dino on the saved probe frame returns plausible can/bottle boxes."""
    from PIL import Image

    rgb = np.array(Image.open(_PROBE).convert("RGB"))
    assert rgb.shape[2] == 3

    det = GroundingDinoDetector()
    detections = det.detect(rgb, "the can")

    assert detections, "detector found nothing on the probe frame"
    # sorted by score descending
    scores = [d.confidence for d in detections]
    assert scores == sorted(scores, reverse=True)
    # boxes are pixel-space xyxy inside the 320x240 frame
    h, w = rgb.shape[:2]
    for d in detections:
        x1, y1, x2, y2 = d.bbox
        assert 0.0 <= x1 < x2 <= w + 1
        assert 0.0 <= y1 < y2 <= h + 1
        assert d.confidence >= 0.2
        assert isinstance(d.label, str) and d.label
