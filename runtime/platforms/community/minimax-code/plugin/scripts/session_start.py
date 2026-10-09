#!/usr/bin/env python3
"""
session_start.py — MiniMax Code `SessionStart` context injection.

Ported from runtime/platforms/claude-code/hooks/sage-session-init.sh, which is
the one hook in the Claude adapter with no Python inside it: 170 lines of bash
doing git locking, a frontmatter scan, and a printf. Rewritten rather than
extracted, because there was nothing to extract.

Below `context-injection` Sage cannot run at all — every other capability is
downstream of the model knowing a cycle is in flight. So this hook is the one
that has to be boring and always work.

Two deliberate differences from the Claude original
--------------------------------------------------
1. The collision lock is keyed on the host's `session_id`, not `$PPID`.
   In Claude the hook's parent process was the session. In MiniMax the hook's
   parent is the app process, shared by every session — so `$PPID` would make
   every concurrent session look like a collision with itself. `session_id`
   is supplied on stdin and actually identifies the session. This is a fix,
   not a downgrade.

2. No `kill -0` liveness probe. That is POSIX; on Windows it does not mean
   what the Claude hook assumes. The lock is a WARNING and never blocks, so
   the staleness window alone is sufficient. A stale lock costs a line of
   output; a wrong `os.kill` on Windows can do worse.

Output is `hookSpecificOutput.additionalContext`, or nothing at all when the
project is not a Sage project. Silence is the correct answer for most repos.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import time

STALE_SECONDS = 21600  # 6h backstop, matching the Claude hook


def read_text(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def frontmatter(text: str, key: str) -> str:
    """Pull `key:` out of a leading --- fenced block, as the bash did with sed."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return ""
    km = re.search(rf'^\s*{key}\s*:\s*"?(.*?)"?\s*$', m.group(1), re.M)
    return km.group(1).strip() if km else ""


def git_toplevel(root: pathlib.Path) -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                             cwd=root, capture_output=True, timeout=5)
        if out.returncode == 0:
            return out.stdout.decode("utf-8", "replace").strip() or None
    except (OSError, subprocess.SubprocessError):
        pass
    return None


def collision_note(sage_dir: pathlib.Path, root: pathlib.Path,
                    session_id: str) -> str:
    """Warn — never block — when another session owns this checkout."""
    if git_toplevel(root) is None:
        return ""  # non-git: never claim a collision off a missing git

    lock = sage_dir / ".session-lock"
    existing = read_text(lock)
    if not existing.strip():
        return ""

    fields = dict(
        line.split("=", 1) for line in existing.splitlines() if "=" in line
    )
    owner = fields.get("session_id", "").strip()
    if not owner or owner == session_id:
        return ""

    try:
        updated = int(fields.get("updated_at", "0") or 0)
    except ValueError:
        updated = 0
    if updated and (time.time() - updated) > STALE_SECONDS:
        return ""  # stale: ignore and take the lock below

    return (
        "Sage: another Sage session appears active in this checkout "
        f"(session {owner[:12]}). Two sessions in one working tree overwrite "
        "each other's artifacts. Use a worktree for an isolated session."
    )


def claim_lock(sage_dir: pathlib.Path, session_id: str) -> None:
    lock = sage_dir / ".session-lock"
    try:
        lock.write_text(
            f"session_id={session_id}\nupdated_at={int(time.time())}\n",
            encoding="utf-8")
    except OSError:
        pass  # a read-only .sage/ must not break the session
    # Keep the lock out of git, matching the Claude hook.
    gi = sage_dir / ".gitignore"
    try:
        existing = read_text(gi)
        if ".session-lock" not in existing.split():
            with gi.open("a", encoding="utf-8") as fh:
                if existing and not existing.endswith("\n"):
                    fh.write("\n")
                fh.write(".session-lock\n")
    except OSError:
        pass


def build_context(sage_dir: pathlib.Path, root: pathlib.Path,
                  session_id: str) -> str:
    lines: list[str] = []
    note = collision_note(sage_dir, root, session_id)
    if note:
        lines += [note, ""]

    work = sage_dir / "work"
    active: list[str] = []
    in_progress = ""
    if work.is_dir():
        for cycle in sorted(p for p in work.iterdir() if p.is_dir()):
            for artifact in ("plan.md", "spec.md", "brief.md"):
                f = cycle / artifact
                if not f.is_file():
                    continue
                text = read_text(f)
                title = frontmatter(text, "title") or cycle.name
                status = frontmatter(text, "status") or "unknown"
                phase = frontmatter(text, "phase")
                active.append(
                    f"- {title} [{status}{', ' + phase if phase else ''}] "
                    f"— .sage/work/{cycle.name}/{artifact}")
                if status == "in-progress":
                    in_progress = title
                break

    if active:
        if in_progress:
            lines.append(f"Sage: {in_progress} is in progress.")
            lines.append("")
        lines.append(f"Active work ({len(active)}):")
        lines += active
    else:
        lines.append("Sage: No active work. Ready for a new task.")

    docs = sage_dir / "docs"
    if docs.is_dir():
        n = sum(1 for p in docs.glob("*.md") if p.is_file())
        if n:
            lines.append("")
            lines.append(f"Project docs: {n} files in .sage/docs/")

    decisions = read_text(sage_dir / "decisions.md")
    recent = [ln for ln in decisions.splitlines() if ln.startswith("### ")][-3:]
    if recent:
        lines.append("")
        lines.append("Recent decisions:")
        lines += recent

    lines.append("")
    lines.append("Sage is active. Load the sage-build / sage-fix / sage-architect "
                 "skill for the matching mode before writing code, and read the "
                 "constitution in .sage/ if present.")
    return "\n".join(lines)


def main() -> None:
    try:
        payload = json.loads(sys.stdin.buffer.read() or b"{}")
    except ValueError:
        sys.exit(0)
    if not isinstance(payload, dict):
        sys.exit(0)

    root = pathlib.Path(
        os.environ.get("MINIMAX_PROJECT_DIR")
        or (payload.get("cwd") or "").strip()
        or os.getcwd()
    )
    sage_dir = root / ".sage"
    if not sage_dir.is_dir():
        sys.exit(0)  # not a Sage project — say nothing

    session_id = (payload.get("session_id") or "").strip() or "unknown"
    context = build_context(sage_dir, root, session_id)
    claim_lock(sage_dir, session_id)

    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
