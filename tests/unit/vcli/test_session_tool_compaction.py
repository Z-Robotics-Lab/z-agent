# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""R2-8: history assembly must never emit an orphaned tool message.

A ``role:"tool"`` (OpenAI) / ``tool_result`` (Anthropic) message not preceded by
the assistant ``tool_calls``/``tool_use`` that produced it makes the chat APIs
400 ("Messages with role 'tool' must be a response to a preceding message with
'tool_calls'") and bricks the REPL. Two surfaces are covered:
- ``compact()`` slicing the history mid tool-exchange (the root cause), and
- ``to_messages()`` defensively dropping any orphan it is handed.
"""
from __future__ import annotations

from vector_os_nano.vcli.backends.openai_compat import convert_messages
from vector_os_nano.vcli.session import create_session


def _tool_use(tid: str, name: str = "walk") -> list[dict]:
    return [{"type": "tool_use", "id": tid, "name": name, "input": {}}]


def _assert_no_orphan_tool(openai_msgs: list[dict]) -> None:
    """Every role:'tool' must fall under an open assistant tool_calls window."""
    open_ids: set[str] = set()
    for m in openai_msgs:
        role = m["role"]
        if role == "assistant":
            open_ids = {tc["id"] for tc in m.get("tool_calls", [])}
        elif role == "tool":
            assert m["tool_call_id"] in open_ids, (
                f"orphan tool message {m.get('tool_call_id')!r} — no open tool_calls"
            )
        else:  # system / user
            open_ids = set()


def _seed_tool_exchange(session, n_turns: int) -> None:
    """Append n_turns of [user, assistant(tool_use), tool_result] triples."""
    for i in range(n_turns):
        session.append_user(f"do task {i}")
        session.append_assistant(text="", tool_use_blocks=_tool_use(f"tu_{i}"))
        session.append_tool_results([{"tool_use_id": f"tu_{i}", "content": "ok"}])


def test_well_formed_history_converts_cleanly(tmp_path):
    session = create_session(directory=tmp_path)
    _seed_tool_exchange(session, 3)
    _assert_no_orphan_tool(convert_messages(session.to_messages(), "sys"))


def test_to_messages_drops_orphan_tool_result(tmp_path):
    """An orphaned tool_result (no preceding assistant tool_use) is dropped."""
    session = create_session(directory=tmp_path)
    session.append_user("[Earlier conversation summary]")
    session.append_tool_results([{"tool_use_id": "tu_gone", "content": "stale"}])
    session.append_assistant(text="continuing")
    msgs = session.to_messages()
    for m in msgs:
        if m["role"] == "user" and isinstance(m["content"], list):
            assert not any(b.get("type") == "tool_result" for b in m["content"])
    _assert_no_orphan_tool(convert_messages(msgs, "sys"))


def test_compact_does_not_orphan_a_tool_result(tmp_path):
    """compact() must not start the recent window on a tool_result whose
    producing assistant gets summarized away (the live 400 root cause)."""
    session = create_session(directory=tmp_path)
    _seed_tool_exchange(session, 3)  # 9 non-meta entries: [u,a,t]*3
    # keep_recent=7 -> naive cut=2 -> recent[0] would be t0 (orphan).
    session.compact(keep_recent=7)
    _assert_no_orphan_tool(convert_messages(session.to_messages(), "sys"))
    non_meta = [e for e in session._entries if e.get("type") != "meta"]
    assert non_meta[1].get("type") != "tool_result"  # entry after the summary


def test_repeated_compaction_stays_valid(tmp_path):
    """Many turns + repeated auto-compaction never produces an orphan."""
    session = create_session(directory=tmp_path)
    for _ in range(6):
        _seed_tool_exchange(session, 3)
        session.compact(keep_recent=12)
    _assert_no_orphan_tool(convert_messages(session.to_messages(), "sys"))
