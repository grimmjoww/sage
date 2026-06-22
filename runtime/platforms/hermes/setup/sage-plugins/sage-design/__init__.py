"""sage-design plugin — Sage design workflow.

Registers the `/design` slash command. The handler reads the sage workflow
markdown from ~/.sage/framework/core/workflows/design.workflow.md and returns
its text content. Per the canon plugin guide (register-slash-commands),
the handler signature is `(raw_args: str) -> str`.
"""

from __future__ import annotations

import os
from pathlib import Path

# Resolve sage framework dir once at import time.
# ~/.sage/framework is the canonical install path; fall back to $SAGE_HOME
# for custom installs, and to the CWD-relative .sage/ for project-local work.
_SAGE_HOME = Path(
    os.environ.get("SAGE_HOME")
    or (Path.home() / ".sage" / "framework")
)

_WORKFLOW_FILE = _SAGE_HOME / "core" / "workflows" / "design.workflow.md"


def _load_workflow() -> str:
    """Return the sage workflow markdown, or a graceful fallback."""
    try:
        return _WORKFLOW_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            f"Sage workflow file not found at {_WORKFLOW_FILE}.\n"
            "Install sage framework to ~/.sage/framework/ or set SAGE_HOME."
        )
    except OSError as exc:
        return f"Could not read sage workflow: {exc}"


def _handle_design(raw_args: str) -> str:
    """Handler for /design — return the design workflow text."""
    del raw_args
    return _load_workflow()


def register(ctx) -> None:
    """Register /design slash command. Defensive try/except so a bad plugin
    does not disable siblings (per canon plugin guide)."""
    try:
        ctx.register_command(
            "design",
            handler=_handle_design,
            description="Product/UI design",
        )
    except Exception as exc:  # pragma: no cover - defensive
        import logging
        logging.getLogger("sage-design").exception("register failed: %s", exc)
