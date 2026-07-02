#!/usr/bin/env bash
# Adapter contract: stdin = the round prompt; run your agent CLI non-interactive/full-auto;
# your exit code = the round result. The agent must obey AGENTS.md + loop/ROUND.md.
exec claude -p "$(cat)" --dangerously-skip-permissions
