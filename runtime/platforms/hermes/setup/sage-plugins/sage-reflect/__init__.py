"""sage-reflect plugin — Sage reflect workflow.

Registers the `/reflect` slash command. The handler reads the sage workflow
markdown from ~/.sage/framework/core/workflows/reflect.workflow.md and returns
its text content. Per the canon plugin guide (register-slash-commands),
the handler signature is `(raw_args: str) -> str`.
"""

from __future__ import annotations

import os
from pathlib import Path

# Resolve sage framework dir once at import time.
# ~/.sage/framework is the canonical install path; fall back to $SAGE_HOME
# for custom installs.
_SAGE_HOME = Path(
    os.environ.get("SAGE_HOME")
    or (Path.home() / ".sage" / "framework")
)

_WORKFLOW_FILE = _SAGE_HOME / "core" / "workflows" / "reflect.workflow.md"


def _load_workflow() -> str:
    """Return the reflect workflow markdown, or a graceful fallback."""
    try:
        return _WORKFLOW_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            f"Sage workflow file not found at {_WORKFLOW_FILE}.\n"
            "Install sage framework to ~/.sage/framework/ or set SAGE_HOME."
        )
    except OSError as exc:
        return f"Could not read sage workflow: {exc}"


def _handle_reflect(raw_args: str) -> str:
    """Handler for /reflect — return the reflect workflow text."""
    del raw_args  # /reflect takes no arguments; it scans completed work itself
    return _load_workflow()


def register(ctx) -> None:
    """Register /reflect slash command. Per canon, defensive try/except so a
    bad plugin does not disable siblings."""
    try:
        ctx.register_command(
            "reflect",
            handler=_handle_reflect,
            description=(
                "Session-end reflection."
            ),
        )
    except Exception as exc:  # pragma: no cover - defensive
        # Surface as a log; per canon (line 279) a crashing register() disables
        # the plugin, but Hermes continues.
        import logging
        logging.getLogger("sage-reflect").exception("register failed: %s", exc)
