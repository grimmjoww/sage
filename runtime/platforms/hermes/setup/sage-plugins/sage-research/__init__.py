"""sage-research plugin — Sage research workflow.

Registers the `/research` slash command. The handler reads the sage workflow
markdown from ~/.sage/framework/core/workflows/research.workflow.md and returns
its text content. Per the canon plugin guide (register-slash-commands),
the handler signature is `(raw_args: str) -> str`.
"""

from __future__ import annotations

import os
from pathlib import Path

_SAGE_HOME = Path(
    os.environ.get("SAGE_HOME")
    or (Path.home() / ".sage" / "framework")
)

_WORKFLOW_FILE = _SAGE_HOME / "core" / "workflows" / "research.workflow.md"


def _load_workflow() -> str:
    """Return the research workflow markdown, or a graceful fallback."""
    try:
        return _WORKFLOW_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            f"Sage workflow file not found at {_WORKFLOW_FILE}.\n"
            "Install sage framework to ~/.sage/framework/ or set SAGE_HOME."
        )
    except OSError as exc:
        return f"Could not read sage workflow: {exc}"


def _handle_research(raw_args: str) -> str:
    """Handler for /research — return the research workflow text."""
    del raw_args
    return _load_workflow()


def register(ctx) -> None:
    """Register /research slash command. Defensive try/except so a bad plugin
    does not disable siblings (per canon plugin guide)."""
    try:
        ctx.register_command(
            "research",
            handler=_handle_research,
            description="Research and analysis",
        )
    except Exception as exc:  # pragma: no cover - defensive
        import logging
        logging.getLogger("sage-research").exception("register failed: %s", exc)
