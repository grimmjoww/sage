#!/usr/bin/env python3
"""
pre_tool_gate.py — MiniMax Code `PreToolUse` adapter for the Sage gates.

This is the `pre-tool-veto` capability, and Sage's own docs are blunt about
it: "if you are choosing which capability to fight for, fight for the veto.
Everything else is a convenience. That one is the product." MiniMax can do
it — `permissionDecision: "deny"` rejects a tool call before it runs — so
this adapter exists to use that.

What it does
------------
Reads the MiniMax hook JSON on stdin, runs the routed Sage gates as
subprocesses with that same stdin, and translates the FIRST block into one
MiniMax deny object on stdout. If nothing blocks, it writes nothing at all
and exits 0 — a side-effect-only allow, which is the cheapest possible
answer for the host to process.

Why subprocesses instead of importing
-------------------------------------
The gates disagree with each other about their verdict transport:
spec and secrets write "BLOCK\\n<msg>" on stdout, tdd writes to stderr and
exits 2. Normalising them at extraction time would have been a rewrite by
stealth — the thing this build exists to avoid. Running them as-is keeps the
gate logic byte-identical to upstream and puts every MiniMax-specific
decision in this one auditable file.

Why it fails OPEN
-----------------
Sage's rule, quoted from the spec gate: "HOOKS ARE GUARDS, NOT GATES. Any
internal error fails OPEN. A broken hook must never brick a user's editor
loop." A hook that denies everything when it is confused trains the user to
disable it, which costs the whole framework. Every failure path below exits
0 with no output.

Failing open is not the same as failing silently
------------------------------------------------
A non-zero exit from this script is reported by the host as
`HOOK_PROCESS_EXITED` and the hook is skipped — which is a fail-open the
user cannot see. So an unexpected exception is caught, printed to stderr
with a traceback, and turned into a normal allow. The gate is still
enforcing; a programming error in *this file* is now visible in the host
log instead of vanishing into a skipped hook.

Budget
------
`hooks/hooks.json` gives this hook a 10s timeout for the whole PreToolUse
event, and the host kills the process at that mark — so overspending the
budget does not degrade the veto, it silently disables it. The routed gate
timeouts sum to more than 10s on the edit path, so the adapter keeps a
wall-clock deadline (EVENT_BUDGET) and short-circuits on the first block,
on a per-gate timeout, or on the first gate it can no longer afford. A gate
we do not run is not a gate that voted: it is reported on stderr and
treated as "no opinion", exactly like a timeout.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import traceback

# ── Gate routing, mirroring Claude's matcher table ──────────────────────
#
# Authoritative source: runtime/platforms/claude-code/setup/generate-claude-code.sh
#   PreToolUse  Edit|Write|MultiEdit        → spec, tdd, bookkeeping, secrets, scope
#   PreToolUse  Bash                         → verify
#   PreToolUse  Bash|Edit|Write|MultiEdit    → config
#
# Replicated exactly rather than running every gate for every call. Two
# reasons, and the second is the important one:
#
#   1. Speed. Six interpreter spawns per tool call is ~240ms of pure
#      startup for gates that mostly have no opinion.
#   2. Correctness. A gate running outside its upstream trigger is a
#      behaviour change, not an optimisation. Measured, not assumed: on a
#      `bash` payload both `scope` and `secrets` currently allow (neither
#      filters on tool name; both need a `file_path` a bash call does not
#      carry), so over-running them is harmless *today*. That is not a licence:
#      if either gate ever grows a bash-relevant rule, this table is what
#      keeps it from firing on calls Claude would have allowed. The bug this
#      port exists to prevent is a gate enforcing something upstream never
#      asked it to enforce.
#
# A tool outside both sets still gets `config`, the only gate Claude
# registers for the whole Bash|Edit|Write|MultiEdit family.
#
# Order within each list is cheapest-and-most-severe first, so a block costs
# one spawn rather than six. The third element is that gate's own ceiling;
# the adapter may still cut it shorter to stay inside EVENT_BUDGET.
EDIT_GATES = [
    ("secrets", "secrets_gate.py", 1.5),      # cheapest, most severe
    ("config", "config_gate.py", 2.0),        # stops an edit that disables enforcement
    ("spec", "spec_gate.py", 2.0),            # Rule 1
    ("bookkeeping", "bookkeeping_gate.py", 2.0),
    ("scope", "scope_gate.py", 2.5),
    ("tdd", "tdd_gate.py", 4.0),              # slowest — can invoke a test runner
]
BASH_GATES = [
    ("verify", "verify_gate.py", 1.5),
    ("config", "config_gate.py", 2.0),
]
UNIVERSAL_GATES = [("config", "config_gate.py", 2.0)]

# MiniMax matcher is `edit|write|bash` (hooks/hooks.json), so those are the
# names this adapter can actually be handed. The rest are accepted so a
# widened matcher does not silently drop to the universal list.
EDIT_TOOLS = {"edit", "write", "multiedit", "notebookedit"}
BASH_TOOLS = {"bash"}

HOST_TIMEOUT = 10.0      # hooks/hooks.json:23 — the whole PreToolUse event
SAFETY_MARGIN = 1.5       # JSON, interpreter startup, and the host's own kill
EVENT_BUDGET = HOST_TIMEOUT - SAFETY_MARGIN  # 8.5s of gate time we may spend

HERE = pathlib.Path(__file__).resolve().parent
GATE_DIR = HERE / "gates"

Gate = tuple[str, str, float]


def selected_gates(tool: str) -> list[Gate]:
    """Which gates run for this tool call, per Claude's matcher table."""
    name = (tool or "").strip().lower()
    if name in BASH_TOOLS:
        return BASH_GATES
    if name in EDIT_TOOLS:
        return EDIT_GATES
    return UNIVERSAL_GATES


def allow(reason: str = "") -> None:
    """No stdout at all. The host's default is to proceed."""
    if reason:
        print(f"sage: {reason}", file=sys.stderr)
    sys.exit(0)


def deny(message: str) -> None:
    """One MiniMax-native PreToolUse deny object."""
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": message,
        }
    }))
    sys.exit(0)


def verdict_of(name: str, gate: pathlib.Path, raw: bytes,
               timeout: float) -> str | None:
    """Run one gate. Return its block message, or None for 'no opinion'.

    Returns a message on a block; None on allow, on an internal error, or on
    a timeout. All three of those mean the same thing to this adapter, which
    is the point: a gate that cannot decide must not decide.

    Why the gate's output goes to temp files, not pipes
    ----------------------------------------------------
    With `capture_output=True`, subprocess gives the gate a PIPE for stdout
    and stderr. On timeout, subprocess.run kills the direct child and then
    calls communicate(), which blocks until *every* writer holding those pipe
    ends has closed them. A gate that spawns a grandchild — the TDD gate runs
    a test runner — hands that grandchild the same handles, so the kill does
    not end the wait. Measured on the edit path: 8.6s with only direct-child
    hangs, 25.0s with one grandchild holding stdout. Both are past the host's
    10s, so a pipe-based gate re-creates exactly the silent
    HOOK_PROCESS_EXITED fail-open the budget exists to prevent.

    A temp file has no such problem: the child and any grandchild inherit a
    plain file descriptor, nothing waits on it, and the direct child's exit is
    the only thing we synchronise on. We read the files back after the fact.

    Known limit: on timeout we kill the direct child only, so a grandchild it
    spawned can outlive us. That costs an orphan, not a stall — and the gates
    we ship bound their own subprocesses (the extracted tdd gate runs git with
    its own timeout).
    """
    with tempfile.TemporaryFile() as out_f, tempfile.TemporaryFile() as err_f:
        try:
            proc = subprocess.run(
                [sys.executable, str(gate)],
                input=raw,
                stdout=out_f,
                stderr=err_f,
                timeout=timeout,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired:
            print(f"sage: {name} gate timed out at {timeout:.1f}s; allowing",
                  file=sys.stderr)
            return None
        except OSError as exc:
            print(f"sage: {name} gate could not start ({exc}); allowing",
                  file=sys.stderr)
            return None

        out_f.seek(0)
        err_f.seek(0)
        out = out_f.read().decode("utf-8", "replace")
        err = err_f.read().decode("utf-8", "replace")

    # tdd gate: exit 2 with the reason on stderr.
    if proc.returncode == 2:
        return err.strip() or f"Sage {name} gate blocked this call."

    # Any other non-zero exit is an internal error. Fail open.
    if proc.returncode != 0:
        print(f"sage: {name} gate error ({proc.returncode}) {err.strip()[:200]}; "
              f"allowing", file=sys.stderr)
        return None

    if not out.startswith("BLOCK"):
        return None
    return out.split("\n", 1)[1].strip() if "\n" in out else \
        f"Sage {name} gate blocked this call."


def main() -> None:
    try:
        raw = sys.stdin.buffer.read()
    except (OSError, ValueError) as exc:
        allow(f"could not read hook input: {exc}")

    try:
        payload = json.loads(raw or b"{}")
    except ValueError:
        allow("hook input was not valid JSON")
    if not isinstance(payload, dict):
        allow("hook input was not a JSON object")

    # Not a Sage project, or the project opted out — nothing to enforce.
    root = (os.environ.get("MINIMAX_PROJECT_DIR")
            or (payload.get("cwd") or "").strip()
            or os.getcwd())
    if not (pathlib.Path(root) / ".sage").is_dir():
        allow()

    if not GATE_DIR.is_dir():
        allow(f"gate directory missing at {GATE_DIR}")

    deadline = time.monotonic() + EVENT_BUDGET
    gates = selected_gates(str(payload.get("tool_name") or ""))
    ran = 0

    for name, filename, ceiling in gates:
        gate = GATE_DIR / filename
        if not gate.is_file():
            print(f"sage: {name} gate not found at {gate}; allowing", file=sys.stderr)
            continue

        remaining = deadline - time.monotonic()
        if remaining <= 0.1:
            # Out of budget: the host would kill us at HOST_TIMEOUT and skip
            # the hook, which fails open silently. Stop while we still can.
            skipped = ", ".join(n for n, _, _ in gates[ran:])
            print(f"sage: event budget spent after {ran} gate(s); "
                  f"did not run: {skipped}", file=sys.stderr)
            allow()

        ran += 1
        message = verdict_of(name, gate, raw, min(ceiling, remaining))
        if message:
            deny(message)

    allow()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:  # noqa: BLE001 — see "Fails open, not silently"
        traceback.print_exc()
        print("sage: adapter raised; failing open so the hook is not skipped",
              file=sys.stderr)
        sys.exit(0)
