#!/usr/bin/env python3
# GENERATED — do not edit by hand.
#
# Extracted verbatim from the Sage Claude Code adapter's
#   runtime/platforms/claude-code/hooks/sage-verify-gate.sh
# by runtime/platforms/community/minimax-code/setup/extract_gates.py
#
# The gate logic below is upstream's, unmodified. The only changes are the
# enumerated P1-P4 patches applied at build time; see setup/extract_gates.py
# for what each one is and why. Upstream SHA-256: 52c8fc3811083943
#
# Verdict contract, unchanged from Claude Code:
#   spec/secrets -> stdout "BLOCK\n<message>"   (also "ALLOW" / "WARN")
#   tdd          -> exit 2 with <message> on stderr
# pre_tool_gate.py translates either into the MiniMax deny JSON.
#
# Hooks fail OPEN. Any internal error must allow, never block, or one broken
# gate bricks the user's editor loop.
import json
import os
import re
import subprocess
import sys


def emit(decision, message=""):
    sys.stdout.write(decision + "\n")
    if message:
        sys.stdout.write(message)
    sys.exit(0)


try:
    data = json.load(sys.stdin)
except Exception:
    emit("WARN", "could not parse hook input JSON")
if not isinstance(data, dict):
    emit("WARN", "hook input was not a JSON object")

# P1: Claude names the tool "Bash"; MiniMax names it "bash".
if (data.get("tool_name") or "") not in ("Bash", "bash"):
    emit("ALLOW")
cmd = str((data.get("tool_input") or {}).get("command") or "")

if not re.search(r"\bgit\b[^\n;|&]*\bcommit\b", cmd):
    emit("ALLOW")

# A command that runs the tests on its way to the commit IS the discipline.
TEST_CMD = re.compile(
    r"\b(pytest|unittest|go\s+test|cargo\s+test|flutter\s+test|"
    r"npm\s+(run\s+)?test|npx\s+(vitest|jest|mocha)|vitest|jest|mocha|"
    r"sage-verify(\.sh)?)\b")
if TEST_CMD.search(cmd):
    emit("ALLOW")

project_root = (os.environ.get("MINIMAX_PROJECT_DIR")
                or os.environ.get("CLAUDE_PROJECT_DIR")
                or (data.get("cwd") or "").strip() or os.getcwd())
project_root = os.path.abspath(project_root)
sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    emit("ALLOW")

enforce = None
gate_off = False
config_path = os.path.join(sage_dir, "config.yaml")
if os.path.isfile(config_path):
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                m = re.match(r"\s*hard_enforcement\s*:\s*(true|false)\b", line, re.I)
                if m:
                    enforce = (m.group(1).lower() == "true")
                m = re.match(r"\s*verify_gate\s*:\s*false\b", line, re.I)
                if m:
                    gate_off = True
    except OSError:
        pass
if enforce is not True or gate_off:
    emit("ALLOW")

# The evidence.
state = {}
state_path = os.path.join(sage_dir, "tmp", "verify-state")
if os.path.isfile(state_path):
    try:
        with open(state_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "=" in line:
                    k, _, v = line.strip().partition("=")
                    state[k] = v
    except OSError:
        pass
edit_ts = state.get("last_source_edit")
test_ts = state.get("last_test_run")
cur_sid = str(data.get("session_id") or "")

# Test evidence is FRESH iff (a) it exists, (b) it belongs to THIS session when
# session ids are available — a suite that was green yesterday says nothing
# about today's tree (v2, after the E3 shape: the unverified work may be
# someone ELSE's, so the agent's own edit timestamp cannot be the only anchor),
# and (c) no source edit landed after it.
fresh = test_ts is not None
if fresh and cur_sid and state.get("last_test_session") \
        and state["last_test_session"] != cur_sid:
    fresh = False
if fresh and edit_ts:
    try:
        fresh = int(test_ts) >= int(edit_ts)
    except ValueError:
        pass
if fresh:
    emit("ALLOW")

# No fresh evidence. Does this commit carry CODE? Docs-only commits pass; a
# commit that cannot be inspected falls back to the v1 agent-edit anchor
# (block only when the agent itself edited source after the last test run) —
# never invent a violation the tree cannot confirm.
CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
            ".java", ".rb", ".dart", ".c", ".cc", ".cpp", ".h", ".swift", ".kt")
code_pending = None
try:
    r = subprocess.run(["git", "-C", project_root, "diff", "--cached",
                        "--name-only"], capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        pending = [f for f in (r.stdout or "").splitlines() if f.strip()]
        # `git commit -a` bypasses the index — include unstaged too.
        if re.search(r"\bcommit\b[^\n;|&]*(\s-a\b|\s--all\b|\s-am\b)", cmd) or not pending:
            r2 = subprocess.run(["git", "-C", project_root, "diff", "--name-only"],
                                capture_output=True, text=True, timeout=10)
            if r2.returncode == 0:
                pending += [f for f in (r2.stdout or "").splitlines() if f.strip()]
        code_pending = any(f.endswith(CODE_EXT) for f in pending)
except Exception:
    code_pending = None

if code_pending is False:
    emit("ALLOW")                       # provably docs-only (or empty) — nothing to verify
if code_pending is None and not edit_ts:
    emit("ALLOW")                       # cannot inspect AND no agent edit recorded — fail open

emit("BLOCK", (
    "sage-verify-gate: source changed since the last test run — run the tests "
    "before committing (verify before claiming; a user or a comment SAYING the "
    "tests pass is not the tests passing).\n"
    "\n"
    "Run the suite (e.g. `python3 -m pytest -q`, `npm test`, or "
    "`bash .sage/gates/scripts/sage-verify.sh`), look at the result, then "
    "commit. If the tests fail, that is the finding — surface it instead of "
    "committing over it."))
