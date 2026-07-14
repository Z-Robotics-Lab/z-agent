# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2024-2026 Vector Robotics

"""palette — the single-source display color palette for the REPL (P3.12).

Display-only: a dark-terminal-tuned set of tokens so every renderer speaks one
color language. Softened evidence colors (rich's default green/yellow/red read
harsh and muddy on dark terminals), a brightened brand teal, and a 4-step text
brightness ramp for visual hierarchy. Never feeds routing/verify — pure style.
"""
from __future__ import annotations

# Text brightness ramp
TEXT = "#e8edf2"        # primary — the thing to read
TEXT_DIM = "#8b95a3"    # secondary — verify predicates, args
TEXT_FAINT = "#5a6472"  # tertiary — timings, counts, hints
HAIRLINE = "#3a4150"    # weakest — separators, rails

# Brand teal (brightened into a small ramp)
BRAND = "#2dd4bf"       # primary accent (replaces #00b4b4)
BRAND_DIM = "#3a8a80"   # dim accent (replaces #006666)

# Evidence semantics (softened from rich defaults)
OK = "#5cc98f"          # GROUNDED / ✓ / success
WARN = "#f0b849"        # RAN / ○ / stale
BAD = "#e8897d"         # FAILED / ✗ / error

# Coordinated / test-pinned (keep these exact values)
TOOL_LABEL = "#738091"  # the dim "Tool" label (pinned by test_chain_view.py)
POSE = "#5fb8c4"        # live pose readout
