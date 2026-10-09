#!/usr/bin/env python3
# GENERATED — do not edit by hand.
#
# Extracted verbatim from the Sage Claude Code adapter's
#   runtime/platforms/claude-code/hooks/sage-bookkeeping-gate.sh
# by runtime/platforms/community/minimax-code/setup/extract_gates.py
#
# The gate logic below is upstream's, unmodified. The only changes are the
# enumerated P1-P4 patches applied at build time; see setup/extract_gates.py
# for what each one is and why. Upstream SHA-256: 2ce1e801b48d560f
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

# Same master switch as the spec gate, plus a dedicated opt-out.
enforce = None
gate_off = False
config_path = os.path.join(sage_dir, "config.yaml")
if os.path.isfile(config_path):
    try:
        with open(config_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                # FIRST occurrence wins — the config-gate's reader convention.
                # A last-wins read here let an appended duplicate
                # `hard_enforcement: false` silence THIS gate (the scope
                # block's guard) while the first-wins gates stayed armed.
                m = re.match(r"\s*hard_enforcement\s*:\s*(true|false)\b", line, re.I)
                if m and enforce is None:
                    enforce = (m.group(1).lower() == "true")
                m = re.match(r"\s*bookkeeping_gate\s*:\s*false\b", line, re.I)
                if m:
                    gate_off = True
    except OSError:
        pass
if enforce is not True or gate_off:
    emit("ALLOW")

# Only a cycle's manifest.md / decisions.md, and only if it already exists.
abspath = (file_path if os.path.isabs(file_path)
           else os.path.join(project_root, file_path))
abspath = os.path.abspath(abspath)
rel = os.path.relpath(abspath, project_root).replace("\\", "/")
m = re.match(r"^\.sage/work/([^/]+)/(manifest\.md|decisions\.md)$", rel)
if not m:
    emit("ALLOW")
if not os.path.isfile(abspath):
    emit("ALLOW")          # creation is authoring, not bookkeeping

# Only while that cycle is ACTIVE (a post-mortem edit of a dead cycle is fine).
manifest_path = os.path.join(project_root, ".sage", "work", m.group(1), "manifest.md")
status = None
try:
    with open(manifest_path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    fm = re.match(r"^\s*---\s*\n(.*?)\n---\s*(?:\n|$)", text.lstrip("﻿"), re.S)
    if fm:
        sm = re.search(r"^status\s*:\s*\"?([A-Za-z-]+)", fm.group(1), re.M)
        status = sm.group(1).lower() if sm else None
except OSError:
    pass
if status in ("complete", "completed", "abandoned"):
    emit("ALLOW")

# gate_state transitions are APPROVAL flow, not bookkeeping — the spec-gate's
# completion guard already polices them (QA field, ledger). Blocking them here
# would strand a cycle that legitimately needs to record gates-passed. Yield —
# but NOT for an edit that also touches the scope or task_graph block: merely
# mentioning `gate_state` in the payload must not become a skeleton key for
# widening `scope:` — or rewiring `task_graph:` dependencies (A8: a hand-cut
# edge dispatches coupled tasks into concurrent lanes) — by hand (independent
# review, confirmed by probe). Both blocks are amended through
# `manifest.py scope …` / `manifest.py graph derive`, which write via Bash
# and never meet this gate.
#
# "Touches the block" is decided by RECONSTRUCTION, not substrings
# (the config-gate's pattern): apply the edit, parse the section
# before and after, compare. A structure-key regex was probed twice and
# lost both ways — prose saying "out of scope:" stranded legit transitions,
# and a widening that adds only a list item (`    - src/**`) carries no
# structure key at all (round-3 review, confirmed). A Write replaces the
# whole file, so for Write the yield requires the content to carry NO scope
# or task_graph block — a full-manifest rewrite is bookkeeping whatever
# else it says.


# Section extraction is a LINE SCANNER, not a regex. Three regex
# generations each fell to the next counterexample (DOTALL captured to
# EOF; MULTILINE stopped at one blank line; the one-blank lookahead
# stopped at two, and its [ \t]-anchored `$` never matched CRLF headers
# at all — round-three F3/F4). The scanner's rule is the actual YAML
# shape: the block is every following line that is indented, plus any
# run of blank lines that is FOLLOWED by another indented line. Line
# endings are normalized for the decisions but preserved in the capture,
# so the before/after compare stays faithful on CRLF manifests.
def _block_section(text, key):
    lines = (text or "").splitlines(True)

    def bare(l):
        return l.rstrip("\r\n")

    # Column-0 header only — an INDENTED `  lanes:` nested inside another
    # block must not claim the section (round-four F5: the un-anchored
    # form let a planted decoy strand the real block un-guarded; guarded
    # blocks are top-level keys by construction, same rule as every
    # scalar reader).
    head = re.compile(r"^%s\s*:[ \t]*(?:#.*)?$" % key)
    start = next((i for i, l in enumerate(lines) if head.match(bare(l))),
                 None)
    if start is None:
        return ""
    out = [lines[start]]
    j = start + 1
    while j < len(lines):
        b = bare(lines[j])
        if b.strip() == "":
            k = j
            while k < len(lines) and bare(lines[k]).strip() == "":
                k += 1
            if k < len(lines) and re.match(r"^[ \t]+\S", bare(lines[k])):
                out.extend(lines[j:k])
                j = k
                continue
            break
        if re.match(r"^[ \t]+", b):
            out.append(lines[j])
            j += 1
            continue
        break
    return "".join(out)


def scope_section(text):
    return _block_section(text, "scope")


def graph_section(text):
    return _block_section(text, "task_graph")


def lanes_section(text):
    return _block_section(text, "lanes")


def guarded_sections(text):
    return "\x00".join((scope_section(text), graph_section(text),
                        lanes_section(text)))


edit_texts = []
if isinstance(tool_input.get("content"), str):
    edit_texts.append(tool_input["content"])
for key in ("old_string", "new_string"):
    if isinstance(tool_input.get(key), str):
        edit_texts.append(tool_input[key])
for e in (tool_input.get("edits") or []):
    if isinstance(e, dict):
        for key in ("old_string", "new_string"):
            if isinstance(e.get(key), str):
                edit_texts.append(e[key])
edit_text = "\n".join(edit_texts)

if "gate_state" in edit_text:
    tool = data.get("tool_name") or ""
    if tool in ("Write", "write"):
        content = str(tool_input.get("content") or "")
        if not (scope_section(content) or graph_section(content)
                or lanes_section(content)):
            emit("ALLOW")
    else:
        try:
            with open(abspath, encoding="utf-8", errors="replace") as fh:
                current = fh.read()
        except OSError:
            current = ""
        after = current
        edits = tool_input.get("edits")
        if not edits and "new_string" in tool_input:
            edits = [{"old_string": tool_input.get("old_string", ""),
                      "new_string": tool_input.get("new_string", "")}]
        for e in edits or []:
            if isinstance(e, dict) and e.get("old_string"):
                # Model the edit FAITHFULLY: replace_all replaces every
                # occurrence. The count=1 model let a replace_all edit whose
                # old_string also occurs above the guarded blocks mutate a
                # task_graph dependency edge while the gate compared an
                # unchanged reconstruction (independent review, finding 3).
                count = -1 if e.get("replace_all") else 1
                after = after.replace(e["old_string"],
                                      e.get("new_string", ""), count)
        if guarded_sections(current) == guarded_sections(after):
            emit("ALLOW")

emit("BLOCK", (
    "sage-bookkeeping-gate: don't hand-edit %s during an active cycle — apply "
    "the whole update in ONE pass instead (this is the close-out economy's "
    "bookkeeping rule, made mechanical):\n"
    "\n"
    "  python3 sage/runtime/tools/manifest.py close-out "
    ".sage/work/%s/manifest.md \\\n"
    "    --summary \"...\" --next-step \"...\" --decision \"...\" "
    "--complete-task N \\\n"
    "    [--phase X] [--status blocked --blocked-on \"the question, the "
    "options, whose call\"]\n"
    "\n"
    "One command writes the manifest prose, prepends decisions (Rule 7), and "
    "checks plan boxes. gate_state and updated: are machine-owned — never set "
    "them by hand. Compose everything first, then run it once."
    % (rel, m.group(1))
))
