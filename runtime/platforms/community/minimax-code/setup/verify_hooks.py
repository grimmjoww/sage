#!/usr/bin/env python3
"""
verify_hooks.py — prove the two lifecycle hooks actually do their job.

Same discipline as verify_veto.py: each case asserts an observable property,
and every "do nothing" case is asserted too. A hook that never fires and a
hook that fires and stays silent are indistinguishable if you only test the
happy path — so half of these cases assert that nothing happened.

  SessionStart  a Sage project gets its active cycle injected as
                additionalContext; a non-Sage project gets NOTHING on stdout,
                because a plugin that greets every repo in the world is noise.
  PostToolUse   a completed tool call is journalled to .sage/gates/audit.jsonl
                in a Sage project, and writes no file anywhere else.

Exit: 0 all cases matched · 1 at least one did not
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "plugin" / "scripts"

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = DIM = RESET = ""

CYCLE_SPEC = """---
title: "Cockpit slice"
status: in-progress
gate_state: pre-spec
phase: specification
---

# Cockpit slice
"""


def make_project(*, sage: bool) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp(prefix="sage-hooks-"))
    if sage:
        (root / ".sage" / "work" / "cockpit").mkdir(parents=True)
        (root / ".sage" / "config.yaml").write_text("hard_enforcement: true\n",
                                                    encoding="utf-8")
        (root / ".sage" / "work" / "cockpit" / "spec.md").write_text(
            CYCLE_SPEC, encoding="utf-8")
    return root


def invoke(script: str, payload: dict, root: pathlib.Path):
    env = os.environ.copy()
    env["MINIMAX_PROJECT_DIR"] = str(root)
    env["PLUGIN_DATA"] = str(root / ".plugindata")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script)],
        input=json.dumps(payload).encode("utf-8"),
        capture_output=True, timeout=20, env=env,
    )
    return proc.stdout.decode("utf-8", "replace"), proc.returncode


def check(name: str, ok: bool, detail: str = "") -> bool:
    if ok:
        print(f"  {GREEN}PASS{RESET}  {name}")
        if detail:
            print(f"        {DIM}{detail[:88]}{RESET}")
    else:
        print(f"  {RED}FAIL{RESET}  {name}" + (f" — {detail[:180]}" if detail else ""))
    return ok


def main() -> int:
    if not SCRIPTS.is_dir():
        print(f"FAIL: scripts dir missing: {SCRIPTS}", file=sys.stderr)
        return 1

    print()
    print("── MiniMax Code lifecycle hook probe ──")
    print(f"  scripts: {SCRIPTS}")
    print()

    results = []

    # 1. SessionStart injects the active cycle on a Sage project.
    root = make_project(sage=True)
    try:
        out, rc = invoke("session_start.py", {
            "hook_event_name": "SessionStart", "session_id": "probe-1",
            "source": "startup", "cwd": str(root)}, root)
        ok = False
        detail = ""
        try:
            hso = json.loads(out)["hookSpecificOutput"]
            ctx = hso["additionalContext"]
            ok = (hso["hookEventName"] == "SessionStart"
                  and "Cockpit slice" in ctx
                  and "in progress" in ctx
                  and rc == 0)
            detail = ctx.splitlines()[0] if ctx else ""
        except Exception as exc:
            detail = f"{exc}: {out[:120]}"
        results.append(check("SessionStart injects active cycle on a Sage project",
                             ok, detail))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # 2. SessionStart stays completely silent on a non-Sage project.
    root = make_project(sage=False)
    try:
        out, rc = invoke("session_start.py", {
            "hook_event_name": "SessionStart", "session_id": "probe-2",
            "source": "startup", "cwd": str(root)}, root)
        results.append(check(
            "SessionStart is silent on a non-Sage project",
            out.strip() == "" and rc == 0,
            f"stdout={out[:60]!r}" if out.strip() else "no stdout"))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # 3. PostToolUse journals a completed tool call on a Sage project.
    root = make_project(sage=True)
    try:
        out, rc = invoke("post_tool_journal.py", {
            "hook_event_name": "PostToolUse", "session_id": "probe-3",
            "tool_name": "write", "tool_use_id": "tu_1", "cwd": str(root),
            "tool_input": {"path": "src/app.py", "content": "x = 1"},
            "tool_response": {"ok": True}}, root)
        audit = root / ".sage" / "gates" / "audit.jsonl"
        lines = audit.read_text(encoding="utf-8").strip().splitlines() if audit.is_file() else []
        rec = json.loads(lines[0]) if lines else {}
        ok = (audit.is_file() and len(lines) == 1
              and rec.get("tool") == "write"
              and rec.get("use_id") == "tu_1"
              and out.strip() == "" and rc == 0)
        results.append(check(
            "PostToolUse writes one audit record on a Sage project", ok,
            f"{len(lines)} line(s), tool={rec.get('tool')!r}"))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # 4. PostToolUse writes nothing outside a Sage project.
    root = make_project(sage=False)
    try:
        out, rc = invoke("post_tool_journal.py", {
            "hook_event_name": "PostToolUse", "session_id": "probe-4",
            "tool_name": "bash", "tool_use_id": "tu_2", "cwd": str(root),
            "tool_input": {"command": "ls"}, "tool_response": {}}, root)
        stray = [p for p in root.rglob("audit.jsonl")]
        results.append(check(
            "PostToolUse writes nothing on a non-Sage project",
            not stray and out.strip() == "" and rc == 0,
            f"stray files: {stray}" if stray else "no files created"))
    finally:
        shutil.rmtree(root, ignore_errors=True)

    passed = sum(1 for r in results if r)
    print()
    print(f"  {passed}/{len(results)} cases matched")
    print()
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
