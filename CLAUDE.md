# Claude Code shim — the constitution is AGENTS.md (all harnesses read that file)
@AGENTS.md
<!-- Claude-specific notes only below this line. Do not add rules here — add them there. -->
- You MAY use native subagents/Workflow/skills as accelerators; the contract is ONLY the
  disk artifacts named in AGENTS.md — no in-context state survives a round.
- Harness project memory (~/.claude/projects/.../MEMORY.md) is machine-local: never rely on
  it. Anything load-bearing must also land in docs/LESSONS.md (Casebook for hidden bugs).
