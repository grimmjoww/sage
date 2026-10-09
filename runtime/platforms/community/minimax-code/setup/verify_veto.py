#!/usr/bin/env python3
"""
verify_veto.py — prove the MiniMax Code adapter actually blocks, in both
directions, before anyone calls the port done.

Why this file exists
--------------------
Tonight, five separate Sage/WaifuClaw gates were found passing while
enforcing nothing. The common shape: a check that looked installed, ran,
exited 0 — and never tested the negative case. A veto gate that has only
ever been observed to ALLOW is indistinguishable from a gate that is not
wired up.

So this asserts the property, not a proxy. "The adapter ran" is not the
property. "A pre-spec edit to a source file was DENIED, and the same edit
was ALLOWED once the cycle advanced" is the property. Four cases, run
against the real adapter and the real extracted gates, on real fixtures.

Each case asserts an exact expectation. A mismatch fails loudly.

Usage:  python3 verify_veto.py [--adapter PATH]
Exit:   0 all cases matched · 1 a case did not · 2 bad arguments
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_ADAPTER = HERE.parent / "plugin" / "scripts" / "pre_tool_gate.py"

PRE_SPEC_MANIFEST = """---
title: "Fixture cycle"
status: in-progress
gate_state: pre-spec
---

# Fixture cycle

A deliberately unfinished cycle, used to prove the veto fires.
"""

BUILDING_MANIFEST = """---
title: "Fixture cycle"
status: in-progress
gate_state: building
---

# Fixture cycle

An advanced cycle. The spec gate must now wave source edits through.
"""

GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"
if not sys.stdout.isatty():
    GREEN = RED = DIM = RESET = ""


def build_fixture(root: pathlib.Path, *, sage: bool, enforce: bool,
                  manifest: str | None) -> None:
    """Create a throwaway project the gates will read."""
    if not sage:
        (root / "src").mkdir(parents=True, exist_ok=True)
        (root / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
        return

    sage_dir = root / ".sage"
    (sage_dir / "work" / "fixture-cycle").mkdir(parents=True, exist_ok=True)
    (sage_dir / "config.yaml").write_text(
        f"hard_enforcement: {'true' if enforce else 'false'}\n", encoding="utf-8")
    if manifest is not None:
        (sage_dir / "work" / "fixture-cycle" / "manifest.md").write_text(
            manifest, encoding="utf-8")
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")


def call_adapter(adapter: pathlib.Path, root: pathlib.Path, *,
                 tool: str = "write", rel: str = "src/app.py",
                 tool_input: dict | None = None
                 ) -> tuple[str, str, int]:
    """Invoke the adapter exactly as the host would: JSON on stdin, cwd set."""
    if tool_input is None:
        tool_input = {"path": rel, "content": "print('changed')\n"}
    payload = json.dumps({
        "hook_event_name": "PreToolUse",
        "session_id": "verify-veto-fixture",
        "cwd": str(root),
        "tool_name": tool,
        "tool_input": tool_input,
    }).encode("utf-8")

    env = os.environ.copy()
    env["MINIMAX_PROJECT_DIR"] = str(root)

    proc = subprocess.run(
        [sys.executable, str(adapter)],
        input=payload, capture_output=True, timeout=30, env=env,
    )
    return (proc.stdout.decode("utf-8", "replace"),
            proc.stderr.decode("utf-8", "replace"),
            proc.returncode)


def parsed_denies(stdout: str) -> list[dict]:
    """Pull MiniMax deny objects out of the adapter's stdout, if any."""
    out = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        hso = obj.get("hookSpecificOutput") or {}
        if hso.get("hookEventName") == "PreToolUse":
            out.append(obj)
    return out


def run_case(name: str, expect: str, *, expect_reason: str | None = None,
             **fixture) -> bool:
    """One assertion: does the adapter's verdict match `expect`?

    `expect_reason` closes the "wrong gate blocked" hole. A DENY is not
    automatically the right DENY: if the config gate's Bash branch were
    still dead and some other gate happened to block the same call, the
    verdict would match and the case would pass while the property stayed
    broken. So a DENY case may name the gate it expects to do the blocking.
    """
    root = pathlib.Path(tempfile.mkdtemp(prefix="sage-veto-"))
    try:
        adapter = pathlib.Path(fixture.pop("adapter", DEFAULT_ADAPTER))
        tool = fixture.pop("tool", "write")
        tool_input = fixture.pop("tool_input", None)
        build_fixture(root, **fixture)
        stdout, stderr, rc = call_adapter(adapter, root, tool=tool,
                                          tool_input=tool_input)
        denials = parsed_denies(stdout)
        denied = bool(denials) and \
            denials[0]["hookSpecificOutput"].get("permissionDecision") == "deny"

        got = "DENY" if denied else "ALLOW"
        ok = got == expect and rc == 0
        reason = ""

        if ok and denied and expect_reason:
            reason = (denials[0]["hookSpecificOutput"]
                      .get("permissionDecisionReason", ""))
            if expect_reason.lower() not in reason.lower():
                ok = False
                print(f"  {RED}FAIL{RESET}  {name} — denied, but not by "
                      f"{expect_reason!r}: {reason.splitlines()[:1]}")

        if ok:
            print(f"  {GREEN}PASS{RESET}  {name}")
            if denials:
                detail = (denials[0]["hookSpecificOutput"]
                          .get("permissionDecisionReason", "").splitlines() or [""])
                if detail and detail[0]:
                    print(f"        {DIM}{detail[0][:88]}{RESET}")
        else:
            if not expect_reason or not denied:
                print(f"  {RED}FAIL{RESET}  {name} — expected {expect}, got {got} "
                      f"(rc={rc})")
            if stderr.strip():
                print(f"        stderr: {stderr.strip()[:200]}")
            if stdout.strip():
                print(f"        stdout: {stdout.strip()[:200]}")
        return ok
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adapter", default=str(DEFAULT_ADAPTER))
    args = ap.parse_args()

    adapter = pathlib.Path(args.adapter)
    if not adapter.is_file():
        print(f"FAIL: adapter not found: {adapter}", file=sys.stderr)
        return 2

    print()
    print("── MiniMax Code veto probe ──")
    print(f"  adapter: {adapter}")
    print()

    cases = [
        # The proof. A pre-spec cycle must not be able to edit source.
        ("pre-spec edit of source file is DENIED", "DENY",
         dict(sage=True, enforce=True, manifest=PRE_SPEC_MANIFEST,
              adapter=adapter)),
        # Both directions of the same control, or the first case proves nothing.
        ("same edit ALLOWED once gate_state is building", "ALLOW",
         dict(sage=True, enforce=True, manifest=BUILDING_MANIFEST,
              adapter=adapter)),
        # Opt-out must be honoured, or the port breaks existing projects.
        ("hard_enforcement: false is ALLOWED", "ALLOW",
         dict(sage=True, enforce=False, manifest=PRE_SPEC_MANIFEST,
              adapter=adapter)),
        # Never brick a non-Sage repo.
        ("non-Sage project is ALLOWED", "ALLOW",
         dict(sage=False, enforce=False, manifest=None, adapter=adapter)),

        # ── The config gate, on both of the paths it guards ────────────────
        # The config gate is the only PreToolUse guard Claude registers for
        # the whole Bash|Edit|Write|MultiEdit family, and it has three
        # tool-name branches. Two of them (`tool == "Write"`, `tool ==
        # "Bash"`) were never patched to MiniMax's lowercase names, so both
        # fail open silently. These four cases are the property: without them
        # a re-broken patch still reports 4/4.
        ("write that weakens .sage/config.yaml is DENIED", "DENY",
         dict(sage=True, enforce=True, manifest=BUILDING_MANIFEST,
              adapter=adapter, tool="write",
              tool_input={"path": ".sage/config.yaml",
                          "content": "hard_enforcement: false\n"},
              expect_reason="config")),
        ("bash redirect that disables hard_enforcement is DENIED", "DENY",
         dict(sage=True, enforce=True, manifest=BUILDING_MANIFEST,
              adapter=adapter, tool="bash",
              tool_input={"command":
                          'echo "hard_enforcement: false" > .sage/config.yaml'},
              expect_reason="config")),
        # Negative controls. The two branches above were dead; switching them
        # on is only correct if they stay quiet on everything else. A gate
        # that blocks the whole session is the failure this port exists to
        # prevent, just in the other direction.
        ("bash that only reads .sage/config.yaml is ALLOWED", "ALLOW",
         dict(sage=True, enforce=True, manifest=BUILDING_MANIFEST,
              adapter=adapter, tool="bash",
              tool_input={"command": "cat .sage/config.yaml"})),
        ("bash that writes an ordinary file is ALLOWED", "ALLOW",
         dict(sage=True, enforce=True, manifest=BUILDING_MANIFEST,
              adapter=adapter, tool="bash",
              tool_input={"command": "echo hi > notes.txt"})),
        ("write to an ordinary source file is ALLOWED", "ALLOW",
         dict(sage=True, enforce=True, manifest=BUILDING_MANIFEST,
              adapter=adapter, tool="write",
              tool_input={"path": "src/app.py", "content": "print('ok')\n"})),
        # Same weakening, spelled the way the adapter routes it. The gates'
        # tool filters accepted only CamelCase "MultiEdit", so a lowercase
        # `multiedit` ran the config gate and was waved through by its own
        # self-filter — the veto present under one spelling and absent under
        # the other. Latent while the matcher is `edit|write|bash`.
        ("multiedit that weakens .sage/config.yaml is DENIED", "DENY",
         dict(sage=True, enforce=True, manifest=BUILDING_MANIFEST,
              adapter=adapter, tool="multiedit",
              tool_input={"path": ".sage/config.yaml",
                          "edits": [{"old_string": "hard_enforcement: true",
                                     "new_string": "hard_enforcement: false"}]},
              expect_reason="config")),
    ]

    results = [run_case(n, e, **kw) for n, e, kw in cases]
    passed = sum(1 for r in results if r)

    print()
    print(f"  {passed}/{len(results)} cases matched")
    print()
    if passed == len(results):
        print(f"  {GREEN}pre-tool-veto: PROVEN{RESET} — a pre-spec edit was blocked, "
              f"and allowed when it should be.")
        print()
        return 0

    print(f"  {RED}pre-tool-veto: NOT PROVEN{RESET} — do not claim this capability.")
    print()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
