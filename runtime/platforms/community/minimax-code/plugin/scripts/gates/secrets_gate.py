#!/usr/bin/env python3
# GENERATED — do not edit by hand.
#
# Extracted verbatim from the Sage Claude Code adapter's
#   runtime/platforms/claude-code/hooks/sage-secrets-gate.sh
# by runtime/platforms/community/minimax-code/setup/extract_gates.py
#
# The gate logic below is upstream's, unmodified. The only changes are the
# enumerated P1-P4 patches applied at build time; see setup/extract_gates.py
# for what each one is and why. Upstream SHA-256: 8eec59ddceb028a7
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

tool_input = data.get("tool_input") or {}
# P2: Claude sends "file_path"; MiniMax sends "path". Accept both.
file_path = (tool_input.get("file_path")
             or tool_input.get("path") or "").strip()
if not file_path:
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
                m = re.match(r"\s*secrets_gate\s*:\s*false\b", line, re.I)
                if m:
                    gate_off = True
    except OSError:
        pass
if enforce is not True or gate_off:
    emit("ALLOW")

rel = os.path.relpath(
    file_path if os.path.isabs(file_path)
    else os.path.join(project_root, file_path), project_root).replace("\\", "/")
base = os.path.basename(rel)
parts = rel.split("/")

# New content: Write carries `content`; Edit carries `new_string`; MultiEdit a
# list of edits. Concatenate whatever is present.
blobs = []
for key in ("content", "new_string"):
    v = tool_input.get(key)
    if isinstance(v, str):
        blobs.append(v)
for e in tool_input.get("edits") or []:
    if isinstance(e, dict) and isinstance(e.get("new_string"), str):
        blobs.append(e["new_string"])
text = "\n".join(blobs)
if not text:
    emit("ALLOW")


def block(what):
    emit("BLOCK", (
        "sage-secrets-gate: this edit hardcodes %s into %s — credentials "
        "never go into files (constitution: secrets).\n"
        "\n"
        "Instead: read it from the environment (os.environ / process.env) "
        "or a gitignored config (.env), and reference the variable here. "
        "If a placeholder is genuinely needed, use an obvious fake like "
        "\"YOUR_API_KEY\"." % (what, rel)))


# ── Class 1: LIVE-marked keys — blocked EVERYWHERE except .env*. ──
# The weak-model proof run caught the gap: E2's key (pfk_live_…) is a fictional
# vendor prefix no provider list can anticipate, and one run parked it in
# tests/ — which the source-only class exempts for FAKE fixtures. A key that
# says live/prod/secret in its own name is not a fixture: `live` means live,
# and it belongs in .env or nowhere. (sk_test_-style keys stay in class 2 —
# vendors design those for code and CI.)
if not (base.startswith(".env") or base == ".gitignore"):
    m = re.search(r"\b[A-Za-z]{2,8}_(?:live|prod|secret)_[A-Za-z0-9]{12,}", text)
    if m:
        block("a live-marked key (%s…)" % m.group(0)[:12])
    if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", text):
        block("a private key block")

# ── Class 2: provider-shaped tokens — blocked in SOURCE only. ──
# Placeholder-shaped fakes are legitimate in tests/fixtures/examples and docs;
# a guard with false positives is a guard people disable.
if base.startswith(".env") or base.endswith((".md", ".txt", ".lock", ".pem.example")):
    emit("ALLOW")
if any(p in ("examples", "fixtures", "tests", "test", ".sage", "sage",
             ".claude", "node_modules") for p in parts):
    emit("ALLOW")

PATTERNS = [
    (r"\bsk-[A-Za-z0-9_-]{16,}", "an sk-… API key"),
    (r"\bsk-ant-[A-Za-z0-9_-]{16,}", "an Anthropic API key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "an AWS access key id"),
    (r"\bgh[pos]_[A-Za-z0-9]{20,}", "a GitHub token"),
    (r"\bgithub_pat_[A-Za-z0-9_]{20,}", "a GitHub fine-grained token"),
    (r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "a Slack token"),
    (r"\bAIza[0-9A-Za-z_-]{30,}", "a Google API key"),
]
for pat, what in PATTERNS:
    if re.search(pat, text):
        block(what)

emit("ALLOW")
