"""Acceptance toolchain (VisionJudge / VLM) honours ZENO_ env vars.

The visual acceptance face is a product-current surface (Inv.#2 second witness).
Its env knobs (JUDGE_BASE_URL/MODEL/API_KEY, VLM_URL/MODEL) must prefer the
ZENO_ product name and fall back to the legacy VECTOR_ name (kept for the
upstream .env / external harnesses). Fully offline — no network, no VLM call:
these assert the resolved module-level constants and the api_key selection only.
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture(autouse=True)
def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "ZENO_JUDGE_BASE_URL", "VECTOR_JUDGE_BASE_URL",
        "ZENO_JUDGE_MODEL", "VECTOR_JUDGE_MODEL",
        "ZENO_JUDGE_API_KEY", "VECTOR_JUDGE_API_KEY",
        "ZENO_VLM_URL", "VECTOR_VLM_URL",
        "ZENO_VLM_MODEL", "VECTOR_VLM_MODEL",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)


def test_judge_model_from_zeno_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """ZENO_JUDGE_MODEL alone (no VECTOR_) selects the judge model — the fix."""
    monkeypatch.setenv("ZENO_JUDGE_MODEL", "zeno/judge")
    import zeno.acceptance.vision_judge as vj

    importlib.reload(vj)
    try:
        assert vj._JUDGE_MODEL == "zeno/judge"
    finally:
        importlib.reload(vj)  # restore module state for other tests


def test_judge_model_from_vector_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy VECTOR_JUDGE_MODEL alone still selects the model (fallback kept)."""
    monkeypatch.setenv("VECTOR_JUDGE_MODEL", "vec/judge")
    import zeno.acceptance.vision_judge as vj

    importlib.reload(vj)
    try:
        assert vj._JUDGE_MODEL == "vec/judge"
    finally:
        importlib.reload(vj)


def test_judge_base_url_zeno_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZENO_JUDGE_BASE_URL", "https://zeno.example/v1")
    monkeypatch.setenv("VECTOR_JUDGE_BASE_URL", "https://vec.example/v1")
    import zeno.acceptance.vision_judge as vj

    importlib.reload(vj)
    try:
        assert vj._JUDGE_BASE_URL == "https://zeno.example/v1"
    finally:
        importlib.reload(vj)


def test_judge_api_key_from_zeno_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """judge() picks ZENO_JUDGE_API_KEY when set, over the OPENROUTER fallback."""
    monkeypatch.setenv("ZENO_JUDGE_API_KEY", "zk")
    monkeypatch.setenv("OPENROUTER_API_KEY", "ork")
    import zeno.acceptance.vision_judge as vj

    captured: dict = {}

    def fake_call(image_b64, prompt, *, model, api_key, timeout=60.0):  # noqa: ANN001
        captured["api_key"] = api_key
        return '{"items": {}}'

    monkeypatch.setattr(vj, "_encode_full_res", lambda p: "b64")
    vj.judge("/nonexistent.png", items=[], call=fake_call)
    assert captured["api_key"] == "zk"


def test_vlm_url_from_zeno_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """ZENO_VLM_URL alone flips the local-VLM backend on (the fix)."""
    monkeypatch.setenv("ZENO_VLM_URL", "http://localhost:11434/v1")
    import zeno.perception.vlm_go2 as vlm

    importlib.reload(vlm)
    try:
        assert vlm._LOCAL_VLM_URL == "http://localhost:11434/v1"
        assert vlm._USE_LOCAL_VLM is True
    finally:
        importlib.reload(vlm)


def test_vlm_url_from_vector_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VECTOR_VLM_URL", "http://legacy:11434/v1")
    import zeno.perception.vlm_go2 as vlm

    importlib.reload(vlm)
    try:
        assert vlm._LOCAL_VLM_URL == "http://legacy:11434/v1"
        assert vlm._USE_LOCAL_VLM is True
    finally:
        importlib.reload(vlm)
