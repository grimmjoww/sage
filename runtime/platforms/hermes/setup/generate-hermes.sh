#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage → Hermes Setup (canonical shape)
# Generates the COMPLETE sage install for Hermes:
#   - AGENTS.md (constitution)
#   - $HERMES_HOME/plugins/sage/ (one plugin, with skills/ + agents/ + references/ + hooks/ + scripts/)
#   - $HERMES_HOME/skills/ (top-level auto-discovered skills, separate from plugin)
#   - agent-hooks/ (3 shell hooks for on_session_start + post_tool_call + pre_llm_call)
#   - shell-hooks-allowlist.json (consent record auto-updated)
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SAGE_ROOT="${1:-.}"
SAGE_DIR="$SAGE_ROOT/sage"
HERMES_ROOT="${HERMES_ROOT:-$SAGE_ROOT}"

# Hermes paths
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
if [ "${OS:-}" = "Windows_NT" ] || uname -s 2>/dev/null | grep -qi mingw; then
  HERMES_HOME="${HERMES_HOME:-$LOCALAPPDATA/hermes}"
fi

HERMES_PLUGINS_DIR="$HERMES_HOME/plugins"
HERMES_SKILLS_DIR="$HERMES_HOME/skills"
HERMES_AGENT_HOOKS_DIR="$HERMES_HOME/agent-hooks"
HERMES_CONFIG_SNIPPET="$HERMES_HOME/config-snippet-hermes.yaml"

CORE="$SAGE_DIR/core"
PLUGIN_TEMPLATE="$(dirname "$0")/sage-plugin-contents"

echo ""
echo "🚀 Sage → Hermes Setup (canonical shape)"
echo "═══════════════════════════════════════════════════════════════"
echo "Hermes home:  $HERMES_HOME"
echo "Plugins dir:  $HERMES_PLUGINS_DIR/sage/"
echo "Skills dir:   $HERMES_SKILLS_DIR"
echo "Agent hooks:  $HERMES_AGENT_HOOKS_DIR"
echo ""

# ── Validate ──
if [ ! -d "$CORE" ]; then
  echo "❌ Sage framework not found at $SAGE_DIR"
  echo "   Run this from the project root where sage/ is located."
  exit 1
fi
if [ ! -d "$PLUGIN_TEMPLATE" ]; then
  echo "❌ Plugin template not found at $PLUGIN_TEMPLATE"
  echo "   The hermes adapter should ship 'setup/sage-plugin-contents/' alongside 'generate-hermes.sh'."
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
# AGENTS.md — constitution
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📝 Generating AGENTS.md..."
source "$(dirname "$0")/../../_shared/instructions-body.sh"
emit_instructions_body > "$SAGE_ROOT/AGENTS.md"

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
fi

python3 -c "
import sys
with open('$SAGE_ROOT/AGENTS.md', 'r') as f:
    content = f.read()
replacement = '''$CONST_SECTION'''
content = content.replace('__CONSTITUTION_PLACEHOLDER__', replacement)
with open('$SAGE_ROOT/AGENTS.md', 'w') as f:
    f.write(content)
" 2>/dev/null || echo "  ⚠ python3 not available; AGENTS.md constitution placeholder not substituted"

echo "  ✓ AGENTS.md"

# ═══════════════════════════════════════════════════════════════
# Plugin — ONE plugin with everything bundled
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📦 Installing sage plugin → $HERMES_PLUGINS_DIR/sage/"

SAGE_PLUGIN="$HERMES_PLUGINS_DIR/sage"
mkdir -p "$SAGE_PLUGIN"

# Clean any previous broken sage-* plugins (from the old shape)
for old_plugin in "$HERMES_PLUGINS_DIR"/sage-*/; do
  [ -d "$old_plugin" ] && rm -rf "$old_plugin"
done

# Copy the entire plugin template dir
for sub in skills agents references hooks scripts; do
  if [ -d "$PLUGIN_TEMPLATE/$sub" ]; then
    mkdir -p "$SAGE_PLUGIN/$sub"
    cp -r "$PLUGIN_TEMPLATE/$sub/." "$SAGE_PLUGIN/$sub/"
  fi
done

# plugin.yaml + __init__.py
[ -f "$PLUGIN_TEMPLATE/plugin.yaml" ] && cp "$PLUGIN_TEMPLATE/plugin.yaml" "$SAGE_PLUGIN/"
[ -f "$PLUGIN_TEMPLATE/__init__.py" ] && cp "$PLUGIN_TEMPLATE/__init__.py" "$SAGE_PLUGIN/"

# Make scripts + init.py executable
chmod +x "$SAGE_PLUGIN/__init__.py" 2>/dev/null
[ -d "$SAGE_PLUGIN/scripts" ] && chmod +x "$SAGE_PLUGIN/scripts/sage" 2>/dev/null

SKILL_COUNT=$(find "$SAGE_PLUGIN/skills" -name "SKILL.md" 2>/dev/null | wc -l)
AGENT_COUNT=$(find "$SAGE_PLUGIN/agents" -name "*.md" 2>/dev/null | wc -l)
REF_COUNT=$(find "$SAGE_PLUGIN/references" -name "*.md" 2>/dev/null | wc -l)
echo "  ✓ plugin.yaml + __init__.py"
echo "  ✓ $SKILL_COUNT skills (in skills/)"
echo "  ✓ $AGENT_COUNT agent personas (in agents/)"
echo "  ✓ $REF_COUNT reference templates (in references/)"

# ═══════════════════════════════════════════════════════════════
# Top-level skills (auto-discovered by Hermes)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📚 Installing top-level skills → $HERMES_SKILLS_DIR"

if [ -d "$SAGE_DIR/skills" ]; then
  mkdir -p "$HERMES_SKILLS_DIR"
  TOP_COUNT=0
  for skill_dir in "$SAGE_DIR/skills"/*/; do
    [ -d "$skill_dir" ] || continue
    name=$(basename "$skill_dir")
    [ -f "$skill_dir/SKILL.md" ] || continue
    mkdir -p "$HERMES_SKILLS_DIR/$name"
    # Copy all files in the skill dir (README.md, SKILL.md, tests.md, subdirs)
    cp -r "$skill_dir/." "$HERMES_SKILLS_DIR/$name/" 2>/dev/null
    TOP_COUNT=$((TOP_COUNT + 1))
  done
  echo "  ✓ $TOP_COUNT skills copied"
fi

# ═══════════════════════════════════════════════════════════════
# Project state — .sage/ initialization
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
# Gate scripts + session-init hook at agent-hooks/
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🔒 Deploying gate scripts → $HERMES_AGENT_HOOKS_DIR"

mkdir -p "$HERMES_AGENT_HOOKS_DIR"
GATE_SCRIPTS="$CORE/gates/scripts"

if [ -d "$GATE_SCRIPTS" ]; then
  for script in "$GATE_SCRIPTS"/*.sh; do
    [ -f "$script" ] || continue
    cp "$script" "$HERMES_AGENT_HOOKS_DIR/"
    chmod +x "$HERMES_AGENT_HOOKS_DIR/$(basename "$script")"
    echo "  ✓ $(basename "$script")"
  done
fi

GATE_CONFIG="$CORE/gates/_config/gate-modes.yaml"
if [ -f "$GATE_CONFIG" ]; then
  cp "$GATE_CONFIG" "$HERMES_AGENT_HOOKS_DIR/"
  echo "  ✓ gate-modes.yaml"
fi

# Session-init hook — the hermes-adapted version
HOOK_SRC="$CORE/../runtime/platforms/hermes/hooks/sage-session-init.sh"
if [ -f "$HOOK_SRC" ]; then
  cp "$HOOK_SRC" "$HERMES_AGENT_HOOKS_DIR/sage-session-init.sh"
  chmod +x "$HERMES_AGENT_HOOKS_DIR/sage-session-init.sh"
  echo "  ✓ sage-session-init.sh (cwd-adapted)"
fi

# ═══════════════════════════════════════════════════════════════
# config-snippet + allowlist update
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📋 Writing config snippet → $HERMES_CONFIG_SNIPPET"

cat > "$HERMES_CONFIG_SNIPPET" << 'HOOKEOF'
# ── Sage hooks — merge into your active profile's config.yaml ──
# (usually ~/.hermes/config.yaml OR $HERMES_HOME/profiles/<profile>/config.yaml)
hooks:
  on_session_start:
  - command: bash "G:/hermes/profiles/REPLACE_ME/agent-hooks/sage-session-init.sh"
    timeout: 10
  post_tool_call:
  - command: bash "G:/hermes/profiles/REPLACE_ME/agent-hooks/sage-mark-edit.sh"
    matcher: write_file|patch
    timeout: 10
  pre_llm_call:
  - command: bash "G:/hermes/profiles/REPLACE_ME/agent-hooks/sage-inject.sh"
    timeout: 10
HOOKEOF

echo "  ✓ $HERMES_CONFIG_SNIPPET"
echo "  → Replace 'REPLACE_ME' with your profile name, then merge."

# Allowlist — auto-update at $HOME/shell-hooks-allowlist.json (not ~/.hermes/!)
ALLOWLIST=""
if [ "${OS:-}" = "Windows_NT" ] || uname -s 2>/dev/null | grep -qi mingw; then
  ALLOWLIST="$HOME/shell-hooks-allowlist.json"
else
  ALLOWLIST="$HERMES_HOME/shell-hooks-allowlist.json"
fi

if [ -d "$(dirname "$ALLOWLIST")" ]; then
  python3 -c "
import json
from pathlib import Path
p = Path('$ALLOWLIST')
data = json.loads(p.read_text()) if p.exists() else {'approvals': []}
data.setdefault('approvals', [])
add = [
  {'event': 'on_session_start', 'command': 'bash \"G:/hermes/profiles/REPLACE_ME/agent-hooks/sage-session-init.sh\"'},
  {'event': 'post_tool_call', 'command': 'bash \"G:/hermes/profiles/REPLACE_ME/agent-hooks/sage-mark-edit.sh\"'},
  {'event': 'pre_llm_call', 'command': 'bash \"G:/hermes/profiles/REPLACE_ME/agent-hooks/sage-inject.sh\"'},
]
existing = {(e.get('event'), e.get('command')) for e in data['approvals']}
for entry in add:
  if (entry['event'], entry['command']) not in existing:
    data['approvals'].append(entry)
p.write_text(json.dumps(data, indent=2))
print(f'  ✓ Allowlist updated at $ALLOWLIST')
" 2>/dev/null || echo "  ⚠ python3 not available; allowlist not auto-updated"
fi

# ═══════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Sage → Hermes setup complete (canonical shape)"
echo ""
echo "Installed:"
echo "  ✓ AGENTS.md at $SAGE_ROOT/"
echo "  ✓ Plugin: $SAGE_PLUGIN/"
echo "      plugin.yaml + __init__.py"
echo "      skills/ ($SKILL_COUNT SKILL.md files; 15 slash-commanded)"
echo "      agents/ ($AGENT_COUNT personas)"
echo "      references/ ($REF_COUNT templates)"
echo "      hooks/hooks.json + scripts/sage"
echo "  ✓ Top-level skills: $HERMES_SKILLS_DIR/<n>/ (auto-discovered)"
echo "  ✓ Gate scripts + session-init at $HERMES_AGENT_HOOKS_DIR/"
echo "  ✓ $HERMES_CONFIG_SNIPPET (merge into your profile's config.yaml)"
echo ""
echo "Next steps:"
echo "  1. Merge $HERMES_CONFIG_SNIPPET into your active profile's config.yaml"
echo "     (replace 'REPLACE_ME' with your profile name first)"
echo "  2. Run 'hermes plugins enable sage' to load the plugin"
echo "  3. Run 'hermes hooks doctor' to verify the 3 hooks"
echo "  4. Restart the gateway; on next session, type /sage or /build"
echo ""
