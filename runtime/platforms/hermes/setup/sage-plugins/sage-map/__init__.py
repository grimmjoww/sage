"""sage-map plugin — Sage map workflow.

Registers the ``/map`` slash command. The handler reads the sage workflow
markdown from ~/.sage/framework/core/workflows/map.workflow.md (with optional
SAGE_HOME env override) and returns its text content.

Per the canon plugin guide (register-slash-commands), the handler signature
is ``(raw_args: str) -> str | None``.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

_PLUGIN_NAME = "sage-map"

_SAGE_HOME = Path(
    os.environ.get("SAGE_HOME") or (Path.home() / ".sage" / "framework")
)

_WORKFLOW_FILE = _SAGE_HOME / "core" / "workflows" / "map.workflow.md"

_COMMAND_DESCRIPTION = "Codebase mapping."
_ARGS_HINT = ""


def _load_workflow() -> str:
    """Return the map workflow markdown, or a graceful fallback."""
    try:
        return _WORKFLOW_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            f"Sage workflow file not found at {_WORKFLOW_FILE}.\n"
            "Install the sage framework to ~/.sage/framework/ or set SAGE_HOME."
        )
    except OSError as exc:
        return f"Could not read sage workflow: {exc}"


def _handle_map(raw_args: str) -> str:
    """Handler for ``/map`` — return the map workflow text."""
    del raw_args
    return _load_workflow()


def register(ctx) -> None:
    """Register the ``/map`` slash command.

    Defensive try/except so a misbehaving plugin does not disable siblings
    (per the canon plugin guide).
    """
    try:
        ctx.register_command(
            "map",
            handler=_handle_map,
            description=_COMMAND_DESCRIPTION,
            args_hint=_ARGS_HINT,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logging.getLogger(_PLUGIN_NAME).exception("register failed: %s", exc)