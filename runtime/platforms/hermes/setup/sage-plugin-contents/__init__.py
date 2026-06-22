"""sage plugin — Hermetic Sage install.

This is a single plugin that bundles the full Sage ecosystem:
- 53 SKILL.md files (16 slash-command + 37 auto-loaded skills)
- 5 agent personas (analyst, architect, debugger, developer, reviewer)
- 10 reference templates (decision, spec, plan, manifest, etc.)
- plugin-internal hooks (hooks/hooks.json)
- a sage CLI wrapper (scripts/sage)

Per Hermes plugin guide (hermes-agent/docs/guides/build-a-hermes-plugin):
> Plugins can ship skill files that the agent loads via
> skill_view("plugin:skill"). Register them in your __init__.py:
>   def register(ctx):
>       skills_dir = Path(__file__).parent / "skills"
>       for child in sorted(skills_dir.iterdir()):
>           skill_md = child / "SKILL.md"
>           if child.is_dir() and skill_md.exists():
>               ctx.register_skill(child.name, skill_md)

Slash commands are SEPARATELY registered via ctx.register_command(name, handler, description).
The 16 SKILL.md files with `disable-model-invocation: true` in their frontmatter
become slash commands — the handler returns the SKILL.md content as a string.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger("sage")

# ── Plugin paths ──
_PLUGIN_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = _PLUGIN_DIR / "skills"
_AGENTS_DIR = _PLUGIN_DIR / "agents"
_REFERENCES_DIR = _PLUGIN_DIR / "references"
_HOOKS_DIR = _PLUGIN_DIR / "hooks"
_SCRIPTS_DIR = _PLUGIN_DIR / "scripts"

# ── Plugin version + metadata (mirror .claude-plugin/plugin.json) ──
__version__ = "1.0.9"
__author__ = "Rei Stewart (adapted from xoai/sage claude-code plugin)"
__description__ = (
    "AI skills framework: UNDERSTAND → ENVISION → DELIVER → REFLECT. "
    "Process enforcement, 14 workflows, 37 skills, 5 agent personas."
)


# ── Slash-command skill IDs (must match skills/<id>/SKILL.md names) ──
# These are the SKILL.md files that have disable-model-invocation: true in
# their frontmatter (per the canonical claude-plugin shape). Other 37 SKILL.md
# files in skills/ are auto-loaded as plain skills, not slash commands.
# sage-navigator is auto-loaded (user-invocable: false) — not a slash command.
SLASH_COMMAND_SKILLS = (
    "sage",
    "build",
    "fix",
    "architect",
    "analyze",
    "learn",
    "map",
    "qa",
    "reflect",
    "research",
    "review",
    "status",
    "design",
    "design-review",
    "continue",
)


def _read_skill_text(skill_id: str) -> str:
    """Read a SKILL.md and return its full text content.

    Slash-command handlers return this string to the user as the workflow
    body. Per the hermes shell-hook contract (agent/shell_hooks.py), this is
    plain text — Hermes appends it to the next user message context.
    """
    skill_md = _SKILLS_DIR / skill_id / "SKILL.md"
    try:
        return skill_md.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            f"Sage workflow file not found at {skill_md}.\n"
            "Install the sage plugin to ~/.hermes/plugins/sage/."
        )
    except OSError as exc:
        return f"Could not read sage workflow: {exc}"


def _handle_skill(skill_id: str, raw_args: str) -> str:
    """Generic slash-command handler factory: returns the SKILL.md body.

    Per hermes plugin guide, handler signature is (raw_args: str) -> str.
    The raw_args is everything typed after the slash command (e.g.
    `/build me a thing` → handler("me a thing")). Most sage workflows don't
    use it (the workflow body self-loads), but we accept it for forward compat.
    """
    del raw_args  # most sage workflows self-load from their body
    return _read_skill_text(skill_id)


def register(ctx) -> None:
    """Hermes plugin entry point — called once at plugin load time.

    Per the docs example: walk skills/ subdir, call ctx.register_skill()
    for each SKILL.md found. THEN register the 16 slash commands.
    """
    try:
        # ── 1. Discover + register all 53 skills in skills/ subdir ──
        if _SKILLS_DIR.is_dir():
            for child in sorted(_SKILLS_DIR.iterdir()):
                skill_md = child / "SKILL.md"
                if child.is_dir() and skill_md.exists():
                    try:
                        ctx.register_skill(child.name, skill_md)
                        logger.debug("Registered skill: %s", child.name)
                    except Exception as exc:
                        logger.warning(
                            "Failed to register skill %s: %s", child.name, exc
                        )

        # ── 2. Register slash commands for the 16 disable-model-invocation skills ──
        for skill_id in SLASH_COMMAND_SKILLS:
            handler = lambda args, _sid=skill_id: _handle_skill(_sid, args)
            description = _read_skill_description(skill_id) or f"/{skill_id} — sage workflow"
            try:
                ctx.register_command(
                    skill_id,
                    handler=handler,
                    description=description,
                )
                logger.debug("Registered slash command: /%s", skill_id)
            except Exception as exc:
                # Conflict-protection: built-in or already-registered names
                # are silently rejected. Don't crash the agent loop.
                logger.debug(
                    "Slash command /%s registration rejected: %s", skill_id, exc
                )

        logger.info(
            "Sage plugin v%s loaded: %d skills, %d slash commands",
            __version__,
            sum(1 for _ in _SKILLS_DIR.iterdir() if (_ / "SKILL.md").exists()) if _SKILLS_DIR.is_dir() else 0,
            len(SLASH_COMMAND_SKILLS),
        )
    except Exception as exc:
        # A misbehaving plugin must not break the agent loop. Log and skip.
        logger.exception("sage plugin register failed: %s", exc)


def _read_skill_description(skill_id: str) -> str | None:
    """Pull the `description:` line from a SKILL.md's frontmatter.

    Used as the slash-command's autocomplete/help description. Falls back to
    None if the file can't be read or has no description frontmatter.
    """
    skill_md = _SKILLS_DIR / skill_id / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    # Frontmatter is between the first pair of '---' lines
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    frontmatter = text[3:end]
    # First non-empty `description:` line, stripped of the YAML key
    in_block = False  # multi-line folded scalar 'description: >-'
    for line in frontmatter.splitlines():
        if line.startswith("description:"):
            val = line.split(":", 1)[1].strip().strip("'\"")
            if val == ">-":
                in_block = True
                continue
            return val if val else None
        if in_block:
            stripped = line.strip()
            if stripped:
                return stripped
    return None
