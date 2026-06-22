#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage → Hermes Setup
# Generates AGENTS.md + skills/<n>/SKILL.md + agent-hooks/ from Sage core
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SAGE_ROOT="${1:-.}"
SAGE_DIR="$SAGE_ROOT/sage"
HERMES_ROOT="${HERMES_ROOT:-$SAGE_ROOT}"

# Hermes paths — the shell-hook subsystem reads from HERMES_HOME (env var) or
# falls back to %LOCALAPPDATA%/hermes on Windows, ~/.hermes elsewhere.
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
if [ "${OS:-}" = "Windows_NT" ] || uname -s 2>/dev/null | grep -qi mingw; then
  HERMES_HOME="${HERMES_HOME:-$LOCALAPPDATA/hermes}"
fi

# Profile-scoped path: when HERMES_HOME is the parent of multiple profiles,
# plugins live under profiles/<active>/plugins/. The simplest correct rule
# is to put plugins under <HERMES_HOME>/plugins/ and let the global
# PluginManager discover them.
HERMES_PLUGINS_DIR="$HERMES_HOME/plugins"

# Skills land at <HERMES_ROOT>/skills/<name>/SKILL.md per Hermes convention
# (hermes-agent/website/docs/developer-guide/creating-skills.md).
HERMES_SKILLS_DIR="$HERMES_ROOT/skills"

# Agent-hooks: the script that fires on session start, etc.
HERMES_AGENT_HOOKS_DIR="$HERMES_ROOT/agent-hooks"

# config snippet — the hooks: block that needs to land in the active profile's
# config.yaml (not in ~/.hermes/config.yaml, which is the global default).
# We write a snippet file the user can manually merge OR symlink.
HERMES_CONFIG_SNIPPET="$HERMES_HOME/config-snippet-hermes.yaml"

CORE="$SAGE_DIR/core"

echo ""
echo "🚀 Sage → Hermes Setup"
echo "═══════════════════════════════"
echo "Hermes home: $HERMES_HOME"
echo "Skills dir:   $HERMES_SKILLS_DIR"
echo "Agent hooks:  $HERMES_AGENT_HOOKS_DIR"
echo "Plugins dir:  $HERMES_PLUGINS_DIR"

# ── Validate ──
if [ ! -d "$CORE" ]; then
  echo "❌ Sage framework not found at $SAGE_DIR"
  echo "   Run this from the project root where sage/ is located."
  exit 1
fi

# ── Read prefix config ──
PREFIX=""
if [ -f "$SAGE_ROOT/.sage/config.yaml" ]; then
  if grep -q 'command_prefix: true' "$SAGE_ROOT/.sage/config.yaml" 2>/dev/null; then
    PREFIX="sage:"
  fi
fi

# ═══════════════════════════════════════════════════════════════
# AGENTS.md — Generated from canonical template pattern
# Hermes reads AGENTS.md (NOT CLAUDE.md) per hermes-agent convention
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📝 Generating AGENTS.md..."
# Source the shared instructions-body emitter
source "$(dirname "$0")/../../_shared/instructions-body.sh"

emit_instructions_body > "$SAGE_ROOT/AGENTS.md"

# ── Dynamic constitution merging (same as claude-code generator) ──
CONST_SECTION="## Engineering Principles

Base (all projects):
1. Tests before code — every behavior has a test before implementation
2. No silent failures — errors handled, logged, or propagated
3. Secrets never in code — use env vars or secret managers
4. Dependencies explicit — declared with pinned versions
5. Changes reversible — migrations reversible, deployments rollbackable"

PRINCIPLE_NUM=5

CONST_FILE="$SAGE_ROOT/.sage/constitution.md"
if [ -f "$CONST_FILE" ]; then
  PRESET=$(sed -n '/^---$/,/^---$/{ /^extends:/s/^extends: *//p; }' "$CONST_FILE" 2>/dev/null)
  if [ -n "$PRESET" ] && [ "$PRESET" != "base" ] && [ "$PRESET" != "none" ]; then
    PRESET_FILE="$CORE/constitution/presets/${PRESET}.constitution.md"
    if [ -f "$PRESET_FILE" ]; then
      PRESET_PRINCIPLES=$(sed -n '/^## Additions/,$ { /^[0-9]/p; }' "$PRESET_FILE")
      if [ -n "$PRESET_PRINCIPLES" ]; then
        CONST_SECTION="$CONST_SECTION

${PRESET} preset:"
        while IFS= read -r line; do
          if [ -n "$line" ]; then
            PRINCIPLE_NUM=$((PRINCIPLE_NUM + 1))
            CLEAN=$(echo "$line" | sed 's/^[0-9]*\. *//')
            CONST_SECTION="$CONST_SECTION
${PRINCIPLE_NUM}. ${CLEAN}"
          fi
        done <<< "$PRESET_PRINCIPLES"
      fi
    fi
  fi

  PROJECT_ADDITIONS=$(sed -n '/^## Project Additions/,$ { /^## Project/d; /^$/d; /^(/d; p; }' "$CONST_FILE" 2>/dev/null)
  if [ -n "$PROJECT_ADDITIONS" ]; then
    CONST_SECTION="$CONST_SECTION

Project additions:"
    while IFS= read -r line; do
      if [ -n "$line" ]; then
        PRINCIPLE_NUM=$((PRINCIPLE_NUM + 1))
        CONST_SECTION="$CONST_SECTION
${PRINCIPLE_NUM}. ${line}"
      fi
    done <<< "$PROJECT_ADDITIONS"
  fi
fi

# Replace placeholder in AGENTS.md
python3 -c "
import sys
with open('$SAGE_ROOT/AGENTS.md', 'r') as f:
    content = f.read()
replacement = '''$CONST_SECTION'''
content = content.replace('__CONSTITUTION_PLACEHOLDER__', replacement)
with open('$SAGE_ROOT/AGENTS.md', 'w') as f:
    f.write(content)
" 2>/dev/null || {
  echo "⚠ python3 not available, AGENTS.md constitution placeholder not substituted"
}

# Apply prefix
if [ -n "$PREFIX" ]; then
  sed -i.bak \
    -e "s|/design-review|/${PREFIX}design-review|g" \
    -e "s|/autoresearch|/${PREFIX}autoresearch|g" \
    -e "s|/architect|/${PREFIX}architect|g" \
    -e "s|/research|/${PREFIX}research|g" \
    -e "s|/continue|/${PREFIX}continue|g" \
    -e "s|/reflect|/${PREFIX}reflect|g" \
    -e "s|/analyze|/${PREFIX}analyze|g" \
    -e "s|/design|/${PREFIX}design|g" \
    -e "s|/review|/${PREFIX}review|g" \
    -e "s|/status|/${PREFIX}status|g" \
    -e "s|/build|/${PREFIX}build|g" \
    -e "s|/learn|/${PREFIX}learn|g" \
    -e "s|/fix|/${PREFIX}fix|g" \
    -e "s|/map|/${PREFIX}map|g" \
    -e "s|/qa|/${PREFIX}qa|g" \
    "$SAGE_ROOT/AGENTS.md" && rm -f "$SAGE_ROOT/AGENTS.md.bak"
  echo "  ✓ AGENTS.md (with ${PREFIX} prefix)"
else
  echo "  ✓ AGENTS.md"
fi

# ═══════════════════════════════════════════════════════════════
# Skills — Hermes-native path: skills/<name>/SKILL.md
# Per hermes-agent/website/docs/developer-guide/creating-skills.md
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📎 Generating skills from core workflows → ${HERMES_SKILLS_DIR}..."

source "$(dirname "$0")/../../_shared/preambles.sh"

mkdir -p "$HERMES_SKILLS_DIR"

SKILL_COUNT=0
for wf in "$CORE"/workflows/*.workflow.md; do
  [ -f "$wf" ] || continue
  basename_wf=$(basename "$wf" .workflow.md)

  PREAMBLE=$({ emit_preamble "$basename_wf"; printf x; })
  PREAMBLE="${PREAMBLE%x}"

  if [ "$basename_wf" = "sage" ]; then
    target_dir="$HERMES_SKILLS_DIR/sage"
    mkdir -p "$target_dir"
    cat > "$target_dir/SKILL.md" << 'SAGEEOF'
---
name: sage
description: Sage workflow router — describe what you want, it routes via keywords → classify → confirm.
---

## When to Use
Load this skill when the user runs `/sage` or asks to sage something.

## Independent review (delegate_task)
When a step calls for an independent review, invoke `delegate_task` with a restricted `toolsets=["file"]` (drops terminal/code_execution) against the `sage-reviewer` skill. Best-effort read-only (restricted toolset + prompt), NOT permission-denied.

RULES (apply to every step — non-negotiable):
- Present project state with "Sage:" prefix
- Present options with [1] [2] [3] bracket notation — ALWAYS
- Recommend a specific workflow for Standard+ tasks
- NEVER just ask "What would you like to do?" — present structured choices
- Never use code blocks for interaction output

## Step 1: Read State

Scan `.sage/work/` for active initiatives (read frontmatter: title, status, phase).
Scan `.sage/docs/` for project-level artifacts.
Read `.sage/decisions.md` for recent context.

## Step 2: Present Status and Options

**If work is in progress:**

**Sage:** [Project name] — [feature] is in progress, [phase] phase.

[1] Continue [feature] — resume from [next step]
[2] Start something new
[3] Review what's been done

**If no work in progress but artifacts exist:**

**Sage:** [Project name] — no active work. Previous: [list initiatives].

[1] Start a new task — describe what you want to build
[2] Review existing artifacts
[3] Learn the codebase

**If fresh project:**

**Sage:** Fresh project, no work in progress.

[1] Build something — describe what you want to create
[2] Learn the codebase first
[3] Something else — describe what you need

## Step 3: Route to Workflow

Based on user's choice or free-form input, classify scope and route:
- Lightweight → just do it
- Standard → announce build/fix workflow, start first step
- Comprehensive → present architect workflow card

For complex routing or gap detection, read sage-navigator at `sage/core/capabilities/orchestration/sage-navigator/SKILL.md`.
SAGEEOF
    echo "  ✓ sage.md → /sage (self-contained)"
    SKILL_COUNT=$((SKILL_COUNT + 1))
    continue
  fi

  if [ "$basename_wf" = "review" ]; then
    target_dir="$HERMES_SKILLS_DIR/${PREFIX}review"
    mkdir -p "$target_dir"
    cat > "$target_dir/SKILL.md" << REVIEWEOF
---
name: ${PREFIX}review
description: Independent artifact review (delegates to a sage-reviewer sub-agent).
---

## When to Use
Load this skill when the user runs /review or asks to review a sage artifact.

## Independent review (delegate_task)
When this skill runs, delegate the actual review to a sage-reviewer sub-agent via delegate_task with restricted toolsets=["file"]. This is best-effort read-only — verify the reviewer never edits a file during the run.

RULES (apply to every step — non-negotiable):
- DELEGATION: Use delegate_task for review. Self-review is NOT independent.
- Always load the producing skill's quality criteria.
- Never use code blocks for interaction output.

## Step 1: Identify What to Review

If not specified, scan \`.sage/work/\` and \`.sage/docs/\` for recent artifacts.

[1] .sage/work/<latest>/brief.md
[2] .sage/work/<latest>/spec.md
[3] .sage/work/<latest>/plan.md
[4] Custom: I'll specify

## Step 2: Prepare Review Context

1. **Artifact path** — the file to review
2. **Producing skill path** — find which skill or workflow created it
3. **Quality criteria** — read from the skill's \`## Quality Criteria\` section

## Step 3: Delegate to sage-reviewer Sub-Agent

\`\`\`
You are independently reviewing a Sage project artifact. You were
NOT involved in producing this work — evaluate it with fresh eyes.

CONTEXT PACKAGE:
1. ARTIFACT: Read the artifact at: [ARTIFACT PATH]
2. CRITERIA: Read quality criteria from: [SKILL/WORKFLOW PATH]
3. DECISIONS: Read .sage/decisions.md for last 5 entries.
4. LEARNINGS: Search sage-memory with the artifact domain as query.

EVALUATE the artifact against EACH quality criterion.

CLASSIFY each finding by severity: CRITICAL, MAJOR, MINOR.

PRESENT YOUR REVIEW AS:
## Review: [artifact name]
### Critical Issues
### Major Issues
### Minor Issues / Improvements
### Strengths
### Verdict
PASS — ready to proceed
NEEDS REVISION — [specific items to address]
FAIL — [significant gaps]
\`\`\`

## Step 4: Present Findings
REVIEWEOF
    echo "  ✓ ${PREFIX}review.md → /${PREFIX}review (delegate_task)"
    SKILL_COUNT=$((SKILL_COUNT + 1))
    continue
  fi

  cmd_name="${basename_wf}"
  [ "$basename_wf" != "sage" ] && cmd_name="${PREFIX}${basename_wf}"

  target_dir="$HERMES_SKILLS_DIR/${cmd_name}"
  mkdir -p "$target_dir"
  {
    printf "%s" "$PREAMBLE"
    sed '/^---$/,/^---$/d' "$wf" \
      | sed 's|\*\*sage-navigator\*\* skill|**sage-navigator** skill at `sage/core/capabilities/orchestration/sage-navigator/SKILL.md`|g' \
      | sed "s|sage-navigator's intelligence layer|sage-navigator's intelligence layer (\`sage/core/capabilities/orchestration/sage-navigator/SKILL.md\`, section 2)|g" \
      | sed 's|If relevant Sage skills exist, read and follow them.|If relevant Sage skills exist in `sage/skills/`, read and follow them.|g' \
      | sed '/^$/N;/^\n$/d'
  } > "$target_dir/SKILL.md"

  echo "  ✓ ${cmd_name}/SKILL.md → /${cmd_name}"
  SKILL_COUNT=$((SKILL_COUNT + 1))
done

echo "  ✓ $SKILL_COUNT skills emitted to ${HERMES_SKILLS_DIR}"

# ═══════════════════════════════════════════════════════════════
# Project state — .sage/ initialization (same as claude-code)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📊 Checking project state..."
PROJECT_SAGE="$SAGE_ROOT/.sage"
if [ -d "$PROJECT_SAGE" ]; then
  echo "  ✓ .sage/ already exists"
else
  mkdir -p "$PROJECT_SAGE/work" "$PROJECT_SAGE/docs"
  cat > "$PROJECT_SAGE/decisions.md" << 'DECEOF'
# Decisions

Shared log for significant decisions and context.
- [init] Sage initialized
DECEOF
  cat > "$PROJECT_SAGE/conventions.md" << 'CONVEOF'
# Project Conventions
Discovered by Sage on first run.
CONVEOF
  echo "  ✓ .sage/ initialized"
fi

# ═══════════════════════════════════════════════════════════════
# Gate scripts — explicit deploy (the upstream bug per LRN d98e34da)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🔒 Deploying gate scripts..."

mkdir -p "$HERMES_AGENT_HOOKS_DIR"
GATE_SCRIPTS="$CORE/gates/scripts"

if [ -d "$GATE_SCRIPTS" ]; then
  for script in "$GATE_SCRIPTS"/*.sh; do
    [ -f "$script" ] || continue
    cp "$script" "$HERMES_AGENT_HOOKS_DIR/"
    chmod +x "$HERMES_AGENT_HOOKS_DIR/$(basename "$script")"
    echo "  ✓ $(basename "$script")"
  done
else
  echo "  ⚠ Gate scripts not found at $GATE_SCRIPTS"
fi

GATE_CONFIG="$CORE/gates/_config/gate-modes.yaml"
if [ -f "$GATE_CONFIG" ]; then
  cp "$GATE_CONFIG" "$HERMES_AGENT_HOOKS_DIR/"
  echo "  ✓ gate-modes.yaml"
fi

# ═══════════════════════════════════════════════════════════════
# Session-init hook — copy the hermes-adapted version to agent-hooks/
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🔗 Setting up session-init hook..."

HOOK_SRC="$CORE/../runtime/platforms/hermes/hooks/sage-session-init.sh"
if [ -f "$HOOK_SRC" ]; then
  cp "$HOOK_SRC" "$HERMES_AGENT_HOOKS_DIR/sage-session-init.sh"
  chmod +x "$HERMES_AGENT_HOOKS_DIR/sage-session-init.sh"
  echo "  ✓ sage-session-init.sh (cwd-adapted for Hermes wire-protocol)"
fi

# ═══════════════════════════════════════════════════════════════
# config-snippet.yaml — the hooks: block to merge into config.yaml
# Hermes loads hooks from the active profile's config.yaml (not the global)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📋 Writing config snippet to $HERMES_CONFIG_SNIPPET..."

cat > "$HERMES_CONFIG_SNIPPET" << 'HOOKEOF'
# ── Sage hooks — paste into your active profile's config.yaml ──
# (usually ~/.hermes/config.yaml OR $HERMES_HOME/profiles/<profile>/config.yaml)
# Run 'hermes hooks doctor' after merging to verify the wiring.
hooks:
  on_session_start:
  - command: bash "$HERMES_AGENT_HOOKS_DIR/sage-session-init.sh"
    timeout: 10
  post_tool_call:
  - command: bash "$HERMES_AGENT_HOOKS_DIR/sage-mark-edit.sh"
    matcher: write_file|patch
    timeout: 10
  pre_llm_call:
  - command: bash "$HERMES_AGENT_HOOKS_DIR/sage-inject.sh"
    timeout: 10
HOOKEOF

echo "  ✓ $HERMES_CONFIG_SNIPPET"
echo "  → Merge this into your profile config.yaml, then run 'hermes hooks doctor'"

# ── Update shell-hooks allowlist (per the Hermes consent model) ──
ALLOWLIST=""
if [ "${OS:-}" = "Windows_NT" ] || uname -s 2>/dev/null | grep -qi mingw; then
  # Willie's box: allowlist at C:/Users/willi/shell-hooks-allowlist.json (NOT ~/.hermes/)
  ALLOWLIST="$HOME/shell-hooks-allowlist.json"
else
  ALLOWLIST="$HERMES_HOME/shell-hooks-allowlist.json"
fi

if [ -f "$ALLOWLIST" ]; then
  echo ""
  echo "📝 Updating allowlist at $ALLOWLIST..."
  python3 -c "
import json, sys
from pathlib import Path
p = Path('$ALLOWLIST')
data = json.loads(p.read_text()) if p.exists() else {'approvals': []}
data.setdefault('approvals', [])
add = [
  {'event': 'on_session_start', 'command': 'bash \"$HERMES_AGENT_HOOKS_DIR/sage-session-init.sh\"'},
  {'event': 'post_tool_call', 'command': 'bash \"$HERMES_AGENT_HOOKS_DIR/sage-mark-edit.sh\"'},
  {'event': 'pre_llm_call', 'command': 'bash \"$HERMES_AGENT_HOOKS_DIR/sage-inject.sh\"'},
]
existing = {(e.get('event'), e.get('command')) for e in data['approvals']}
for entry in add:
  if (entry['event'], entry['command']) not in existing:
    data['approvals'].append(entry)
    print(f'  + {entry[\"event\"]}')
  else:
    print(f'  = {entry[\"event\"]} (already approved)')
p.write_text(json.dumps(data, indent=2))
print(f'  ✓ Allowlist updated at $ALLOWLIST')
" 2>/dev/null || echo "  ⚠ python3 not available; allowlist not auto-updated"
fi

# ═══════════════════════════════════════════════════════════════
# Slash commands — install the 16 sage-* plugin folders to $HERMES_PLUGINS_DIR
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🧠 Installing sage-* slash-command plugins → $HERMES_PLUGINS_DIR"

PLUGIN_SRC="$(dirname "$0")/sage-plugins"
if [ -d "$PLUGIN_SRC" ]; then
  mkdir -p "$HERMES_PLUGINS_DIR"
  PLUGIN_COUNT=0
  for plugin_dir in "$PLUGIN_SRC"/*/; do
    [ -d "$plugin_dir" ] || continue
    plugin_name=$(basename "$plugin_dir")
    [ -f "$plugin_dir/plugin.yaml" ] || continue
    mkdir -p "$HERMES_PLUGINS_DIR/$plugin_name"
    cp "$plugin_dir/plugin.yaml" "$HERMES_PLUGINS_DIR/$plugin_name/"
    cp "$plugin_dir/__init__.py" "$HERMES_PLUGINS_DIR/$plugin_name/"
    PLUGIN_COUNT=$((PLUGIN_COUNT + 1))
  done
  echo "  ✓ $PLUGIN_COUNT plugins installed"
  echo ""
  echo "Enable them on next session start with:"
  echo "  for p in $HERMES_PLUGINS_DIR/sage-*/; do"
  echo "    hermes plugins enable \"\$(basename \"\$p\")\""
  echo "  done"
else
  echo "  ⚠ Plugin source not found at $PLUGIN_SRC"
fi

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════"
echo "✅ Sage → Hermes setup complete"
echo ""
echo "Installed:"
echo "  ✓ AGENTS.md (replaces CLAUDE.md)"
echo "  ✓ $SKILL_COUNT skills at $HERMES_SKILLS_DIR"
echo "  ✓ $(find "$HERMES_AGENT_HOOKS_DIR" -maxdepth 1 -name '*.sh' -o -name '*.yaml' 2>/dev/null | wc -l) hook scripts at $HERMES_AGENT_HOOKS_DIR"
echo "  ✓ $HERMES_CONFIG_SNIPPET (merge into your active profile's config.yaml)"
echo ""
echo "Next steps:"
echo "  1. Merge $HERMES_CONFIG_SNIPPET into your active profile's config.yaml"
echo "  2. Run 'hermes hooks doctor' to verify all 3 hooks are healthy + allowlisted"
echo "  3. Run 'hermes plugins list' to confirm the sage-* plugins are discovered"
echo "  4. Run 'hermes plugins enable sage-<name>' for each plugin you want"
echo "  5. Restart the gateway; on next session start, type /build or /sage to test"
echo ""
