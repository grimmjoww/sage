#!/usr/bin/env python3
"""
validate_package.py — structural validation for the Sage MiniMax Code plugin.

One command, one `PASS <id>` / `FAIL <id>` line per check, because a gate
that can only report "the validator ran" is a gate that cannot fail.

Every rule here comes from the local Plugin V1 reference or the Hook wire
contract. Nothing is inferred from what "looks right": a path is checked to
exist, an icon is checked by its magic bytes rather than its extension, a
hook field is checked against the supported set rather than against the
document that describes it.

Usage:
  validate_package.py                 # all package checks
  validate_package.py --docs-only     # just the adapter-doc gate
  validate_package.py --installed     # also compare against the installed copy

Exit: 0 no failures · 1 at least one check failed
"""

from __future__ import annotations

import argparse
import ast
import filecmp
import json
import pathlib
import py_compile
import re
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ADAPTER = HERE.parent
PACKAGE = ADAPTER / "plugin"
INSTALLED = pathlib.Path(r"C:\Users\willi\.minimax\plugins\sage")

REQUIRED_MANIFEST_FIELDS = [
    "schemaVersion", "name", "version", "description", "author",
    "icon", "category", "exampleQueries", "apps", "mcpServers", "skills",
]
ALLOWED_CATEGORIES = {
    "Office", "Studio", "Design & Sites", "Code", "Business", "Sales",
    "Productivity", "Science & Healthcare", "Education", "Other",
}
SUPPORTED_EVENTS = {
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse",
    "PermissionRequest", "PostToolUse", "SubagentStart", "SubagentStop",
    "Stop", "PreCompact", "PostCompact",
}
ALLOWED_HANDLER_FIELDS = {"type", "command", "commandWindows", "timeout"}
REQUIRED_CAPABILITIES = {
    "context-injection", "command-delivery", "native-skill-discovery",
    "pre-tool-veto", "post-tool-events", "subagent-dispatch",
    "session-events", "context-injection-midstream",
}

RESULTS: list[tuple[bool, str, str]] = []

# Gates that are extracted and installed but that no adapter invokes.
#
# This set is an admission, not an exemption. The extractor ships nine gates
# because upstream has nine; the adapters route seven. The other two are
# PostToolUse observers whose host contract does not match the way
# post_tool_journal.py is built (it appends its own audit line and returns
# within the shared event budget, rather than spawning observers), so they are
# carried as staged source, not as running enforcement.
#
# Carrying them costs nothing at runtime and keeps the extraction mechanical —
# upstream is the reference, and a gate that upstream ships should be on disk
# to diff against. What it must never do is LOOK like coverage. So the check
# below requires this set to equal exactly (gates on disk) - (gates routed):
# add an unrouted gate and this check goes red; delete a staged gate from disk
# and it goes red too, because the admission is stale.
#
# If these are ever wired into a PostToolUse adapter, remove them here in the
# same commit — the check will confirm the routing before the entry is needed.
STAGED_GATES = {
    "degradation_log.py",
    "verify_tracker.py",
}


def record(ok: bool, check_id: str, desc: str) -> bool:
    RESULTS.append((ok, check_id, desc))
    return ok


def no_dup_keys(pairs):
    seen = {}
    for k, v in pairs:
        if k in seen:
            raise ValueError(f"duplicate key {k!r}")
        seen[k] = v
    return seen


def load_json(path: pathlib.Path):
    """Strict JSON: no BOM, no duplicate keys, object root only."""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError("file starts with a UTF-8 BOM")
    text = raw.decode("utf-8")
    data = json.loads(text, object_pairs_hook=no_dup_keys)
    if not isinstance(data, dict):
        raise ValueError(f"root is {type(data).__name__}, not an object")
    return data


# ── individual checks ──────────────────────────────────────────────────────

def check_json_parse() -> None:
    bad = []
    for jf in sorted(PACKAGE.rglob("*.json")):
        try:
            load_json(jf)
        except Exception as exc:
            bad.append(f"{jf.relative_to(PACKAGE)}: {exc}")
    record(not bad, "json-parse",
           f"{len(list(PACKAGE.rglob('*.json')))} JSON file(s) parse strictly"
           + ("" if not bad else f" — {'; '.join(bad)}"))


def check_manifest_fields() -> None:
    mf = PACKAGE / ".minimax-plugin" / "plugin.json"
    try:
        m = load_json(mf)
    except Exception as exc:
        record(False, "manifest-fields", f"manifest unreadable: {exc}")
        return
    problems = []
    for f in REQUIRED_MANIFEST_FIELDS:
        if f not in m:
            problems.append(f"missing {f}")
    if m.get("schemaVersion") != 1:
        problems.append(f"schemaVersion={m.get('schemaVersion')!r}, expected 1")
    if m.get("category") not in ALLOWED_CATEGORIES:
        problems.append(f"category={m.get('category')!r} not in the allowed set")
    if m.get("apps") != []:
        problems.append(f"apps={m.get('apps')!r}, Local App refs are ignored — must be []")
    if not re.match(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", str(m.get("name", ""))):
        problems.append(f"name={m.get('name')!r} does not match the required pattern")
    ver = str(m.get("version", ""))
    if not re.match(r"^\d+\.\d+\.\d+$", ver):
        problems.append(f"version={ver!r} is not SemVer")
    q = m.get("exampleQueries")
    if not isinstance(q, list) or not q or not all(
            isinstance(x, str) and x.strip() for x in q):
        problems.append("exampleQueries must be a non-empty list of non-blank strings")
    eff = len(m.get("mcpServers") or []) + len(m.get("skills") or []) + \
        len(m.get("hooks") or [])
    if eff == 0:
        problems.append("no MCP, Skill or Hook capability is effective")
    record(not problems, "manifest-fields",
           "all required fields present and valid" if not problems
           else "; ".join(problems))


def check_manifest_refs() -> None:
    mf = PACKAGE / ".minimax-plugin" / "plugin.json"
    try:
        m = load_json(mf)
    except Exception as exc:
        record(False, "manifest-refs", f"manifest unreadable: {exc}")
        return
    problems = []
    refs = [m.get("icon"), m.get("darkIcon")]
    for key in ("mcpServers", "skills", "hooks"):
        refs += m.get(key) or []
    for r in refs:
        if not r:
            continue
        s = str(r)
        if "\\" in s:
            problems.append(f"{s}: backslash, manifests use / separators")
        if s.startswith("/") or ".." in s.split("/"):
            problems.append(f"{s}: absolute or escaping path")
        if not (PACKAGE / s).is_file():
            problems.append(f"{s}: referenced file does not exist")
    record(not problems, "manifest-refs",
           f"{len([r for r in refs if r])} manifest reference(s) resolve"
           if not problems else "; ".join(problems))


def check_icons() -> None:
    problems = []
    n = 0
    for name in ("icon.png", "icon-dark.png"):
        p = PACKAGE / name
        if not p.is_file():
            problems.append(f"{name} missing")
            continue
        n += 1
        head = p.read_bytes()[:8]
        if head != b"\x89PNG\r\n\x1a\n":
            problems.append(f"{name} is not a PNG (magic bytes {head!r})")
    record(not problems, "icons",
           f"{n} icon(s) are real PNGs" if not problems else "; ".join(problems))


def check_hook_contract() -> None:
    hf = PACKAGE / "hooks" / "hooks.json"
    try:
        doc = load_json(hf)
    except Exception as exc:
        record(False, "hook-contract", f"hooks.json unreadable: {exc}")
        return
    problems = []
    groups = doc.get("hooks")
    if not isinstance(groups, dict):
        record(False, "hook-contract", "hooks is not an object")
        return
    total = 0
    for event, matchers in groups.items():
        if event not in SUPPORTED_EVENTS:
            problems.append(f"unsupported event {event!r}")
            continue
        for matcher in matchers:
            handlers = matcher.get("hooks") or []
            total += len(handlers)
            for h in handlers:
                if h.get("type") != "command":
                    problems.append(f"{event}: handler type {h.get('type')!r} "
                                    "is not a synchronous command")
                extra = set(h) - ALLOWED_HANDLER_FIELDS
                if extra:
                    problems.append(f"{event}: unsupported field(s) {sorted(extra)}")
                if not h.get("command"):
                    problems.append(f"{event}: empty command")
                t = h.get("timeout")
                if t is not None and (not isinstance(t, int) or not 1 <= t <= 10):
                    problems.append(f"{event}: timeout {t!r} outside 1..10")
                for f in ("command", "commandWindows"):
                    if f in h and "${PLUGIN_ROOT}" not in h[f]:
                        problems.append(f"{event}: {f} does not use ${{PLUGIN_ROOT}}")
    if total > 64:
        problems.append(f"{total} handlers exceeds the 64-handler ceiling")
    record(not problems, "hook-contract",
           f"{len(groups)} event(s), {total} handler(s), all contract-clean"
           if not problems else "; ".join(problems))


def check_interpreter() -> None:
    """The path named in commandWindows must actually resolve on THIS box."""
    hf = PACKAGE / "hooks" / "hooks.json"
    doc = load_json(hf)
    problems = []
    seen = 0
    for matchers in doc["hooks"].values():
        for matcher in matchers:
            for h in matcher.get("hooks") or []:
                cmd = h.get("commandWindows")
                if not cmd:
                    continue
                exe = re.match(r'^"([^"]+)"', cmd)
                if not exe:
                    problems.append(f"commandWindows is not quoted: {cmd!r}")
                    continue
                seen += 1
                if not pathlib.Path(exe.group(1)).is_file():
                    problems.append(f"interpreter missing: {exe.group(1)}")
    record(not problems and seen > 0, "interpreter",
           f"{seen} commandWindows interpreter(s) resolve"
           if not problems else "; ".join(problems))


def check_compiles() -> None:
    problems = []
    files = sorted(PACKAGE.rglob("*.py"))
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="sage-pyc-"))
    try:
        for f in files:
            try:
                py_compile.compile(str(f), cfile=str(tmp / (f.stem + ".pyc")),
                                   doraise=True)
            except py_compile.PyCompileError as exc:
                problems.append(f"{f.relative_to(PACKAGE)}: {exc}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    record(not problems, "compiles",
           f"{len(files)} script(s) compile"
           if not problems else "; ".join(problems[:3]))


def check_skill_frontmatter() -> None:
    problems = []
    n = 0
    for skill_md in sorted(PACKAGE.glob("skills/*/SKILL.md")):
        n += 1
        dirname = skill_md.parent.name
        text = skill_md.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        if not m:
            problems.append(f"{dirname}: no YAML frontmatter")
            continue
        name = re.search(r"^name\s*:\s*(.+?)\s*$", m.group(1), re.M)
        desc = re.search(r"^description\s*:\s*(.+?)\s*$", m.group(1), re.M | re.S)
        if not name or name.group(1).strip().strip('"') != dirname:
            problems.append(f"{dirname}: frontmatter name != directory name")
        if not desc or not desc.group(1).strip():
            problems.append(f"{dirname}: empty description")
    record(not problems and n > 0, "skill-frontmatter",
           f"{n} skill(s) have matching frontmatter"
           if not problems else "; ".join(problems))


# Credential shapes worth catching in a package that will be committed.
SECRET_PATTERNS = [
    (r"sk-[A-Za-z0-9]{20,}", "openai-style key"),
    (r"sk-ant-[A-Za-z0-9_-]{20,}", "anthropic key"),
    (r"gh[pousr]_[A-Za-z0-9]{20,}", "github token"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "slack token"),
    (r"AKIA[0-9A-Z]{16}", "aws access key id"),
    (r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b", "telegram bot token"),
]


def check_no_secrets() -> None:
    hits = []
    for f in PACKAGE.rglob("*"):
        if not f.is_file() or f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pattern, label in SECRET_PATTERNS:
            for m in re.finditer(pattern, text):
                hits.append(f"{f.relative_to(PACKAGE)}: {label}")
    record(not hits, "no-secrets",
           "no credential-shaped literal in the package"
           if not hits else "; ".join(sorted(set(hits))[:5]))


def _package_files(root: pathlib.Path) -> set[str]:
    """Package-relative files, excluding build artefacts.

    `__pycache__` appears the moment anyone imports or byte-compiles a script
    from the package, including the proof harnesses. It is not package
    content, it is not installed, and letting it into this comparison made
    the file-set check short-circuit before the content check ran — so a
    genuinely stale install could report only "a .pyc is missing".
    """
    out = set()
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if "__pycache__" in p.parts or p.suffix == ".pyc":
            continue
        out.add(str(p.relative_to(root)))
    return out


def check_install() -> None:
    if not INSTALLED.is_dir():
        record(False, "install-match", f"{INSTALLED} does not exist")
        return
    src_files = _package_files(PACKAGE)
    dst_files = _package_files(INSTALLED)

    problems = []
    only_src = sorted(src_files - dst_files)
    only_dst = sorted(dst_files - src_files)
    if only_src:
        problems.append(f"missing from install: {only_src}")
    if only_dst:
        problems.append(f"extra in install: {only_dst}")

    # Report content drift even when the file sets differ. A set mismatch is
    # not a reason to stop looking — the files that ARE in both are exactly
    # where a stale adapter hides.
    common = sorted(src_files & dst_files)
    differing = [rel for rel in common
                 if not filecmp.cmp(PACKAGE / rel, INSTALLED / rel, shallow=False)]
    if differing:
        problems.append(f"content differs: {differing}")

    record(not problems, "install-match",
           "; ".join(problems) if problems else
           f"{len(src_files)} file(s) installed and byte-identical")


def _routed_gate_filenames() -> set[str]:
    """Gate filenames any adapter can actually execute, read from the adapters
    themselves rather than from a second hand-maintained list.

    Two sources, because two adapters exist:
      * pre_tool_gate.py   — AST-walks its routing tables and collects the
                             gate filename from each entry tuple.
      * post_tool_journal.py — any string literal naming a file in gates/.
    """
    found: set[str] = set()
    gate_dir = PACKAGE / "scripts" / "gates"

    pre = PACKAGE / "scripts" / "pre_tool_gate.py"
    if pre.is_file():
        try:
            tree = ast.parse(pre.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            print(f"FAIL: could not parse {pre.name}: {exc}", file=sys.stderr)
            return found
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if not any(n.endswith("_GATES") or n == "EDIT_GATES"
                       for n in names):
                continue
            if not isinstance(node.value, (ast.List, ast.Tuple)):
                continue
            for entry in node.value.elts:
                if not isinstance(entry, (ast.List, ast.Tuple)):
                    continue
                for elt in entry.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        if (gate_dir / elt.value).is_file():
                            found.add(elt.value)

    journal = PACKAGE / "scripts" / "post_tool_journal.py"
    if journal.is_file():
        try:
            tree = ast.parse(journal.read_text(encoding="utf-8"))
        except SyntaxError:
            tree = ast.walk(ast.parse(""))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value.endswith(".py") and (gate_dir / node.value).is_file():
                    found.add(node.value)

    return found


def check_gate_routing() -> None:
    """Every extracted gate must be reachable from some adapter.

    Why this check exists
    ---------------------
    The extractor emits nine gates; the adapters route seven. Nothing compared
    the two, so a gate could be generated, compiled, installed, and never
    execute — which is the shape of every gate in this port that looked
    installed and enforced nothing. "It compiles" is not the property.
    "Something runs it" is.
    """
    gate_dir = PACKAGE / "scripts" / "gates"
    if not gate_dir.is_dir():
        record(False, "gate-routing", f"no gate directory at {gate_dir}")
        return

    on_disk = {p.name for p in gate_dir.glob("*.py")}
    routed = _routed_gate_filenames()
    unrouted = sorted(on_disk - routed)

    problems = []
    if not routed:
        problems.append("no adapter references any gate — routing is empty")
    if set(unrouted) != STAGED_GATES:
        extra = sorted(set(unrouted) - STAGED_GATES)
        stale = sorted(STAGED_GATES - set(unrouted))
        if extra:
            problems.append(f"unrouted and undeclared: {extra}")
        if stale:
            problems.append(f"declared staged but actually routed or gone: {stale}")

    staged_note = f"; staged-not-routed (declared): {sorted(STAGED_GATES)}" \
        if STAGED_GATES else ""
    record(not problems, "gate-routing",
           "; ".join(problems) if problems else
           f"{len(routed)}/{len(on_disk)} gate(s) routed by an adapter"
           f"{staged_note}")


def check_docs() -> None:
    required = ["platform.yaml", "README.md", "INSTALL.md"]
    missing = [f for f in required if not (ADAPTER / f).is_file()]
    if missing:
        record(False, "docs-ok", f"missing: {missing}")
    else:
        record(True, "docs-ok",
               f"{len(required)} required adapter doc(s) present")


def check_contract() -> None:
    """platform.yaml must declare all eight capabilities — silence is not an
    answer — and must name a maintainer. Parsed with regexes on purpose: a
    PyYAML dependency would make validating this contract depend on the very
    thing the contract describes."""
    py = ADAPTER / "platform.yaml"
    if not py.is_file():
        record(False, "contract-ok", "platform.yaml missing")
        return
    text = py.read_text(encoding="utf-8")

    problems = []
    m = re.search(r"^contract-version:\s*(\d+)\s*$", text, re.M)
    if not m or m.group(1) != "2":
        problems.append(f"contract-version is {m.group(1) if m else None!r}, expected 2")

    caps_block = re.search(r"^capabilities:\s*\n((?:\s+\S.*\n?)+)", text, re.M)
    declared = {}
    if caps_block:
        for line in caps_block.group(1).splitlines():
            cm = re.match(r"^\s+([a-z-]+)\s*:\s*(true|false|attested)\s*$", line)
            if cm:
                declared[cm.group(1)] = cm.group(2)
    missing = REQUIRED_CAPABILITIES - set(declared)
    extra = set(declared) - REQUIRED_CAPABILITIES
    if missing:
        problems.append(f"undeclared capability/capabilities: {sorted(missing)}")
    if extra:
        problems.append(f"unknown capability key(s): {sorted(extra)}")

    if not re.search(r'^maintainer:\s*"?.+"?\s*$', text, re.M):
        problems.append("no maintainer — nobody answers when conformance goes red")

    # Every `attested` needs an attestation block; none are declared here, so
    # an attestation section without a matching capability would be a lie.
    attested = {k for k, v in declared.items() if v == "attested"}
    for cap in sorted(attested):
        if not re.search(rf"^\s*-\s*capability:\s*{cap}\s*$", text, re.M):
            problems.append(f"{cap} is `attested` with no attestation block")

    if problems:
        record(False, "contract-ok", "; ".join(problems))
    else:
        record(True, "contract-ok",
               f"{len(declared)} capabilities declared, maintainer named")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs-only", action="store_true")
    ap.add_argument("--contract-only", action="store_true")
    ap.add_argument("--installed", action="store_true")
    args = ap.parse_args()

    if args.docs_only or args.contract_only:
        if args.contract_only:
            check_contract()
        if args.docs_only:
            check_docs()
        ok = all(r[0] for r in RESULTS)
        print(f"\n  {'OK' if ok else 'FAIL'} — {sum(1 for r in RESULTS if r[0])}"
              f"/{len(RESULTS)}")
        return 0 if ok else 1

    if not PACKAGE.is_dir():
        print(f"FAIL: package dir missing: {PACKAGE}", file=sys.stderr)
        return 1

    check_json_parse()
    check_manifest_fields()
    check_manifest_refs()
    check_icons()
    check_hook_contract()
    check_interpreter()
    check_compiles()
    check_gate_routing()
    check_skill_frontmatter()
    check_no_secrets()
    check_docs()
    check_contract()
    if args.installed:
        check_install()

    for ok, cid, desc in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'} {cid} — {desc}")

    passed = sum(1 for r in RESULTS if r[0])
    print(f"\n  {passed}/{len(RESULTS)} checks passed")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
