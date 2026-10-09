#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# generate-minimax-code.sh — generate Sage artifacts for MiniMax Code
#
# Usage:
#   sage init --platform minimax-code
#   bash runtime/platforms/community/minimax-code/setup/generate-minimax-code.sh <project-root>
#
# What it does:
#   1. Creates the .sage/ directory structure
#   2. Writes .sage/config.yaml with the gate toggles
#   3. Writes the eager core + merged constitution into AGENTS.md
#   4. Copies the gate scripts into .sage/gates/
#   5. Installs the Local Plugin into ~/.minimax/plugins/sage/
#   6. Prints next steps
#
# Why AGENTS.md and not CLAUDE.md:
#   MiniMax Code reads a project-root AGENTS.md. That is the file the host's
#   own `init` skill generates for agent bootstrapping, so it is the real
#   context-injection target rather than a fiction invented to satisfy a
#   conformance check. The conformance suite reads `artifacts.instructions`
#   from platform.yaml; this generator and that field name the same file.
#
# Skills are NOT inlined. MiniMax has native skill discovery, so per
# ADR-9 the ~220 lines stay in the skills where the host can fetch them on
# demand. Inlining them here would grow every session's context for nothing.
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

PROJECT_ROOT="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(dirname "$SCRIPT_DIR")"
# Four levels up: minimax-code → community → platforms → runtime → repo root.
# Three lands on `runtime/` and every later path silently gains a `runtime/`
# prefix — which is how the first run of this generator exited 2 while the
# conformance suite reported a successful generation.
SAGE_ROOT="$(cd "$PLATFORM_ROOT/../../../.." && pwd)"
CORE="$SAGE_ROOT/core"
PLUGIN_SRC="$PLATFORM_ROOT/plugin"
MCODE_PLUGIN_DIR="${MINIMAX_PLUGIN_DIR:-$HOME/.minimax/plugins}"

BOLD='\033[1m'; GREEN='\033[32m'; CYAN='\033[36m'; RED='\033[31m'; RESET='\033[0m'

# The shared emitters are not optional. If they are missing we fail loudly
# rather than emitting a thinner instructions file that still claims to be
# Sage — that is the exact silent-narrowing failure conformance exists to catch.
SHARED="$SAGE_ROOT/runtime/platforms/_shared"
for f in instructions-body.sh constitution.sh; do
  if [ ! -f "$SHARED/$f" ]; then
    echo -e "${RED}generate-minimax-code: missing $SHARED/$f${RESET}" >&2
    exit 2
  fi
done
# shellcheck source=/dev/null
source "$SHARED/instructions-body.sh"
# shellcheck source=/dev/null
source "$SHARED/constitution.sh"

echo ""
echo -e "  ${BOLD}Sage for MiniMax Code${RESET}"
echo ""

# ── 1. .sage/ structure ────────────────────────────────────────────────────
mkdir -p "$PROJECT_ROOT/.sage"/{work,gates,tmp}
echo -e "  ${GREEN}✓${RESET} Created .sage/ directory"

# ── 2. config.yaml ─────────────────────────────────────────────────────────
CONFIG="$PROJECT_ROOT/.sage/config.yaml"
if [ ! -f "$CONFIG" ]; then
  cat > "$CONFIG" << 'EOF'
# Sage enforcement configuration
# All gates are opt-in — set to false to disable enforcement.

hard_enforcement: true    # master switch — gates are inert when false
tdd_enforcement: true     # tdd-gate: tests before code (Rule 2)
secrets_gate: true        # secrets-gate: no hardcoded credentials (Rule 3)
verify_gate: true         # verify-gate: verify before claiming (Rule 5)
spec_gate: true           # spec-gate: spec before implementation (Rule 1)

# MiniMax Code notes.
#
# The plugin is GLOBAL — ~/.minimax/plugins/sage/. These toggles are what make
# the gates apply to THIS project; the plugin stays installed and inert
# everywhere else. A repo without .sage/ is never touched by any hook.
#
# The four ported gates (spec, tdd, secrets, verify) all check
# `hard_enforcement` before doing anything.
EOF
  echo -e "  ${GREEN}✓${RESET} Wrote .sage/config.yaml"
else
  echo -e "  ${CYAN}⊘${RESET} .sage/config.yaml already exists, skipping"
fi

# ── 3. .sage/.gitignore ────────────────────────────────────────────────────
GITIGNORE="$PROJECT_ROOT/.sage/.gitignore"
if [ ! -f "$GITIGNORE" ]; then
  cat > "$GITIGNORE" << 'EOF'
# Sage runtime state
.session-lock
tmp/
gates/audit.jsonl
gates/session-pickup.md
gates/session-log
gates/gate-blocks.log
EOF
  echo -e "  ${GREEN}✓${RESET} Wrote .sage/.gitignore"
fi

# ── 4. Gate scripts into .sage/gates/ ──────────────────────────────────────
# The plugin owns the authoritative copies; this is a project-local mirror so
# the gates are readable and diffable from the repo they are protecting.
if [ -d "$PLUGIN_SRC/scripts/gates" ]; then
  cp "$PLUGIN_SRC/scripts/gates/"*.py "$PROJECT_ROOT/.sage/gates/"
  echo -e "  ${GREEN}✓${RESET} Mirrored gate scripts into .sage/gates/"
else
  echo -e "  ${CYAN}⊘${RESET} No extracted gates yet — run setup/extract_gates.py first"
fi

# ── 5. AGENTS.md — the eager core + merged constitution ─────────────────────
AGENTS="$PROJECT_ROOT/AGENTS.md"
CONST="$(build_constitution_section "$CORE" "$PROJECT_ROOT/.sage")"
BODY="$(emit_instructions_body)"

# Substitute the placeholder with Python, never sed. The merged constitution
# is prose full of '|', '\' and '/' — table rows, code fences, URLs — and
# every sed delimiter collides with one of them. A first attempt used '|' and
# died with "unterminated `s' command", and `set -e` took the generator down
# with it, which made `sage init` look successful while writing no AGENTS.md.
BODY_FILE="$(mktemp)"; CONST_FILE="$(mktemp)"
trap 'rm -f "$BODY_FILE" "$CONST_FILE"' EXIT
printf '%s' "$BODY"    > "$BODY_FILE"
printf '%s' "$CONST"   > "$CONST_FILE"

if [ -f "$AGENTS" ] && grep -q '<!-- sage:begin' "$AGENTS"; then
  # Re-running init must not stack a second eager core onto the first.
  echo -e "  ${CYAN}⊘${RESET} AGENTS.md already carries a Sage block, skipping"
else
  if python3 "$SCRIPT_DIR/emit_agents_md.py" "$BODY_FILE" "$CONST_FILE" > "$AGENTS.tmp"; then
    if [ -f "$AGENTS" ]; then
      # A project that already has AGENTS.md keeps its own content; Sage is
      # appended in a marked block rather than overwriting anyone's file.
      cat "$AGENTS.tmp" >> "$AGENTS"
      echo -e "  ${GREEN}✓${RESET} Appended Sage block to existing AGENTS.md"
    else
      mv "$AGENTS.tmp" "$AGENTS"
      echo -e "  ${GREEN}✓${RESET} Wrote AGENTS.md (eager core + merged constitution)"
    fi
  else
    rm -f "$AGENTS.tmp"
    echo -e "  ${CYAN}⊘${RESET} Could not compose AGENTS.md — leaving it untouched"
  fi
fi

# ── 6. Install the Local Plugin ────────────────────────────────────────────
if [ -d "$PLUGIN_SRC" ]; then
  mkdir -p "$MCODE_PLUGIN_DIR/sage"
  # Copy contents, not the wrapper, so the package root IS the plugin root.
  cp -R "$PLUGIN_SRC/." "$MCODE_PLUGIN_DIR/sage/"
  echo -e "  ${GREEN}✓${RESET} Installed plugin → $MCODE_PLUGIN_DIR/sage"
else
  echo -e "  ${CYAN}⊘${RESET} plugin/ not found at $PLUGIN_SRC — install it manually"
fi

# ── 7. Next steps ──────────────────────────────────────────────────────────
# printf, not a heredoc: a heredoc emits the \033 bytes literally, so the user
# sees "\033[1mNext steps:" instead of a bold heading.
printf '\n  %bNext steps:%b\n\n' "$BOLD" "$RESET"
printf '  1. %bRestart MiniMax Code%b (or wait for the automatic plugin rescan)\n' "$CYAN" "$RESET"
printf '     and confirm "Sage" appears under Local Plugins.\n\n'
printf '  2. %bVerify enforcement is real — not just installed:%b\n' "$CYAN" "$RESET"
printf '     python3 %s/runtime/platforms/community/minimax-code/setup/verify_veto.py\n' "$SAGE_ROOT"
printf '     Must print "4/4 cases matched". If it does not, the veto is not wired.\n\n'
printf '  3. %bStart a workflow:%b load the sage skill and pick FIX / BUILD / ARCHITECT.\n' "$CYAN" "$RESET"
printf '     BUILD writes a spec before it touches source.\n\n'
printf '  %bTo disable enforcement:%b set hard_enforcement: false in .sage/config.yaml\n\n' "$CYAN" "$RESET"
printf '  %b✓%b Sage for MiniMax Code initialized.\n\n' "$GREEN" "$RESET"
