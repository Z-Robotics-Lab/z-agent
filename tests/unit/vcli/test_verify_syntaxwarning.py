# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""LLM-authored verify expressions must not spam SyntaxWarning to the console.

A model often emits sloppy escape sequences (e.g. '\\.') inside a verify string.
``ast.parse`` parses them fine (the escape degrades to a literal) but, with no
filename, emits a ``SyntaxWarning`` against ``<unknown>`` straight to the user's
terminal. The verifier and decomposer suppress that noise — it is model output,
not a code defect.
"""
from __future__ import annotations

import warnings

from zeno.vcli.cognitive.goal_verifier import GoalVerifier


def test_verify_with_bad_escape_emits_no_syntaxwarning():
    gv = GoalVerifier({"file_exists": lambda p: False})
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)  # any SyntaxWarning -> test failure
        ok, _ = gv.evaluate("file_exists('a\\.txt')")  # bad escape '\.'
    assert ok is False  # the predicate ran; no warning leaked


def test_verify_bad_escape_does_not_break_evaluation():
    # Suppression must not change the verdict — the expression still evaluates.
    gv = GoalVerifier({"grep_count": lambda pat, path=".": 3})
    ok, val = gv.evaluate("grep_count('foo\\.bar') > 0")
    assert ok is True
    assert val is True
