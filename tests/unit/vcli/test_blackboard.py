# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""Unit tests for the run-scoped Blackboard (Phase D Stage 1a).

Covers capture (put/get/snapshot), reference resolution (nested dict, list
index, embedded substring, native-type preservation), unknown-path passthrough,
and — critically — that no ${...} payload is ever evaluated (no injection).
"""
from __future__ import annotations

import pytest

from vector_os_nano.vcli.cognitive.blackboard import Blackboard


# ---------------------------------------------------------------------------
# put / get / snapshot
# ---------------------------------------------------------------------------


def test_put_and_get_round_trip() -> None:
    bb = Blackboard()
    bb.put("detect", {"objects": [{"id": "cup"}]})
    assert bb.get("detect") == {"objects": [{"id": "cup"}]}


def test_get_missing_returns_none() -> None:
    assert Blackboard().get("nope") is None


def test_put_overwrites() -> None:
    bb = Blackboard()
    bb.put("step", {"v": 1})
    bb.put("step", {"v": 2})
    assert bb.get("step") == {"v": 2}


def test_put_ignores_non_dict_and_empty_name() -> None:
    bb = Blackboard()
    bb.put("step", ["not", "a", "dict"])  # type: ignore[arg-type]
    bb.put("", {"v": 1})
    assert bb.get("step") is None
    assert bb.data == {}


def test_data_and_snapshot_are_shallow_copies() -> None:
    bb = Blackboard()
    bb.put("a", {"x": 1})
    snap = bb.snapshot()
    snap["b"] = {"y": 2}  # mutating the copy must not affect the board
    assert bb.get("b") is None
    assert bb.data == {"a": {"x": 1}}


# ---------------------------------------------------------------------------
# resolve — exact single reference (native-type preserving)
# ---------------------------------------------------------------------------


def test_resolve_exact_ref_preserves_type() -> None:
    bb = Blackboard()
    bb.put("count", {"value": 42})
    assert bb.resolve("${count.value}") == 42
    assert isinstance(bb.resolve("${count.value}"), int)


def test_resolve_exact_ref_to_dict() -> None:
    bb = Blackboard()
    bb.put("detect", {"obj": {"id": "cup", "pos": [1, 2]}})
    assert bb.resolve("${detect.obj}") == {"id": "cup", "pos": [1, 2]}


def test_resolve_nested_dict_path() -> None:
    bb = Blackboard()
    bb.put("detect", {"obj": {"id": "cup"}})
    assert bb.resolve("${detect.obj.id}") == "cup"


# ---------------------------------------------------------------------------
# resolve — list index
# ---------------------------------------------------------------------------


def test_resolve_list_index() -> None:
    bb = Blackboard()
    bb.put("detect_all", {"objects": [{"id": "cup"}, {"id": "ball"}]})
    assert bb.resolve("${detect_all.objects.0.id}") == "cup"
    assert bb.resolve("${detect_all.objects.1.id}") == "ball"


def test_resolve_negative_list_index() -> None:
    bb = Blackboard()
    bb.put("s", {"items": ["a", "b", "c"]})
    assert bb.resolve("${s.items.-1}") == "c"


def test_resolve_out_of_range_index_passthrough() -> None:
    bb = Blackboard()
    bb.put("s", {"items": ["a"]})
    assert bb.resolve("${s.items.5}") == "${s.items.5}"


# ---------------------------------------------------------------------------
# resolve — embedded substrings (stringified)
# ---------------------------------------------------------------------------


def test_resolve_embedded_ref_is_stringified() -> None:
    bb = Blackboard()
    bb.put("detect", {"id": "cup"})
    assert bb.resolve("grasp the ${detect.id} now") == "grasp the cup now"


def test_resolve_multiple_embedded_refs() -> None:
    bb = Blackboard()
    bb.put("a", {"v": "X"})
    bb.put("b", {"v": "Y"})
    assert bb.resolve("${a.v}-${b.v}") == "X-Y"


# ---------------------------------------------------------------------------
# resolve — recursion through containers
# ---------------------------------------------------------------------------


def test_resolve_walks_nested_containers() -> None:
    bb = Blackboard()
    bb.put("detect", {"pos": [1.0, 2.0, 3.0]})
    payload = {
        "target": "${detect.pos}",
        "steps": ["${detect.pos}", "static"],
        "nested": {"p": "${detect.pos}"},
    }
    resolved = bb.resolve(payload)
    assert resolved["target"] == [1.0, 2.0, 3.0]
    assert resolved["steps"][0] == [1.0, 2.0, 3.0]
    assert resolved["steps"][1] == "static"
    assert resolved["nested"]["p"] == [1.0, 2.0, 3.0]


def test_resolve_non_string_scalars_pass_through() -> None:
    bb = Blackboard()
    assert bb.resolve(7) == 7
    assert bb.resolve(3.5) == 3.5
    assert bb.resolve(True) is True
    assert bb.resolve(None) is None


# ---------------------------------------------------------------------------
# unknown-path passthrough
# ---------------------------------------------------------------------------


def test_resolve_unknown_step_passthrough() -> None:
    bb = Blackboard()
    assert bb.resolve("${ghost.value}") == "${ghost.value}"


def test_resolve_unknown_key_passthrough() -> None:
    bb = Blackboard()
    bb.put("detect", {"id": "cup"})
    assert bb.resolve("${detect.missing}") == "${detect.missing}"


def test_resolve_traverse_into_scalar_passthrough() -> None:
    bb = Blackboard()
    bb.put("detect", {"id": "cup"})
    # "cup" is a scalar; further traversal must fail soft.
    assert bb.resolve("${detect.id.deeper}") == "${detect.id.deeper}"


def test_resolve_string_without_refs_unchanged() -> None:
    bb = Blackboard()
    assert bb.resolve("plain text") == "plain text"


# ---------------------------------------------------------------------------
# SECURITY: no eval / no injection
# ---------------------------------------------------------------------------


def test_resolve_injection_payload_is_inert() -> None:
    bb = Blackboard()
    # An import-style payload must NEVER execute; it has no matching path so it
    # resolves to passthrough (the original text), unchanged.
    payload = "${__import__('os').system('echo pwned')}"
    assert bb.resolve(payload) == payload


def test_resolve_code_like_path_not_evaluated() -> None:
    bb = Blackboard()
    bb.put("a", {"b": 1})
    # A path that looks like an expression is treated as literal dot-separated
    # segments — no arithmetic, no attribute access, no call.
    assert bb.resolve("${a.b + 1}") == "${a.b + 1}"
    assert bb.resolve("${a.__class__}") == "${a.__class__}"


@pytest.mark.parametrize(
    "bad",
    [
        "${}",
        "${.}",
        "${a..b}",
    ],
)
def test_resolve_malformed_paths_passthrough(bad: str) -> None:
    bb = Blackboard()
    bb.put("a", {"b": 1})
    assert bb.resolve(bad) == bad
