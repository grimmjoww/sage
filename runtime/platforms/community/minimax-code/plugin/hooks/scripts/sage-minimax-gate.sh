#!/usr/bin/env bash
# MiniMax Code transport for the canonical Sage gates.
#
# The canonical gates speak one contract: read the tool-call JSON on stdin,
# exit 0 to allow, exit 2 to block with the reason on stderr. MiniMax Code
# instead reads a JSON decision object on stdout. This bridge runs the
# canonical gate unchanged and translates its exit code into the one object
# the host understands. It copies no gate logic and makes no decisions of its
# own; a gate that cannot decide never decides here either.
#
# Usage: sage-minimax-gate.sh <gate-script.sh>
set -uo pipefail

GATE_SCRIPT="${1:-}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/$GATE_SCRIPT"

PYTHON_EXE="${SAGE_FORMAL_GATE_PYTHON:-$(type -P python3 || true)}"

emit() {
  "$PYTHON_EXE" -c '
import json, sys
mode, reason = sys.argv[1], sys.argv[2]
if mode == "deny":
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason or "blocked by sage gate"}}))
' "$1" "$(cat 2>/dev/null | head -c 4000)"
}

if [ -z "$GATE_SCRIPT" ] || [ ! -f "$TARGET" ]; then
  printf 'sage-minimax-gate: canonical gate not found: %s\n' "$TARGET" >&2
  exit 0
fi
if [ -z "$PYTHON_EXE" ] || [ ! -f "$PYTHON_EXE" ]; then
  # No interpreter means no decision. Stay out of the way rather than block a
  # legitimate edit; the missing interpreter is reported, not guessed around.
  printf 'sage-minimax-gate: python3 unavailable; gate not run\n' >&2
  exit 0
fi

export PYTHONUTF8=1
if command -v cygpath >/dev/null 2>&1; then
  export TMPDIR="$(cygpath -m "${TEMP:-${TMPDIR:-/tmp}}")"
  export MSYS_NO_PATHCONV=1
fi

OUT="$(mktemp "${TMPDIR:-/tmp}/sage-minimax-gate-out-XXXXXX" 2>/dev/null)"
ERR="$(mktemp "${TMPDIR:-/tmp}/sage-minimax-gate-err-XXXXXX" 2>/dev/null)"
if [ -z "$OUT" ] || [ -z "$ERR" ]; then
  printf 'sage-minimax-gate: could not capture gate output\n' >&2
  [ -n "$OUT" ] && rm -f "$OUT"
  [ -n "$ERR" ] && rm -f "$ERR"
  exit 0
fi
trap 'rm -f "$OUT" "$ERR"' EXIT

# The gate reads the real tool-call payload on stdin, so stdin is inherited.
"$BASH" "$TARGET" >"$OUT" 2>"$ERR"
RC=$?

case "$RC" in
  0)
    # Allow: say nothing on stdout. The host's default is to proceed, and an
    # empty stdout cannot be misread as a decision.
    if [ -s "$ERR" ]; then cat "$ERR" >&2; fi
    ;;
  2)
    emit deny <"$ERR"
    cat "$ERR" >&2
    ;;
  *)
    # Unverifiable: the gate itself broke. Same rule as a broken hook elsewhere
    # in Sage — report it, do not turn it into a silent allow or a fake block.
    printf 'sage-minimax-gate: %s exited %s unexpectedly\n' "$GATE_SCRIPT" "$RC" >&2
    cat "$ERR" >&2
    ;;
esac
exit 0