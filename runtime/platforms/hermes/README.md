# Sage on Hermes

Setup guide for using [Sage](https://github.com/xoai/sage) with
[Hermes Agent](https://hermes-agent.nousresearch.com).

## Quick Setup

```bash
# 1. Initialize Sage in your project (auto-detects Hermes from HERMES_HOME/plugins/)
sage init

# 2. Run the hermes-specific generator — installs the COMPLETE sage ecosystem:
#    - AGENTS.md (constitution, replaces CLAUDE.md)
#    - $HERMES_HOME/plugins/sage/  (ONE plugin with skills/, agents/, references/, hooks/, scripts/)
#    - $HERMES_HOME/skills/<n>/  (top-level skills, auto-discovered by Hermes)
#    - $HERMES_HOME/hooks/sage/  (4 shell hooks (on_session_start + post_tool_call + pre_llm_call) + 4 quality gate scripts + gate-modes.yaml)
#    - $HERMES_HOME/config-snippet-hermes.yaml (merge into your active profile's config.yaml)
bash sage/runtime/platforms/hermes/setup/generate-hermes.sh .

# 3. Merge the config snippet (replace REPLACE_ME with your profile name first):
#    sed -i 's/REPLACE_ME/your-profile-name/g' $HERMES_HOME/config-snippet-hermes.yaml
#    cat $HERMES_HOME/config-snippet-hermes.yaml >> $HERMES_HOME/profiles/your-profile/config.yaml

# 4. Enable the plugin + verify hooks
hermes plugins enable sage
hermes hooks doctor

# 5. Restart the gateway; on next session, type /sage or /build to test.
```

On next Hermes session start, slash commands will be available:
`/sage`, `/build`, `/fix`, `/architect`, `/analyze`, `/learn`, `/map`,
`/qa`, `/reflect`, `/research`, `/review`, `/status`, `/design`,
`/design-review`, `/continue`.

The full skill library (~50 skills at `$HERMES_HOME/skills/<n>/`) is
auto-discovered by Hermes at session start — loadable via
`skill_view("sage:<skill-name>")` or appearing in autocomplete.

## What Gets Installed

```
your-project/
├── AGENTS.md                       # Always-on project instructions (Hermes reads AGENTS.md, not CLAUDE.md)
├── skills/                         # Sage workflows emitted as Hermes skills (slash-commandable)
│   ├── sage/                       # /sage — workflow router
│   ├── build/                      # /build — feature development
│   ├── fix/                        # /fix — debug and patch
│   └── ... (slash commands only — the rest of the 16 go in the plugin below)
└── .sage/                          # Project state (platform-agnostic)
```

`$HERMES_HOME/plugins/sage/` — the **single** sage plugin (per Hermes plugin
guide, NOT 16 separate plugins):

```
sage/
├── plugin.yaml              # name=sage, version=1.0.9, description, etc.
├── __init__.py              # def register(ctx): walks skills/, calls ctx.register_skill() per skill, plus ctx.register_command() for the 15 slash commands
├── skills/                  # 53 SKILL.md files (15 slash-commanded + 38 plain)
│   ├── sage/                # slash command
│   ├── build/               # slash command
│   ├── analyze/             # slash command
│   ├── ... (15 total)
│   ├── api/                 # plain skill (auto-loaded)
│   ├── baas/                # plain skill
│   └── ... (38 total)
├── agents/                  # 5 persona files
│   ├── analyst.md           # senior product analyst persona
│   ├── architect.md         # system architect persona
│   ├── debugger.md          # debugging specialist persona
│   ├── developer.md         # full-stack dev persona
│   └── reviewer.md          # code review persona
├── references/              # 10 template files
│   ├── decision-template.md
│   ├── design-review-template.md
│   ├── full-spec-template.md
│   ├── journal-template.md
│   ├── lightpanda-setup.md
│   ├── manifest-template.md
│   ├── plan-template.md
│   ├── qa-report-template.md
│   ├── skill-authoring-guide.md
│   └── spec-template.md
├── hooks/                   # plugin-internal hooks (different from shell-hooks)
│   └── hooks.json           # SessionStart + PostToolUse plugin-internal hooks
└── scripts/                 # plugin-internal sage CLI
    └── sage                 # full copy of bin/sage (1838 lines)
```

`$HERMES_HOME/skills/<n>/` — top-level auto-discovered skills (separate from
the plugin's bundled skills/):

```
$HERMES_HOME/skills/
├── api/                       # API design (13 common mistakes)
├── autoresearch/              # Autonomous iteration
├── baas/                      # Backend-as-a-Service
├── flutter/                  # Flutter mobile
├── jtbd/                      # Jobs To Be Done
├── mobile/                    # Mobile dev
├── nextjs/                    # Next.js patterns
├── opportunity-map/          # JTBD → opportunity mapping
├── pack-* (6 dirs)            # Pack discovery, drafting, observing, etc.
├── prd/                       # Product Requirements Doc
├── problem-solving/          # Systematic problem solving
├── product-management/       # PM workflow
├── react/                     # React patterns
├── react-native/              # React Native
├── sage-memory/               # sage-memory knowledge graph
├── sage-ontology/             # Typed ontology
├── sage-self-learning/        # Self-learning skill
├── skill-builder/             # Skill authoring
├── stack-* (4 dirs)           # Stack-specific patterns
├── user-interview/            # User interview
├── ux-* (8 dirs)              # UX research, design, audit, etc.
├── web/                       # Web patterns
└── ... (40 total)
```

These are auto-loaded by Hermes at session start, independent of any plugin.

`$HERMES_HOME/hooks/sage/` — shell-hook scripts (canonical Gateway Hooks shape):

```
hooks/sage/
├── sage-session-init.sh         # Fires on_session_start — emits Sage context block
├── sage-mark-edit.sh            # Fires post_tool_call (write_file|patch) — marks touched files
├── sage-inject.sh               # Fires pre_llm_call — injects sage workflow hints as {context: ...}
├── sage-hallucination-check.sh  # Quality gate 4
├── sage-spec-check.sh           # Quality gate 1
├── sage-verify.sh               # Quality gate 5
├── sage-visual-gate.sh          # Visual gate
└── gate-modes.yaml              # Gate activation config
```

## How It Works on Hermes

Hermes is a Python agent runtime with three surfaces Sage integrates with:

### 1. Slash commands (in-session, user-facing)

`ctx.register_command(name, handler, description)` in the plugin's `__init__.py`.
15 SKILL.md files in the plugin have `disable-model-invocation: true` in
their frontmatter — the plugin iterates `skills/`, registers each as a
skill AND registers the matching slash command. The handler returns the
SKILL.md body as a string.

### 2. Skills (auto-loaded at session start)

Hermes auto-discovers skills at `$HERMES_HOME/skills/<n>/SKILL.md` AND
at plugin-bundled `skills/<n>/SKILL.md`. Each skill has frontmatter
(name, description, version, optional disable-model-invocation). The
plugin's `__init__.py` walks its `skills/` subdir and calls
`ctx.register_skill(child.name, skill_md)` for each.

### 3. Shell hooks (event-driven, observer or in-session-injector)

Three hooks fire from `~/.hermes/config.yaml` under `hooks:`:

| Event | Script | Behavior |
|---|---|---|
| `on_session_start` | `sage-session-init.sh` | Observer — emits `## Sage Context (auto-injected)` block on stdout, parsed but discarded |
| `post_tool_call` (matcher `write_file|patch`) | `sage-mark-edit.sh` | Observer — appends marked-edit line to `hooks.log` |
| `pre_llm_call` | `sage-inject.sh` | Injector — returns `{"context": "[sage hint: workflow=/X active_cycle=Y]"}` on stdout (parsed by hermes_cli/plugins.py and appended to next user message) |

Per the Hermes shell-hook contract (`agent/shell_hooks.py`), stdin is JSON
with this shape:
```
{
  "hook_event_name": "pre_llm_call",
  "session_id": "...",
  "cwd": "...",
  "extra": {<event-specific kwargs>}
}
```
**All event-specific kwargs live under `.extra`**, top-level keys are
reserved for the canonical wire fields. The hook reads `.extra.user_message`
not `.user_message`. Stdout must be JSON for any return value to be parsed.

## Why a separate platform adapter?

The 5 platforms upstream ships (claude-code, antigravity, codex, opencode,
gemini-cli) all use `.claude/commands/` or similar per-platform paths for
slash commands. Hermes's slash-command surface is the **plugin system**, and
its skill discovery surface is `~/.hermes/skills/<n>/`. The hermes adapter
adapts the bash generator's output paths to those locations.

Critically: the hermes adapter bundles the **entire sage ecosystem as ONE
plugin** (`sage/`) with skills/, agents/, references/, hooks/, scripts/
inside it. The previous broken port split this across 16 separate
`sage-*` plugin folders — that violated the Hermes plugin guide's
"plugin = directory with manifest + init + skills" structure.

## Compatibility caveats

- **Slash-command names** — bare names (`build`, `fix`, etc.) in
  `ctx.register_command()`; Hermes adds the `/` prefix at the prompt.
  Conflict protection: built-in names (help, model, new) take precedence.
- **Plugin source-of-truth** — `runtime/platforms/hermes/setup/sage-plugin-contents/`
  ships the 53 skills + 5 agents + 10 references + hooks.json + scripts/sage.
  The generator copies this tree to `$HERMES_HOME/plugins/sage/`.
- **Top-level skills** — the 40 SKILL.md files in `sage/skills/` (top-level
  in the sage repo) are auto-discovered by Hermes. The generator copies
  them to `$HERMES_HOME/skills/<n>/`.
- **Allowlist path** — `$HOME/shell-hooks-allowlist.json` on Windows (NOT
  `~/.hermes/` as upstream docs claim; see LRN d9645db2).
- **AGENTS.md vs CLAUDE.md** — Hermes reads `AGENTS.md`, claude-code reads
  `CLAUDE.md`. The hermes generator emits `AGENTS.md`.
- **plugin.json → plugin.yaml** — Hermes uses YAML manifests (`plugin.yaml`).
  Same metadata fields: name, version, description, author.

## Reference docs

- Hermes plugin authoring: https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin
- Hermes shell hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- Hermes skill authoring: https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills
- Hermes plugin discovery: `hermes_cli/plugins.py` lines 1230-1245
- Shell-hook payload shape: `agent/shell_hooks.py:_serialize_payload`
- Hermes home resolution: `hermes_constants.py:get_hermes_home`
- Canonical Sage install: `tools/sage-claude-plugin/` in the sage repo (this port's reference shape)
