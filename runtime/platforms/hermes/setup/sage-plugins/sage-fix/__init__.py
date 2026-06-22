"""sage-fix plugin — Sage fix workflow.

Registers the `/fix` slash command. The handler reads the sage workflow
markdown from ~/.sage/framework/core/workflows/fix.workflow.md and returns
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

_WORKFLOW_FILE = _SAGE_HOME / "core" / "workflows" / "fix.workflow.md"


def _load_workflow() -> str:
    """Return the fix workflow markdown, or a graceful fallback."""
    try:
        return _WORKFLOW_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            f"Sage workflow file not found at {_WORKFLOW_FILE}.\n"
            "Install sage framework to ~/.sage/framework/ or set SAGE_HOME."
        )
    except OSError as exc:
        return f"Could not read sage workflow: {exc}"


def _handle_fix(raw_args: str) -> str:
    """Handler for /fix — return the fix workflow text."""
    del raw_args
    return _load_workflow()


def register(ctx) -> None:
    """Register /fix slash command. Defensive try/except so a bad plugin
    does not disable siblings (per canon plugin guide)."""
    try:
        ctx.register_command(
            "fix",
            handler=_handle_fix,
            description='Debug and patch. Diagnose, test, fix, verify.',
        )
    except Exception as exc:  # pragma: no cover - defensive
        import logging
        logging.getLogger("sage-fix").exception("register failed: %s", exc)
