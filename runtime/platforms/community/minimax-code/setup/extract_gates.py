#!/usr/bin/env python3
"""
extract_gates.py — lift Claude Code's embedded gate Python into the MiniMax
Code plugin package, patched for the MiniMax hook contract.

Why this script exists
----------------------
The three `PreToolUse` gates in the Claude Code adapter are 91%/79%/78%
Python; the bash around them only does plumbing (check `python3`, mktemp,
write a temp file, run it, translate the verdict). Rewriting the gates would
mean hand-transcribing ~1,200 lines — which is exactly how a gate starts
lying. So we do not rewrite. We extract the Python verbatim and apply a
small, enumerated set of patches, each of which is ASSERTED. A patch that
does not apply aborts the build instead of silently producing a gate that
allows everything.

Sage's own rule applies here: a gate must assert the property, not a proxy.
"The script ran" is not the property. "The gate denies a pre-spec edit" is.

The patches (each one is a real Claude→MiniMax divergence)
-----------------------------------------------------------
P1  TOOL NAMES. Claude emits "Edit"/"Write"/"MultiEdit"; MiniMax emits
    lowercase "edit"/"write". A gate that matches Claude's capitalised
    names will `allow()` every MiniMax call — a gate that looks installed
    and enforces nothing. This is the exact failure Sage's v1.2.0 eval
    measured at a behavioural delta of zero.

P2  FILE PATH FIELD. Claude's Edit/Write input field is `file_path`;
    MiniMax's `write`/`edit` use `path`. Same failure mode as P1: an empty
    path falls through to "not a recognized source file" → ALLOW.

P3  PROJECT ROOT ENV. `CLAUDE_PROJECT_DIR` does not exist in MiniMax; the
    host injects `MINIMAX_PROJECT_DIR`. Without this the root falls back to
    os.getcwd(), which is the *turn workspace*, not necessarily the project.

P4  VERDICT TRANSPORT. Claude gates signal a block with `exit 2` + a message
    on stderr; spec/secrets gates instead write "BLOCK\\n<msg>" on stdout.
    MiniMax wants one JSON object on stdout. We leave both transports
    intact and translate in the adapter (pre_tool_gate.py), because the
    three gates do not agree with each other and normalising them here
    would be a rewrite by stealth.

Exit: 0 success · 1 a patch did not apply · 2 bad arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

# Claude tool names -> MiniMax tool names. Both are accepted after patching so
# the extracted gate still runs under Claude Code, which keeps this file
# diffable against upstream.
TOOL_NAMES = {
    "sage-tdd-gate.sh": [
        (
            'if tool not in ("Edit", "Write", "MultiEdit"):',
            'if tool not in ("edit", "write", "multiedit",\n'
            '                "Edit", "Write", "MultiEdit"):',
            "P1 tool names (tdd)",
        ),
        (
            'os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()',
            'os.environ.get("MINIMAX_PROJECT_DIR")\n'
            '    or os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '    or payload.get("cwd") or os.getcwd()',
            "P3 project root (tdd)",
        ),
    ],
    "sage-spec-gate.sh": [
        (
            'tool_input = data.get("tool_input") or {}\n'
            'file_path = (tool_input.get("file_path") or "").strip()',
            'tool_input = data.get("tool_input") or {}\n'
            '# P2: Claude sends "file_path"; MiniMax sends "path". Accept both.\n'
            'file_path = (tool_input.get("file_path")\n'
            '             or tool_input.get("path") or "").strip()',
            "P2 file path (spec)",
        ),
        (
            'project_root = (os.environ.get("CLAUDE_PROJECT_DIR") or stdin_cwd or os.getcwd())',
            'project_root = (os.environ.get("MINIMAX_PROJECT_DIR")\n'
            '                or os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or stdin_cwd or os.getcwd())',
            "P3 project root (spec)",
        ),
    ],
    "sage-secrets-gate.sh": [
        (
            'file_path = (tool_input.get("file_path") or "").strip()',
            '# P2: Claude sends "file_path"; MiniMax sends "path". Accept both.\n'
            'file_path = (tool_input.get("file_path")\n'
            '             or tool_input.get("path") or "").strip()',
            "P2 file path (secrets)",
        ),
        (
            'project_root = (os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            'project_root = (os.environ.get("MINIMAX_PROJECT_DIR")\n'
            '                or os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            "P3 project root (secrets)",
        ),
    ],
    # The verify gate watches Bash specifically, so it is the one gate whose
    # whole trigger is a tool NAME. Get this patch wrong and it allows
    # everything, because "bash" never equals "Bash".
    "sage-verify-gate.sh": [
        (
            'if (data.get("tool_name") or "") != "Bash":',
            '# P1: Claude names the tool "Bash"; MiniMax names it "bash".\n'
            'if (data.get("tool_name") or "") not in ("Bash", "bash"):',
            "P1 tool names (verify)",
        ),
        (
            'project_root = (os.environ.get("CLAUDE_PROJECT_DIR")',
            'project_root = (os.environ.get("MINIMAX_PROJECT_DIR")\n'
            '                or os.environ.get("CLAUDE_PROJECT_DIR")',
            "P3 project root (verify)",
        ),
    ],
    # ── The remaining PreToolUse guards ────────────────────────────────────
    "sage-scope-gate.sh": [
        (
            'file_path = (tool_input.get("file_path") or "").strip()',
            'file_path = (tool_input.get("file_path")\n'
            '             or tool_input.get("path") or "").strip()',
            "P2 file path (scope)",
        ),
        (
            'project_root = (os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            'project_root = (os.environ.get("MINIMAX_PROJECT_DIR")\n'
            '                or os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            "P3 project root (scope)",
        ),
    ],
    "sage-bookkeeping-gate.sh": [
        (
            'file_path = (tool_input.get("file_path") or "").strip()',
            'file_path = (tool_input.get("file_path")\n'
            '             or tool_input.get("path") or "").strip()',
            "P2 file path (bookkeeping)",
        ),
        (
            'project_root = (os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            'project_root = (os.environ.get("MINIMAX_PROJECT_DIR")\n'
            '                or os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            "P3 project root (bookkeeping)",
        ),
        (
            'if tool == "Write":',
            'if tool in ("Write", "write"):',
            "P1 tool names (bookkeeping)",
        ),
    ],
    "sage-config-gate.sh": [
        (
            'project_root = (os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            'project_root = (os.environ.get("MINIMAX_PROJECT_DIR")\n'
            '                or os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            "P3 project root (config)",
        ),
        (
            'if tool in ("Edit", "Write", "MultiEdit"):',
            'if tool in ("edit", "write", "multiedit",\n'
            '              "Edit", "Write", "MultiEdit"):',
            "P1 tool names (config)",
        ),
        (
            'str(tool_input.get("file_path") or "")',
            'str(tool_input.get("file_path") or tool_input.get("path") or "")',
            "P2 file path (config)",
        ),
        # The config gate is the one guard that runs on BOTH the edit and the
        # bash path, and it has three tool-name branches, not one. The P1 patch
        # above only widens the `tool in (...)` branch. These two were missed,
        # and both fail OPEN silently:
        #
        #   `if tool == "Write"` — on MiniMax the tool is "write", so the gate
        #   fell to the else branch, which reconstructs via edits. A `write`
        #   carries `content`, not edits, so `after` stayed equal to `current`
        #   and `weaker(current, current)` was never true. A `write` that
        #   weakened .sage/config.yaml was ALLOWED.
        #
        #   `if tool == "Bash"` — "bash" never equals "Bash", so the entire
        #   Bash-evasion branch (redirect/sed/tee that turns an enforcement key
        #   off) was dead code on MiniMax.
        (
            'if tool == "Write":',
            'if tool in ("Write", "write"):',
            "P1 tool names (config, write branch)",
        ),
        (
            'if tool == "Bash":',
            'if tool in ("Bash", "bash"):',
            "P1 tool names (config, bash branch)",
        ),
    ],
    # ── The PostToolUse observers ──────────────────────────────────────────
    # degradation-log already reads `file_path` OR `path`, so it needs only P3.
    "sage-degradation-log.sh": [
        (
            'project_root = os.path.abspath(\n'
            '    os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()\n'
            ')',
            'project_root = os.path.abspath(\n'
            '    os.environ.get("MINIMAX_PROJECT_DIR")\n'
            '    or os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '    or payload.get("cwd") or os.getcwd()\n'
            ')',
            "P3 project root (degradation)",
        ),
    ],
    "sage-verify-tracker.sh": [
        (
            'project_root = (os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            'project_root = (os.environ.get("MINIMAX_PROJECT_DIR")\n'
            '                or os.environ.get("CLAUDE_PROJECT_DIR")\n'
            '                or (data.get("cwd") or "").strip() or os.getcwd())',
            "P3 project root (verify-tracker)",
        ),
        (
            'if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):',
            'if tool in ("edit", "write", "Edit", "Write", "MultiEdit", "NotebookEdit"):',
            "P1 tool names (verify-tracker)",
        ),
        (
            'path = str(tool_input.get("file_path") or "")',
            'path = str(tool_input.get("file_path") or tool_input.get("path") or "")',
            "P2 file path (verify-tracker)",
        ),
    ],
}

OUTPUT_NAMES = {
    "sage-spec-gate.sh": "spec_gate.py",
    "sage-tdd-gate.sh": "tdd_gate.py",
    "sage-secrets-gate.sh": "secrets_gate.py",
    "sage-verify-gate.sh": "verify_gate.py",
    "sage-scope-gate.sh": "scope_gate.py",
    "sage-bookkeeping-gate.sh": "bookkeeping_gate.py",
    "sage-config-gate.sh": "config_gate.py",
    "sage-degradation-log.sh": "degradation_log.py",
    "sage-verify-tracker.sh": "verify_tracker.py",
}

# Which adapter runs each gate, and on which MiniMax event. The adapter reads
# this so the routing is data, not a second hand-maintained list.
EVENTS = {
    "spec_gate.py": "PreToolUse",
    "tdd_gate.py": "PreToolUse",
    "secrets_gate.py": "PreToolUse",
    "verify_gate.py": "PreToolUse",
    "scope_gate.py": "PreToolUse",
    "bookkeeping_gate.py": "PreToolUse",
    "config_gate.py": "PreToolUse",
    "degradation_log.py": "PostToolUse",
    "verify_tracker.py": "PostToolUse",
}

BANNER = '''#!/usr/bin/env python3
# GENERATED — do not edit by hand.
#
# Extracted verbatim from the Sage Claude Code adapter's
#   runtime/platforms/claude-code/hooks/{source}
# by runtime/platforms/community/minimax-code/setup/extract_gates.py
#
# The gate logic below is upstream's, unmodified. The only changes are the
# enumerated P1-P4 patches applied at build time; see setup/extract_gates.py
# for what each one is and why. Upstream SHA-256: {digest}
#
# Verdict contract, unchanged from Claude Code:
#   spec/secrets -> stdout "BLOCK\\n<message>"   (also "ALLOW" / "WARN")
#   tdd          -> exit 2 with <message> on stderr
# pre_tool_gate.py translates either into the MiniMax deny JSON.
#
# Hooks fail OPEN. Any internal error must allow, never block, or one broken
# gate bricks the user's editor loop.
'''


def extract_python(source_text: str, hook_name: str) -> str:
    """Pull the heredoc'd Python program out of a Sage .sh hook."""
    lines = source_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("cat >") and "<<'PYEOF'" in line:
            start = i + 1
            break
    if start is None:
        raise SystemExit(f"FAIL {hook_name}: no <<'PYEOF' heredoc found")

    body: list[str] = []
    for line in lines[start:]:
        if line.strip() == "PYEOF":
            return "\n".join(body) + "\n"
        body.append(line)
    raise SystemExit(f"FAIL {hook_name}: heredoc opened but never closed with PYEOF")


def apply_patches(code: str, hook_name: str) -> str:
    """Apply P1-P4, asserting each one landed. A silent no-op here is a
    false-passing gate, which is worse than a build failure."""
    patches = TOOL_NAMES.get(hook_name)
    if not patches:
        raise SystemExit(f"FAIL {hook_name}: no patch table for this hook")

    for old, new, label in patches:
        if old not in code:
            raise SystemExit(
                f"FAIL {hook_name}: patch {label!r} did not apply.\n"
                f"  Upstream changed shape. Refusing to emit a gate that may\n"
                f"  allow everything. Anchor not found:\n"
                f"  {old!r}"
            )
        if code.count(old) != 1:
            raise SystemExit(
                f"FAIL {hook_name}: patch {label!r} anchor is ambiguous "
                f"({code.count(old)} matches). Refusing to guess."
            )
        code = code.replace(old, new, 1)

    return code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--claude-code-hooks", required=True,
                    help="path to runtime/platforms/claude-code/hooks")
    ap.add_argument("--out", required=True,
                    help="output dir for the generated *_gate.py files")
    args = ap.parse_args()

    hooks_dir = pathlib.Path(args.claude_code_hooks)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not hooks_dir.is_dir():
        print(f"FAIL: hooks dir not found: {hooks_dir}", file=sys.stderr)
        return 2

    written = []
    for hook_name, out_name in OUTPUT_NAMES.items():
        src = hooks_dir / hook_name
        if not src.is_file():
            print(f"FAIL: {src} not found", file=sys.stderr)
            return 2

        raw = src.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        code = apply_patches(extract_python(raw.decode("utf-8"), hook_name), hook_name)

        banner = BANNER.format(source=hook_name, digest=digest[:16])
        target = out_dir / out_name
        target.write_text(banner + code, encoding="utf-8", newline="\n")

        py_lines = code.count("\n")
        print(f"  ok  {hook_name:<24} -> {out_name:<18} {py_lines:>4} lines  sha={digest[:12]}")
        written.append(target)

    # Every extracted gate must still be valid Python. A syntax error here
    # would surface only when a user's edit gets silently allowed.
    for path in written:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as exc:
            print(f"FAIL: {path.name} does not compile: {exc}", file=sys.stderr)
            return 1
        print(f"  ok  {path.name:<18} compiles")

    print(f"\n  {len(written)} gate(s) extracted, all patches applied, all compile.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
