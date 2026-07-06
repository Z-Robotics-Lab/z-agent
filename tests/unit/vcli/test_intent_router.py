# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Tests for IntentRouter — keyword-based tool category routing."""
from zeno.vcli.intent_router import IntentRouter


class TestIntentRouter:
    def setup_method(self):
        self.router = IntentRouter()

    def test_code_intent_chinese(self):
        result = self.router.route("改一下代码")
        assert result is not None
        assert "code" in result

    def test_code_intent_english(self):
        result = self.router.route("fix the bug in navigate.py")
        assert result is not None
        assert "code" in result

    def test_robot_intent_chinese(self):
        result = self.router.route("去厨房")
        assert result is not None
        assert "robot" in result

    def test_robot_intent_english(self):
        result = self.router.route("navigate to kitchen")
        assert result is not None
        assert "robot" in result

    def test_diag_intent(self):
        result = self.router.route("FAR 为什么不工作")
        assert result is not None
        assert "diag" in result

    def test_sim_intent(self):
        result = self.router.route("启动仿真")
        assert result is not None
        assert "system" in result

    def test_ambiguous_returns_none(self):
        result = self.router.route("你好")
        assert result is None

    def test_mixed_intent(self):
        result = self.router.route("改完代码然后去厨房")
        assert result is not None
        assert "code" in result
        assert "robot" in result

    def test_explore_chinese(self):
        result = self.router.route("探索一下房子")
        assert result is not None
        assert "robot" in result

    def test_result_is_sorted(self):
        result = self.router.route("去厨房看看")
        if result is not None:
            assert result == sorted(result)


class TestAnnotationsResolvable:
    """Regression guard (E162 class): every annotation in intent_router must
    resolve. `from __future__ import annotations` stringizes them, so an
    undefined name (e.g. `Any` never imported) silently survives every green
    suite yet raises NameError the moment any tool calls typing.get_type_hints
    — a dead/untested path, exactly like config.py's undefined `logger`."""

    def test_all_callable_annotations_resolve(self):
        import inspect
        import typing

        from zeno.vcli import intent_router as mod

        unresolved = []
        members = [(mod.__name__, mod)]
        for name, obj in vars(mod).items():
            if inspect.isclass(obj) and obj.__module__ == mod.__name__:
                for mname, meth in vars(obj).items():
                    if inspect.isfunction(meth):
                        members.append((f"{name}.{mname}", meth))
            elif inspect.isfunction(obj) and obj.__module__ == mod.__name__:
                members.append((name, obj))

        for label, obj in members:
            try:
                typing.get_type_hints(obj)
            except NameError as exc:
                unresolved.append(f"{label}: {exc}")

        assert not unresolved, f"unresolved annotations (undefined names): {unresolved}"
