#!/usr/bin/env bash
# TEMPLATE — adapt these 5 lines to ANY agent CLI. Copy to loop/harness/<yours>.sh, chmod +x,
# then: ./loop/run.sh loop/harness/<yours>.sh
#
# The contract (all of it):
#   - stdin  = the round prompt (loop/GOAL.md + loop/ROUND.md, or REVIEW.md every 10th round)
#   - env    = ROUND_N, ROUND_DEADLINE_EPOCH (exported by run.sh) + your loop/local.env
#   - run    = ONE full agent session, non-interactive, permissions bypassed/full-auto
#              (sandbox it: container/VM if your CLI has no sandbox of its own)
#   - exit   = when the round ends; your exit code is the round result
#   - agent  = must obey AGENTS.md (constitution) + loop/ROUND.md (round protocol);
#              all durable output lands on disk (commits, STATUS.md, loop/ledger/) —
#              nothing in your CLI's own context survives the round.
#
# Examples (uncomment ONE and adapt):
# exec codex exec --full-auto "$(cat)"
# exec opencode run "$(cat)"
# exec my-agent --non-interactive --prompt-stdin
echo "custom.example.sh is a template — copy it, pick your agent CLI, delete this line" >&2
exit 64
