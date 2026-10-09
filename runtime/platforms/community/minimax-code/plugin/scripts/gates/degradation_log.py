#!/usr/bin/env python3
# GENERATED — do not edit by hand.
#
# Extracted verbatim from the Sage Claude Code adapter's
#   runtime/platforms/claude-code/hooks/sage-degradation-log.sh
# by runtime/platforms/community/minimax-code/setup/extract_gates.py
#
# The gate logic below is upstream's, unmodified. The only changes are the
# enumerated P1-P4 patches applied at build time; see setup/extract_gates.py
# for what each one is and why. Upstream SHA-256: 468bfe33a0ace10b
#
# Verdict contract, unchanged from Claude Code:
#   spec/secrets -> stdout "BLOCK\n<message>"   (also "ALLOW" / "WARN")
#   tdd          -> exit 2 with <message> on stderr
# pre_tool_gate.py translates either into the MiniMax deny JSON.
#
# Hooks fail OPEN. Any internal error must allow, never block, or one broken
# gate bricks the user's editor loop.
import datetime
import json
import os
import re
import sys

# Dispositions that mean "a capability that should have run, did not". Each maps
# to the sentence written into decisions.md.
DEGRADED = {
    "skipped-no-subagent":
        "auto-QA skipped (no sub-agent dispatch on this platform) — "
        "completion accepted without independent QA.",
    "skipped-disabled":
        "auto-QA skipped (auto_qa disabled in .sage/config.yaml) — "
        "completion accepted without independent QA.",
    "skipped-timeout":
        "auto-QA skipped (sub-agent timed out) — "
        "completion accepted without independent QA.",
    "waived":
        "auto-QA waived by the user — completion accepted without independent QA.",
}

MARK = "[auto-logged by sage-degradation-log]"

try:
    payload = json.load(sys.stdin)
except (ValueError, OSError):
    sys.exit(0)

tool_input = payload.get("tool_input") or {}
file_path = tool_input.get("file_path") or tool_input.get("path") or ""
if not file_path:
    sys.exit(0)

project_root = os.path.abspath(
    os.environ.get("MINIMAX_PROJECT_DIR")
    or os.environ.get("CLAUDE_PROJECT_DIR")
    or payload.get("cwd") or os.getcwd()
)
abspath = file_path if os.path.isabs(file_path) else os.path.join(project_root, file_path)
abspath = os.path.abspath(abspath)

# Only a cycle manifest under .sage/work/<slug>/manifest.md is interesting.
if os.path.basename(abspath) != "manifest.md":
    sys.exit(0)
sage_dir = os.path.join(project_root, ".sage")
work_root = os.path.normpath(os.path.join(sage_dir, "work"))
try:
    if os.path.commonpath([abspath, work_root]) != work_root:
        sys.exit(0)
except ValueError:
    sys.exit(0)

if not os.path.isfile(abspath):
    sys.exit(0)

try:
    with open(abspath, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
except OSError:
    sys.exit(0)

# The frontmatter block only — a `qa:` mentioned in prose is not a declaration.
m = re.match(r"^\s*---\s*\n(.*?)\n---\s*(\n|$)", text, re.S)
if not m:
    sys.exit(0)
fm = m.group(1)

qm = re.search(r"^\s*qa\s*:\s*\"?([A-Za-z0-9_-]+)\"?\s*(?:#.*)?$", fm, re.M)
if not qm:
    sys.exit(0)
disposition = qm.group(1).lower()
if disposition not in DEGRADED:
    sys.exit(0)          # `passed` / `pending` — nothing to record

slug = os.path.basename(os.path.dirname(abspath))
decisions = os.path.join(sage_dir, "decisions.md")

# Idempotent: this cycle's disposition is recorded once, not once per manifest edit.
key = 'cycle "%s"' % slug
try:
    with open(decisions, encoding="utf-8", errors="replace") as fh:
        existing = fh.read()
except OSError:
    existing = ""
for line in existing.splitlines():
    if MARK in line and key in line and disposition in line:
        sys.exit(0)

today = datetime.date.today().isoformat()
entry = '- [%s] %s — %s (%s) %s\n' % (
    today, key, DEGRADED[disposition], disposition, MARK,
)

try:
    if not os.path.isdir(sage_dir):
        sys.exit(0)                       # not a Sage project
    need_nl = bool(existing) and not existing.endswith("\n")
    with open(decisions, "a", encoding="utf-8") as fh:
        if need_nl:
            fh.write("\n")
        fh.write(entry)
except OSError:
    sys.exit(0)

# Surfaced on stderr so the degradation is visible in the session too, without
# depending on the model choosing to mention it.
sys.stderr.write(
    'Sage: recorded a degraded completion for cycle "%s" (%s) in '
    ".sage/decisions.md.\n" % (slug, disposition)
)
sys.exit(0)
