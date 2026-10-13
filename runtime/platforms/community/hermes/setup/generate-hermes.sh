#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# generate-hermes.sh — generate Sage artifacts for Hermes Agent
#
# Usage:
#   sage init --platform hermes
#   bash runtime/platforms/community/hermes/setup/generate-hermes.sh <project-root>
#
# What it does:
#   1. Creates .sage/ directory structure
#   2. Writes SOUL.md (Hermes reads this as system prompt slot #1)
#   3. Copies gate scripts to .sage/gates/
#   4. Prints config snippet for ~/.hermes/config.yaml
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

# Args: <project-root> [--profile <name>] [--profile=<name>]
# --profile: install the Sage plugin into $HERMES_HOME/profiles/<name>/plugins/sage
# instead of just printing manual copy instructions.
PROJECT_ROOT=""
PROFILE_NAME=""
while [ $# -gt 0 ]; do
  case "$1" in
    --profile=*) PROFILE_NAME="${1#--profile=}" ;;
    --profile)
      [ $# -ge 2 ] || { echo -e "  ${RED}❌ --profile requires a name${RESET}" >&2; exit 1; }
      PROFILE_NAME="$2"
      shift
      ;;
    *)
      [ -z "$PROJECT_ROOT" ] && PROJECT_ROOT="$1"
      ;;
  esac
  shift
done
PROJECT_ROOT="${PROJECT_ROOT:-.}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLATFORM_ROOT="$(dirname "$SCRIPT_DIR")"
# Hermes lives 4 levels below the repo root: sage/runtime/platforms/community/hermes.
# Four `..`s, not three — three lands on `sage/runtime` and only the runtime/
# subdirs make it into the installed plugin (caught 2026-10-13 via `bash -x`).
SAGE_ROOT="$(cd "$PLATFORM_ROOT/../../../.." && pwd)"

# Resolve Hermes home: $HERMES_HOME if set, else ~/.hermes.
# This is where Hermes stores profiles/, and where Sage must land its plugin.
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"

BOLD='\033[1m'
GREEN='\033[32m'
CYAN='\033[36m'
RED='\033[31m'
YELLOW='\033[33m'
RESET='\033[0m'

echo ""
echo -e "  ${BOLD}Sage for Hermes Agent${RESET}"
echo ""

# ── Create .sage directory structure ──
mkdir -p "$PROJECT_ROOT/.sage"/{work,gates,tmp}
echo -e "  ${GREEN}✓${RESET} Created .sage/ directory"

# ── Write default config.yaml ──
CONFIG="$PROJECT_ROOT/.sage/config.yaml"
if [ ! -f "$CONFIG" ]; then
  cat > "$CONFIG" << 'EOF'
# Sage enforcement configuration
# All gates are opt-in — set to true to enable enforcement.

hard_enforcement: true    # master switch — gates are inert when false
tdd_enforcement: true     # tdd-gate: tests before code (Rule 1)
secrets_gate: true        # secrets-gate: no hardcoded credentials
verify_gate: true         # verify-gate: verify before claiming (Rule 5)
bookkeeping_gate: true    # bookkeeping-gate: one-command close-out

# Review loop configuration
review_loop:
  mode: v2                # v2 = witness capping, v1 = unlimited
  witness_capping: true   # cap witnesses to prevent runaway review

# Auto-QA configuration
auto_qa: true             # dispatch subagent for independent review (when available)
EOF
  echo -e "  ${GREEN}✓${RESET} Wrote .sage/config.yaml"
else
  echo -e "  ${CYAN}⊘${RESET} .sage/config.yaml already exists, skipping"
fi

# ── Write .gitignore for .sage ──
GITIGNORE="$PROJECT_ROOT/.sage/.gitignore"
if [ ! -f "$GITIGNORE" ]; then
  cat > "$GITIGNORE" << 'EOF'
# Sage runtime state
.session-lock
tmp/
gates/session-pickup.md
gates/session-log
gates/gate-blocks.log
EOF
  echo -e "  ${GREEN}✓${RESET} Wrote .sage/.gitignore"
fi

# ── Write SOUL.md (Hermes reads this as system prompt slot #1) ──
SOUL="$PROJECT_ROOT/SOUL.md"
if [ ! -f "$SOUL" ]; then
  cat > "$SOUL" << 'SOULEOF'
# Sage — Always-On Rules

You are running under Sage, an intelligent skills framework that enforces
quality through mechanical gates, not just instructions.

## Session Pickup

Before starting any work, check `.sage/gates/session-pickup.md` for:
- Active cycles and their status
- Recent decisions
- Collision warnings from parallel sessions
- Worktree memory directives (if in a linked worktree)

## The 8 Always-On Rules

### 1. Memory before work
Before starting any task, search Sage memory for relevant context:
- `sage-self-learning` for WHEN/CHECK/BECAUSE prevention rules
- `sage-memory` for project knowledge and conventions
- `sage-ontology` for entity relationships

### 2. Spec-first
Every medium+ task needs a `spec.md` BEFORE source edits. The spec-gate
hook will block source edits until a spec exists and is approved.

### 3. Test-first (TDD)
Write tests BEFORE editing source files. The tdd-gate hook blocks source
edits until a corresponding test file exists.

### 4. No hardcoded secrets
Never put API keys, passwords, or tokens in source code. The secrets-gate
hook will block edits containing hardcoded secrets.

### 5. Artifact-only state
Progress lives in artifacts (spec.md, plan.md, manifest.md), not in
conversational summaries. File existence IS the state.

### 6. Checkpoints
Use [A]pprove / [R]evise / [C]ontinue patterns. Never unilaterally defer
decisions — always offer numbered options.

### 7. Decisions logging
Log all significant decisions to `.sage/decisions.md` (newest-first).
Include reasoning, not just outcomes.

### 8. Skills before assumptions
Check available Sage skills before making domain assumptions.
Load skills via `skill_view("sage:<name>")`.

## Available Workflows

Read these skill files to start a workflow:
- `/sage` — route via keywords → classify → confirm
- `/build` — spec → plan → build-loop → quality gates
- `/fix` — diagnose → scope → fix → verify
- `/architect` — elicit → design → milestone plan
- `/research` — user interviews → JTBD → opportunity map
- `/design` — UX brief → specify → writing
- `/review` — independent evaluation (ux|design|browser|code)
- `/learn` — codebase scan → memory
- `/reflect` — review cycle → extract learnings
- `/continue` — resume an active cycle
- `/autoresearch` — autonomous iteration toward a metric

## Enforcement Status

This project has Sage enforcement **enabled**. The following gates are active:
- **config-gate** — blocks edits that would disable enforcement
- **secrets-gate** — blocks hardcoded credentials
- **bookkeeping-gate** — redirects hand-edits to the one-command close-out writer
- **spec-gate** — blocks source edits while any cycle is `pre-spec`
- **tdd-gate** — blocks source edits before a test exists
- **verify-gate** — blocks commits without fresh test evidence

To disable enforcement, edit `.sage/config.yaml` and set `hard_enforcement: false`.
SOULEOF
  echo -e "  ${GREEN}✓${RESET} Wrote SOUL.md"
else
  echo -e "  ${CYAN}⊘${RESET} SOUL.md already exists, skipping"
fi

# ── Print next steps / install plugin into the named profile ──
echo ""
if [ -n "$PROFILE_NAME" ]; then
  PROFILES_ROOT="$HERMES_HOME/profiles"
  PROFILE_DIR="$PROFILES_ROOT/$PROFILE_NAME"
  if [ ! -d "$PROFILE_DIR" ]; then
    echo -e "  ${RED}❌ Profile '$PROFILE_NAME' not found under $HERMES_HOME.${RESET}" >&2
    echo "" >&2
    echo -e "  ${BOLD}Profiles that exist there:${RESET}" >&2
    if [ -d "$PROFILES_ROOT" ]; then
      for p in "$PROFILES_ROOT"/*; do
        [ -d "$p" ] && echo "    - $(basename "$p")" >&2
      done
    else
      echo "    (no profiles/ directory under $HERMES_HOME)" >&2
    fi
    echo "" >&2
    echo "  Create the profile first, then re-run with --profile $PROFILE_NAME." >&2
    exit 1
  fi
  PLUGIN_DIR="$PROFILE_DIR/plugins/sage"
  mkdir -p "$(dirname "$PLUGIN_DIR")"
  rm -rf "$PLUGIN_DIR"
  mkdir -p "$PLUGIN_DIR"
  # `cp -a SRC DEST` when DEST exists puts SRC *as a subdir* of DEST on GNU
  # cp — we want DEST to receive SRC's contents, so we copy SRC/.'s contents.
  cp -a "$SAGE_ROOT/." "$PLUGIN_DIR/"
  echo -e "  ${GREEN}✓${RESET} Installed Sage plugin → ${CYAN}$PLUGIN_DIR${RESET}"
  echo ""
  echo -e "  ${BOLD}Enable the plugin:${RESET}"
  echo "    hermes plugins enable sage"
  echo ""
else
  echo -e "  ${BOLD}Next steps:${RESET}"
  echo ""
  echo -e "  1. ${CYAN}Copy the Sage plugin to your Hermes profile:${RESET}"
  echo "     cp -r \"$SAGE_ROOT\" \"$HERMES_HOME/profiles/<your-profile>/plugins/sage/\""
  echo ""
  echo -e "     (Hermes home resolved as: ${CYAN}$HERMES_HOME${RESET})"
  echo ""
  echo -e "  2. ${CYAN}Enable the plugin:${RESET}"
  echo "     hermes plugins enable sage"
  echo ""
  echo -e "  3. ${CYAN}Start a Sage workflow:${RESET}"
  echo "     hermes"
  echo "     > /sage build a REST API for user authentication"
  echo ""
fi
echo -e "  ${GREEN}✓${RESET} Sage for Hermes Agent initialized successfully!"
echo ""
