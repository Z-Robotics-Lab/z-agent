"""Regression guard: the async VGG completion closure must NOT late-bind the
REPL loop variable ``user_input`` (ruff B023 / classic closure-over-loop-var).

THE BUG (R375/E164, found by a mechanical ruff bugbear scan, same dormant-defect
flavor as E162/E163): ``_on_vgg_complete`` is defined inside the ``while True``
REPL loop in ``run_repl`` and launched on a BACKGROUND thread via
``engine.vgg_execute_async(goal_tree, on_complete=_on_vgg_complete)``; the REPL
then ``continue``s and blocks on the next prompt, REASSIGNING ``user_input``
(cli.py's read-input line). When the async goal finishes, the closure runs
``session.append_user(user_input)`` — reading whatever the user typed NEXT, not
the command that triggered the goal. Result: session-history mis-pairing (the
"[VGG executed]" assistant note gets attached to the wrong user turn).

It survives every green suite because tests drive VGG SYNCHRONOUSLY (the -p /
single-shot path uses ``vgg_execute`` and never reaches a second prompt before
completion). It only bites the REAL interactive acceptance face on Linux, where
``vgg_execute_async`` genuinely runs off-thread and the REPL keeps accepting
input.

FIX: bind the triggering command at closure-definition time via a default arg
(``def _on_vgg_complete(trace, _user_input=user_input)``) and record
``_user_input`` — eager capture, so a later reassignment cannot corrupt it.
``on_complete`` is only ever called as ``on_complete(trace)`` (engine.py), so the
extra defaulted parameter is never overridden.

This AST guard reads the SHIPPED source (not a copy) and also catches
re-introduction of the same late-binding.
"""
from __future__ import annotations

import ast
import inspect

from zeno.vcli import cli as cli_mod


def _find_on_vgg_complete() -> ast.FunctionDef:
    src = inspect.getsource(cli_mod)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_on_vgg_complete":
            return node
    raise AssertionError(
        "_on_vgg_complete not found in cli.py — did the async VGG completion "
        "handler get renamed? Update this regression guard."
    )


def _param_names(fn: ast.FunctionDef) -> set[str]:
    a = fn.args
    names = {p.arg for p in (*a.posonlyargs, *a.args, *a.kwonlyargs)}
    if a.vararg:
        names.add(a.vararg.arg)
    if a.kwarg:
        names.add(a.kwarg.arg)
    return names


def test_async_completion_does_not_free_load_user_input() -> None:
    """The closure body must not FREELY load ``user_input`` (the loop var).

    Pre-fix this FAILS (``session.append_user(user_input)`` is a free Load of the
    loop variable). Post-fix the triggering command flows through a bound
    parameter, so ``user_input`` never appears as a free Load in the body.
    """
    fn = _find_on_vgg_complete()
    bound = _param_names(fn)

    # Scan only the BODY — a Load of `user_input` in the default-arg expression
    # (``_user_input=user_input``) is the CORRECT def-time capture, evaluated in
    # the enclosing scope, not a late-binding body reference.
    body_nodes = [n for stmt in fn.body for n in ast.walk(stmt)]

    # Any free (non-parameter) Load of `user_input` inside the body is the bug:
    # it late-binds to the loop variable that the next prompt reassigns.
    free_user_input_loads = [
        node
        for node in body_nodes
        if isinstance(node, ast.Name)
        and node.id == "user_input"
        and isinstance(node.ctx, ast.Load)
        and "user_input" not in bound
    ]
    assert not free_user_input_loads, (
        "_on_vgg_complete late-binds the REPL loop variable `user_input` "
        f"(free Load at line(s) {[n.lineno for n in free_user_input_loads]}). "
        "The async completion runs on a background thread after the REPL has "
        "read the NEXT input, so this records the wrong user turn. Bind the "
        "triggering command via a def-time default arg instead."
    )


def test_triggering_command_bound_as_parameter() -> None:
    """Positive assertion: the triggering command is captured as a parameter.

    Guards against a 'fix' that reads the value some other late-binding way. The
    completion handler must take a parameter whose default is ``user_input`` so
    the value is frozen at def-time.
    """
    fn = _find_on_vgg_complete()
    defaulted = {
        arg.arg
        for arg in fn.args.args + fn.args.kwonlyargs
    }
    # There must be a parameter that carries the eagerly-captured command.
    default_srcs = {
        arg.arg: default
        for arg, default in zip(
            fn.args.args[len(fn.args.args) - len(fn.args.defaults):],
            fn.args.defaults,
        )
    }
    default_srcs.update(
        {
            arg.arg: default
            for arg, default in zip(fn.args.kwonlyargs, fn.args.kw_defaults)
            if default is not None
        }
    )
    bound_to_user_input = [
        name
        for name, default in default_srcs.items()
        if isinstance(default, ast.Name) and default.id == "user_input"
    ]
    assert bound_to_user_input, (
        "_on_vgg_complete must bind the triggering command at def-time via a "
        "parameter defaulting to the loop's `user_input` "
        f"(params seen: {sorted(defaulted)}). This freezes the value so the "
        "background-thread completion records the correct user turn."
    )
