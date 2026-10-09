#!/usr/bin/env python3
"""
post_tool_journal.py — MiniMax Code `PostToolUse` audit trail.

Gives the platform `post-tool-events`: the record that separates a degraded
run from a clean one. Every completed tool call on a Sage project appends one
line to `.sage/gates/audit.jsonl`.

Deliberately small
------------------
Sage's fuller PostToolUse set is four scripts — verify-tracker,
degradation-log, manifest-sync, scope-journal. Only the last two are
extracted rather than rewritten upstream, and scope-journal delegates to a
38KB `scope_judge.py` that Sage ships DISABLED (its own comment: E-JUDGE-1
measured one false positive in four clean runs with unmeasurable detection).

So this port ships the audit trail and honestly leaves the rest staged. A
journal that records what happened is worth having on its own; a scope judge
that cries wolf is worse than none.

Bounded on purpose
------------------
`PostToolUse` has a 15s shared event budget with at most 8 concurrent
commands. This does one append and returns. It never blocks, never writes
stdout, and truncates any single record so a large tool response cannot blow
the 64KiB stdout cap or bloat the journal without bound.

A note on `context-injection-midstream`: this hook deliberately does NOT
claim it. That capability needs the scope judge's correction channel, which
is not ported yet. Declaring it here would be exactly the "sentence in a
README asserting it works" that Sage's conformance suite exists to delete.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time

MAX_RECORD = 2000  # bytes of tool detail kept per entry
TOOLS_OF_INTEREST = {"bash", "write", "edit", "multi_edit", "read", "grep", "glob"}


def truncate(value, limit: int = MAX_RECORD):
    """Keep the journal bounded without ever raising on odd input."""
    try:
        text = value if isinstance(value, str) else json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = repr(value)
    if len(text) <= limit:
        return text
    return text[:limit] + f"…(+{len(text) - limit} chars)"


def main() -> None:
    try:
        payload = json.loads(sys.stdin.buffer.read() or b"{}")
    except ValueError:
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    tool = (payload.get("tool_name") or "").strip()
    if tool.lower() not in TOOLS_OF_INTEREST:
        sys.exit(0)

    root = pathlib.Path(
        os.environ.get("MINIMAX_PROJECT_DIR")
        or (payload.get("cwd") or "").strip()
        or os.getcwd()
    )
    gates = root / ".sage" / "gates"
    if not (root / ".sage").is_dir():
        sys.exit(0)  # not a Sage project

    record = {
        "ts": int(time.time()),
        "tool": tool,
        "event": payload.get("hook_event_name") or "",
        "use_id": payload.get("tool_use_id") or "",
        "session": (payload.get("session_id") or "")[:16],
        "input": truncate(payload.get("tool_input")),
        "response": truncate(payload.get("tool_response")),
    }

    try:
        gates.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with (gates / "audit.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass  # an unwritable .sage/ must not break the user's tool loop

    # No stdout. This is a side-effect-only hook; the cheapest thing the host
    # can process is nothing at all.
    sys.exit(0)


if __name__ == "__main__":
    main()
