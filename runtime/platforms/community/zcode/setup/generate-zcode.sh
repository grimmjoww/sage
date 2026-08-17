#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
# Sage → ZCode Setup
# Generates AGENTS.md + .zcode/config.json hooks for ZCode, the
# Claude-plugin-compatible agent CLI. ZCode loads AGENTS.md as
# project instructions and runs Claude-format hooks — with two
# Windows-critical differences this generator accounts for:
#   1. Hook commands are executed through bash: ${CLAUDE_PLUGIN_ROOT}
#      and ${CLAUDE_PROJECT_DIR} expand to backslash paths on Windows,
#      and an UNQUOTED backslash path is mangled by bash (rc 127).
#      Every path this generator emits is double-quoted.
#   2. Hook stdout is parsed as strict JSON — plain text is discarded.
#      The session-start wrapper re-emits sage-session-init.sh output
#      as {"additionalContext": ...} so the model actually receives it.
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

SAGE_ROOT="${1:-.}"
SAGE_DIR="$SAGE_ROOT/sage"
ZCODE_DIR="$SAGE_ROOT/.zcode"
PROJECT_SAGE="$SAGE_ROOT/.sage"
CORE="$SAGE_DIR/core"

echo ""
echo "🚀 Sage → ZCode Setup"
echo "═══════════════════════════════"

if [ ! -d "$CORE" ]; then
  echo "❌ Sage framework not found at $SAGE_DIR"
  echo "   Run this from the project root where sage/ is located."
  exit 1
fi

# ── AGENTS.md — ZCode's instructions file ──
echo "📝 Generating AGENTS.md..."

SKIP_AGENTS_MD=false
if [ -f "$SAGE_ROOT/AGENTS.md" ]; then
  if head -1 "$SAGE_ROOT/AGENTS.md" 2>/dev/null | grep -q "Sage"; then
    SKIP_AGENTS_MD=false
  else
    SKIP_AGENTS_MD=true
    echo "  ⚠ AGENTS.md exists and is not Sage-generated — skipping write."
  fi
fi

if [ "$SKIP_AGENTS_MD" = false ]; then
  source "$(dirname "$0")/../../../_shared/instructions-body.sh"
  emit_instructions_body \
    | sed -e 's|`.claude/commands/\[workflow\].md`|ZCode skills / slash commands|g' \
    > "$SAGE_ROOT/AGENTS.md"

  # Inline system skills: the generated install does not depend on the
  # sage plugin being installed. (If it is, plugin skills add discovery
  # on top — the contract attests that path separately.)
  source "$(dirname "$0")/../../../_shared/system-skills.sh"
  emit_system_skills_inline "$CORE" >> "$SAGE_ROOT/AGENTS.md"
  echo "  ✓ AGENTS.md"
fi

# ── Dynamic constitution merging ──
CONST_SECTION="## Engineering Principles

Base (all projects):
1. Tests before code — every behavior has a test before implementation
2. No silent failures — errors handled, logged, or propagated
3. Secrets never in code — use env vars or secret managers
4. Dependencies explicit — declared with pinned versions
5. Changes reversible — migrations reversible, deployments rollbackable"

PRINCIPLE_NUM=5
CONST_FILE="$PROJECT_SAGE/constitution.md"
if [ -f "$CONST_FILE" ]; then
  PRESET=$(sed -n '/^extends:/s/^extends: *//p' "$CONST_FILE" 2>/dev/null)
  if [ -n "$PRESET" ] && [ "$PRESET" != "base" ] && [ "$PRESET" != "none" ]; then
    PRESET_FILE="$CORE/constitution/presets/${PRESET}.constitution.md"
    if [ -f "$PRESET_FILE" ]; then
      PRESET_PRINCIPLES=$(awk '/^[0-9]+\./{print}' "$PRESET_FILE" 2>/dev/null)
      if [ -n "$PRESET_PRINCIPLES" ]; then
        CONST_SECTION="$CONST_SECTION

Preset ($PRESET):"
        while IFS= read -r line; do
          [ -z "$line" ] && continue
          NEW_PRINCIPLE=$(echo "$line" | sed "s/^[0-9]\+\./$((++PRINCIPLE_NUM))./")
          CONST_SECTION="$CONST_SECTION
$NEW_PRINCIPLE"
        done <<< "$PRESET_PRINCIPLES"
      fi
    fi
  fi
fi

if [ "$SKIP_AGENTS_MD" = false ]; then
  python3 -c "
with open('$SAGE_ROOT/AGENTS.md', 'r') as f:
    content = f.read()
replacement = '''$CONST_SECTION'''
content = content.replace('__CONSTITUTION_PLACEHOLDER__', replacement)
with open('$SAGE_ROOT/AGENTS.md', 'w') as f:
    f.write(content)
" 2>/dev/null || true
fi

# ═══════════════════════════════════════════════════════════════
# Hooks — .zcode/config.json (workspace-level, hooks.enabled: true)
# All script paths double-quoted: ${CLAUDE_PROJECT_DIR} expands to a
# backslash path on Windows and bash mangles it unquoted (rc 127).
# ═══════════════════════════════════════════════════════════════
echo ""
echo "🪝 Generating .zcode/config.json hooks..."

# Session-start wrapper: ZCode discards non-JSON stdout, so capture
# sage-session-init.sh and re-emit it as additionalContext JSON.
mkdir -p "$PROJECT_SAGE/hooks"
cat > "$PROJECT_SAGE/hooks/zcode-session-start.sh" <<'WRAPPER'
#!/usr/bin/env bash
# ZCode adapter: re-emit sage-session-init.sh plain output as
# {"additionalContext": "..."} — the only stdout form ZCode delivers.
out="$(bash "${CLAUDE_PROJECT_DIR}/sage/hooks/scripts/sage-session-init.sh" 2>/dev/null || true)"
[ -z "$out" ] && exit 0
python3 - "$out" <<'PY' 2>/dev/null || exit 0
import json, sys
print(json.dumps({"additionalContext": sys.argv[1]}))
PY
WRAPPER

python3 - "$SAGE_ROOT" "$PROJECT_SAGE" <<'PYGEN'
import json, os, sys

sage_root, project_sage = sys.argv[1], sys.argv[2]
cfg_path = os.path.join(sage_root, ".zcode", "config.json")
os.makedirs(os.path.dirname(cfg_path), exist_ok=True)

cfg = {}
if os.path.exists(cfg_path):
    try:
        cfg = json.load(open(cfg_path))
    except Exception:
        cfg = {}

def gate(script, timeout=10):
    return {
        "type": "command",
        "command": f'bash "${{CLAUDE_PROJECT_DIR}}/sage/hooks/scripts/{script}"',
        "timeout": timeout,
    }

def group(matcher, *hooks):
    return {"matcher": matcher, "hooks": list(hooks)}

sess = {
    "type": "command",
    "command": 'bash "${CLAUDE_PROJECT_DIR}/.sage/hooks/zcode-session-start.sh"',
    "timeout": 10,
}

events = {
    "SessionStart": [group("", sess)],
    "PreToolUse": [
        group("Edit|Write|MultiEdit",
              gate("sage-spec-gate.sh"),
              gate("sage-tdd-gate.sh"),
              gate("sage-bookkeeping-gate.sh"),
              gate("sage-secrets-gate.sh")),
        group("Bash", gate("sage-verify-gate.sh")),
        group("Bash|Edit|Write|MultiEdit", gate("sage-config-gate.sh")),
    ],
    "PostToolUse": [
        group("Write|Edit",
              gate("sage-verify.sh", 30),
              gate("sage-degradation-log.sh"),
              gate("sage-manifest-sync.sh")),
        group("Bash|Edit|Write|MultiEdit", gate("sage-verify-tracker.sh")),
    ],
}

hooks = cfg.get("hooks") or {}
cfg["hooks"] = {"enabled": True, "timeoutMs": hooks.get("timeoutMs", 60000),
                "maxOutputBytes": hooks.get("maxOutputBytes", 10240),
                "events": events}

with open(cfg_path, "w", newline="\n") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
print("  ✓ .zcode/config.json (hooks enabled, quoted paths)")
PYGEN

# ── Project state — .sage/ initialization ──
echo ""
echo "📊 Checking project state..."
if [ -d "$PROJECT_SAGE" ]; then
  echo "  ✓ .sage/ already exists"
else
  mkdir -p "$PROJECT_SAGE/work" "$PROJECT_SAGE/docs"
  echo "  ✓ .sage/ initialized"
fi

echo ""
echo "═══════════════════════════════"
echo "✅ Sage → ZCode setup complete"
echo ""
echo "Files written:"
echo "  AGENTS.md                (loaded by ZCode as project instructions)"
echo "  .zcode/config.json       (hooks: gates + session pickup, Windows-safe paths)"
echo "  .sage/hooks/             (zcode session-start JSON adapter)"
echo ""
echo "Next steps:"
echo "  - Restart your ZCode session so the hooks load"
echo "  - /sage or describe what you want to build"
echo "  - python3 must resolve to a real interpreter on PATH (not the"
echo "    Windows Store stub) — the gates call it on every edit."
echo ""
