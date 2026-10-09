#!/usr/bin/env python3
# GENERATED — do not edit by hand.
#
# Extracted verbatim from the Sage Claude Code adapter's
#   runtime/platforms/claude-code/hooks/sage-verify-tracker.sh
# by runtime/platforms/community/minimax-code/setup/extract_gates.py
#
# The gate logic below is upstream's, unmodified. The only changes are the
# enumerated P1-P4 patches applied at build time; see setup/extract_gates.py
# for what each one is and why. Upstream SHA-256: d4a5ecfa5a30619a
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
import sys
import time

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
if not isinstance(data, dict):
    sys.exit(0)

project_root = (os.environ.get("MINIMAX_PROJECT_DIR")
                or os.environ.get("CLAUDE_PROJECT_DIR")
                or (data.get("cwd") or "").strip() or os.getcwd())
project_root = os.path.abspath(project_root)
sage_dir = os.path.join(project_root, ".sage")
if not os.path.isdir(sage_dir):
    sys.exit(0)

tool = data.get("tool_name") or ""
tool_input = data.get("tool_input") or {}
session_id = str(data.get("session_id") or "")

CODE_EXT = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
            ".java", ".rb", ".dart", ".c", ".cc", ".cpp", ".h", ".swift", ".kt")
TEST_CMD = re.compile(
    r"\b(pytest|unittest|go\s+test|cargo\s+test|flutter\s+test|"
    r"npm\s+(run\s+)?test|npx\s+(vitest|jest|mocha)|vitest|jest|mocha|"
    r"sage-verify(\.sh)?)\b")

key = None
if tool in ("edit", "write", "Edit", "Write", "MultiEdit", "NotebookEdit"):
    path = str(tool_input.get("file_path") or tool_input.get("path") or "")
    rel = path.replace("\\", "/")
    # Sage machinery and docs are not source; a test file IS source here —
    # a freshly written test needs running exactly as much as the code does.
    if rel.endswith(CODE_EXT) and not any(
            seg in ("/.sage/", "/sage/", "/.claude/", "/node_modules/")
            for seg in ["/" + p + "/" for p in rel.split("/")[:-1]]):
        key = "last_source_edit"
elif tool == "Bash":
    if TEST_CMD.search(str(tool_input.get("command") or "")):
        key = "last_test_run"

if key is None:
    sys.exit(0)

tmp_dir = os.path.join(sage_dir, "tmp")
state_path = os.path.join(tmp_dir, "verify-state")
try:
    os.makedirs(tmp_dir, exist_ok=True)
    state = {}
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if "=" in line:
                    k, _, v = line.strip().partition("=")
                    state[k] = v
    state[key] = str(int(time.time() * 1000))
    if session_id:
        state[key.replace("_run", "").replace("_edit", "") + "_session"] = session_id
    with open(state_path, "w", encoding="utf-8") as fh:
        for k, v in sorted(state.items()):
            fh.write(f"{k}={v}\n")
except OSError:
    pass
sys.exit(0)
