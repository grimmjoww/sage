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

# Discover installed profiles — for multi-profile setups (HERMES_HOME set),
# hooks go into EACH profile's config + agent-hooks. For single-profile
# setups (HERMES_HOME unset → $HOME/.hermes), there's only one profile dir.
#
# Use --profile=<name> to target a single profile (RECOMMENDED).
# Use --all-profiles to target every profile (default, but explicit).
HERMES_PROFILES_ROOT="$HERMES_HOME/profiles"
TARGET_PROFILE=""
TARGET_ALL_PROFILES=true
for arg in "$@"; do
  case "$arg" in
    --profile=*) TARGET_PROFILE="${arg#--profile=}"; TARGET_ALL_PROFILES=false ;;
    --all-profiles) TARGET_ALL_PROFILES=true ;;
  esac
done
HERMES_PROFILES=()
if [ -d "$HERMES_PROFILES_ROOT" ]; then
  if [ -n "$TARGET_PROFILE" ]; then
    # Targeted install: only the named profile
    if [ -d "$HERMES_PROFILES_ROOT/$TARGET_PROFILE" ]; then
      HERMES_PROFILES=("$HERMES_PROFILES_ROOT/$TARGET_PROFILE")
    else
      echo "❌ Profile '$TARGET_PROFILE' not found at $HERMES_PROFILES_ROOT/"
      echo "   Available profiles: $(ls "$HERMES_PROFILES_ROOT" | tr '\n' ' ')"
      exit 1
    fi
  else
    for prof in "$HERMES_PROFILES_ROOT"/*/; do
      [ -d "$prof" ] || continue
      HERMES_PROFILES+=("$prof")
    done
  fi
fi

# If no profiles dir exists, install hooks into HERMES_HOME root + write a
# top-level config.yaml hooks: block (single-profile default).
if [ "${#HERMES_PROFILES[@]}" -eq 0 ]; then
  HERMES_PROFILES=("$HERMES_HOME")
fi

HERMES_PLUGINS_DIR="$HERMES_HOME/plugins"
HERMES_SKILLS_DIR="$HERMES_HOME/skills"

CORE="$SAGE_DIR/core"
PLUGIN_TEMPLATE="$(dirname "$0")/sage-plugin-contents"

echo ""
echo "🚀 Sage → Hermes Setup (canonical shape)"
echo "═══════════════════════════════════════════════════════════════"
echo "Hermes home:  $HERMES_HOME"
echo "Plugins dir:  $HERMES_PLUGINS_DIR/sage/"
echo "Skills dir:   $HERMES_SKILLS_DIR"
echo "Agent hooks:  per-profile agent-hooks/ (discovered from $HERMES_HOME/profiles/*/)"
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

SAGE_PLUGIN="$HERMES_PLUGINS_DIR/sage"

# ═══════════════════════════════════════════════════════════════
# Plugin — install at top-level, symlink into each profile
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📦 Installing sage plugin → $SAGE_PLUGIN"

mkdir -p "$SAGE_PLUGIN"

# Clean any previous broken sage-* plugins (from the old shape)
for old_plugin in "$HERMES_PLUGINS_DIR"/sage-*/; do
  [ -d "$old_plugin" ] && rm -rf "$old_plugin"
done
# Also clean from each profile's plugin dir
for prof_dir in "${HERMES_PROFILES[@]}"; do
  [ "$prof_dir" = "$HERMES_HOME" ] && continue  # skip HERMES_HOME root in single-profile mode
  for old_plugin in "$prof_dir"/plugins/sage-*/; do
    [ -d "$old_plugin" ] && rm -rf "$old_plugin"
  done
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

# Symlink the plugin into each profile's plugin dir so profile-scoped
# config can discover it via get_hermes_home() / 'plugins'.
# (Per hermes-cli/plugins.py:1240, profile plugins come from the profile's
# own plugins/ dir. Symlinking into each keeps the source single.)
#
# On Windows, use 'cmd /c mklink /J' to create a Junction (no admin needed,
# works under Git-bash and WSL). On Linux/macOS, plain `ln -s` works.
for prof_dir in "${HERMES_PROFILES[@]}"; do
  [ "$prof_dir" = "$HERMES_HOME" ] && continue  # skip HERMES_HOME root
  prof_plugins="$prof_dir/plugins"
  mkdir -p "$prof_plugins"
  if [ "$prof_plugins" != "$HERMES_PLUGINS_DIR" ]; then
    if [ -d "$prof_plugins/sage" ] || [ -L "$prof_plugins/sage" ]; then
      rm -rf "$prof_plugins/sage"
    fi
    SAGE_PLUGIN_WIN=$(echo "$SAGE_PLUGIN" | sed 's|^/c/|C:/|; s|^/g/|G:/|')
    PROFILE_PLUGINS_WIN=$(echo "$prof_plugins" | sed 's|^/c/|C:/|; s|^/g/|G:/|')
    if [ "${OS:-}" = "Windows_NT" ] || uname -s 2>/dev/null | grep -qi mingw; then
      # Use Windows Junction (no admin needed for user-writable paths)
      cmd.exe //c "mklink /J \"${PROFILE_PLUGINS_WIN}\\sage\" \"${SAGE_PLUGIN_WIN}\"" >/dev/null 2>&1
      echo "  ✓ $(basename "$prof_dir")/plugins/sage → ${SAGE_PLUGIN_WIN} (junction)"
    else
      ln -s "$SAGE_PLUGIN" "$prof_plugins/sage"
      echo "  ✓ $(basename "$prof_dir")/plugins/sage → ${SAGE_PLUGIN_WIN} (symlink)"
    fi
  fi
done

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
# Gate scripts + session-init hook — DEPLOYED TO EACH PROFILE'S agent-hooks/
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🔒 Deploying gate scripts + session-init → per-profile agent-hooks/"

GATE_SCRIPTS="$CORE/gates/scripts"
GATE_CONFIG="$CORE/gates/_config/gate-modes.yaml"
HOOK_SRC="$CORE/../runtime/platforms/hermes/hooks/sage-session-init.sh"

for prof_dir in "${HERMES_PROFILES[@]}"; do
  prof_hooks_dir="$prof_dir/agent-hooks"
  mkdir -p "$prof_hooks_dir"

  if [ -d "$GATE_SCRIPTS" ]; then
    for script in "$GATE_SCRIPTS"/*.sh; do
      [ -f "$script" ] || continue
      cp "$script" "$prof_hooks_dir/"
      chmod +x "$prof_hooks_dir/$(basename "$script")"
    done
  fi
  [ -f "$GATE_CONFIG" ] && cp "$GATE_CONFIG" "$prof_hooks_dir/"
  [ -f "$HOOK_SRC" ] && cp "$HOOK_SRC" "$prof_hooks_dir/sage-session-init.sh" && chmod +x "$prof_hooks_dir/sage-session-init.sh"
  echo "  ✓ $(basename "$prof_dir")/agent-hooks/ ($(ls "$prof_hooks_dir" | wc -l) files)"
done

# ═══════════════════════════════════════════════════════════════
# config.yaml hooks: block — DIRECTLY UPDATE EACH PROFILE'S config.yaml
# (no config-snippet file with REPLACE_ME placeholder; that was the broken pattern)
# ═══════════════════════════════════════════════════════════════
echo ""
echo "📋 Updating hooks: block in each profile's config.yaml"

for prof_dir in "${HERMES_PROFILES[@]}"; do
  prof_cfg="$prof_dir/config.yaml"
  prof_name=$(basename "$prof_dir")
  prof_hooks_dir="$prof_dir/agent-hooks"

  # If config.yaml doesn't exist yet (fresh install), create a minimal one
  # with the hooks: block already populated. This avoids the "hooks
  # installed but config silent" gap for new users.
  if [ ! -f "$prof_cfg" ]; then
    if [ ! -d "$prof_dir" ]; then
      mkdir -p "$prof_dir"
    fi
    cat > "$prof_cfg" << 'NEWCFG'
# Minimal hermes config — populated by sage init --platform hermes
hooks: {}
hooks_auto_accept: true
platforms: []
NEWCFG
    echo "  ✓ $prof_name/config.yaml (created with hooks: skeleton)"
  fi

  # Use python3 to safely merge the hooks: block into config.yaml
  python3 -c "
import yaml, sys
from pathlib import Path
p = Path(r'''$prof_cfg''')
hooks_dir = r'''$prof_hooks_dir'''
data = yaml.safe_load(p.read_text()) or {}
if not isinstance(data, dict):
    data = {}
hooks_block = {
    'on_session_start': [{'command': f'bash {hooks_dir}/sage-session-init.sh', 'timeout': 10}],
    'post_tool_call':   [{'command': f'bash {hooks_dir}/sage-mark-edit.sh', 'matcher': 'write_file|patch', 'timeout': 10}],
    'pre_llm_call':      [{'command': f'bash {hooks_dir}/sage-inject.sh', 'timeout': 10}],
}
data['hooks'] = hooks_block
# Ensure hooks_auto_accept: true so first run doesn't prompt
data.setdefault('hooks_auto_accept', True)
p.write_text(yaml.safe_dump(data, sort_keys=False, default_flow_style=False))
print(f'  ✓ {r'''$prof_name'''}/config.yaml: hooks: block written')
" 2>/dev/null || echo "  ⚠ python3+pyyaml not available; manual merge required for $prof_name"
done

# ═══════════════════════════════════════════════════════════════
# Allowlist — auto-update at $HOME/shell-hooks-allowlist.json (not ~/.hermes/!)
# Each profile's hooks need their own approval entries in the allowlist
# ═══════════════════════════════════════════════════════════════
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
  {'event': 'on_session_start', 'command': 'bash \"G:/hermes/profiles/<profile>/agent-hooks/sage-session-init.sh\"'},
  {'event': 'post_tool_call', 'command': 'bash \"G:/hermes/profiles/<profile>/agent-hooks/sage-mark-edit.sh\"'},
  {'event': 'pre_llm_call', 'command': 'bash \"G:/hermes/profiles/<profile>/agent-hooks/sage-inject.sh\"'},
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
PROFILE_PLUGIN_SYMLINKS=$(for prof_dir in "${HERMES_PROFILES[@]}"; do [ "$prof_dir" != "$HERMES_HOME" ] && echo "Y"; done | wc -l)
if [ "$PROFILE_PLUGIN_SYMLINKS" -gt 0 ]; then
  echo "  ✓ Symlinked into $PROFILE_PLUGIN_SYMLINKS profile plugin dirs"
fi
echo "  ✓ Top-level skills: $HERMES_SKILLS_DIR/<n>/ (auto-discovered)"
echo "  ✓ Gate scripts + session-init at each profile's agent-hooks/"
echo "  ✓ Hooks block written to each profile's config.yaml"
echo ""
echo "Next steps:"
echo "  1. Run 'hermes plugins enable sage' to load the plugin"
echo "  2. Run 'hermes hooks doctor' to verify the 3 hooks (per-profile)"
echo "  3. Restart the gateway; on next session, type /sage or /build"
echo ""
