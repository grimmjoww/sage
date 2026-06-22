# Sage on Hermes

Setup guide for using [Sage](https://github.com/xoai/sage) with
[Hermes Agent](https://hermes-agent.nousresearch.com).

## Quick Setup

```bash
# 1. Initialize Sage in your project (auto-detects Hermes from HERMES_HOME/plugins/)
sage init

# 2. Run the hermes-specific generator (writes skills/ + agent-hooks/ + AGENTS.md)
bash sage/runtime/platforms/hermes/setup/generate-hermes.sh .

# 3. Merge the config snippet into your active profile's config.yaml
#    (snippet written to $HERMES_HOME/config-snippet-hermes.yaml)
cat $HERMES_HOME/config-snippet-hermes.yaml >> $HERMES_HOME/profiles/$(hermes profile list --plain | head -1)/config.yaml

# 4. Install the 16 sage-* slash-command plugins
mkdir -p $HERMES_HOME/plugins
for p in sage-analyze sage-architect sage-autoresearch sage-build sage-continue \
         sage-design sage-design-review sage-fix sage-learn sage-map sage-qa \
         sage-reflect sage-research sage-review sage-sage sage-status; do
  mkdir -p "$HERMES_HOME/plugins/$p"
  cp "sage/runtime/platforms/hermes/setup/sage-plugins/$p/plugin.yaml" \
     "sage/runtime/platforms/hermes/setup/sage-plugins/$p/__init__.py" \
     "$HERMES_HOME/plugins/$p/"
done

# 5. Enable each plugin and run hermes hooks doctor to verify wiring
for p in sage-analyze sage-architect sage-autoresearch sage-build sage-continue \
         sage-design sage-design-review sage-fix sage-learn sage-map sage-qa \
         sage-reflect sage-research sage-review sage-sage sage-status; do
  hermes plugins enable "$p"
done
hermes hooks doctor
```

On next Hermes session start the slash commands will be available:
`/sage`, `/build`, `/fix`, `/architect`, `/analyze`, `/learn`, `/map`,
`/qa`, `/reflect`, `/research`, `/review`, `/status`, `/design`,
`/design-review`, `/continue`, `/autoresearch`.

## What Gets Generated

```
your-project/
├── AGENTS.md                       # Always-on project instructions (Hermes reads AGENTS.md, not CLAUDE.md)
├── skills/                         # Hermes-native SKILL.md layout
│   ├── sage/                       # /sage — intelligent entry point
│   ├── build/                      # /build — feature development
│   ├── fix/                        # /fix — debug and patch
│   ├── architect/                  # /architect — system design
│   ├── analyze/                    # /analyze — UX/codebase audit
│   ├── learn/                      # /learn — scan codebase → memory
│   ├── map/                        # /map — ontology mapping
│   ├── qa/                         # /qa — quality assurance
│   ├── reflect/                    # /reflect — review the cycle
│   ├── research/                   # /research — user interview
│   ├── review/                     # /review — independent review (delegates to sage-reviewer)
│   ├── status/                     # /status — project state
│   ├── design/                     # /design — UX brief → spec → copy
│   ├── design-review/              # /design-review — design quality audit
│   ├── continue/                   # /continue — resume a cycle
│   ├── build-x/                    # /build-x — multi-agent variant
│   └── autoresearch/               # /autoresearch — autonomous iteration
├── agent-hooks/                    # Shell-hook scripts Hermes invokes per event
│   ├── sage-session-init.sh        # Fires on_session_start — injects Sage context
│   ├── sage-mark-edit.sh           # Fires post_tool_call (write_file/patch) — marks touched files
│   ├── sage-inject.sh             # Fires pre_llm_call — injects sage workflow hints
│   ├── sage-hallucination-check.sh # Quality gate 4
│   ├── sage-spec-check.sh          # Quality gate 1
│   ├── sage-verify.sh             # Quality gate 5
│   ├── sage-visual-gate.sh         # Visual gate
│   └── gate-modes.yaml             # Gate activation config
└── .sage/                          # Project state (platform-agnostic)
```

Slash-command plugins (installed to `$HERMES_HOME/plugins/`):
- 16 `sage-*/` plugin folders, each with `plugin.yaml` + `__init__.py` calling `ctx.register_command()`
- Discovery path: `get_hermes_home() / "plugins"` per `hermes_cli/plugins.py:1240`
- Enable with `hermes plugins enable <name>`

## How It Works on Hermes

Hermes is an opinionated Python agent runtime with a strict plugin discovery
contract. Sage integrates via three surfaces:

### 1. Slash commands (in-session, user-facing)

Hermes plugins can register slash commands via `ctx.register_command(name, handler, description)`.
The 16 sage-* plugins each register one command, returning the corresponding
workflow markdown to be loaded as the next user message context.

### 2. Skills (auto-loaded by Hermes)

Hermes scans `~/.hermes/skills/<name>/SKILL.md` files at startup. Each skill is a
SKILL.md with frontmatter + body. The hermes generator emits sage workflow
files to this exact path — no `.claude/commands/` directory needed.

### 3. Shell hooks (event-driven, observer or in-session-injector)

Hermes invokes shell hooks configured in `~/.hermes/config.yaml` under `hooks:`.
Three hooks fire:
- `on_session_start` → `sage-session-init.sh` reads `.sage/` artifacts and emits
  a `## Sage Context (auto-injected)` block (observer-style, no return value)
- `post_tool_call` (matcher `write_file|patch`) → `sage-mark-edit.sh` records
  the touched path to `agent-hooks/hooks.log` (observer)
- `pre_llm_call` → `sage-inject.sh` detects `/build /fix /architect /design
  /analyze /learn /map /qa /reflect /research /review /continue /build-x
  /autoresearch /status /sage` triggers and returns `{"context":"[sage hint:
  workflow=X active_cycle=Y]"}` on stdout (injects context into next LLM turn)

### 4. Quality gates

The 4 gate scripts (verify, hallucination-check, spec-check, visual-gate) +
gate-modes.yaml are deployed to `agent-hooks/`. The user's profile config can
register them as additional hooks, OR the saga harness invokes them at the
appropriate phase boundaries.

## Why a separate platform adapter?

The 5 platforms upstream ships (claude-code, antigravity, codex, opencode,
gemini-cli) all assume a per-platform dir like `.claude/commands/` for slash
commands. Hermes doesn't have that — its slash-command surface is the
**plugin system**, and its skill-discovery surface is `~/.hermes/skills/`.
The hermes adapter adapts sage's bash-based generator output to those paths.

## Compatibility caveats

- **Slash-command names** — Sage's workflows are documented as `/<name>`
  (e.g. `/build`, `/fix`). The plugin's `register_command("build", ...)` registers
  the bare name; the `/` is added by Hermes at the prompt.
- **Plugin source-of-truth** — the upstream sage repo does not ship the 16
  sage-* plugin folders. They live in `runtime/platforms/hermes/setup/sage-plugins/`
  (added by this PR) and get copied to `~/.hermes/plugins/` at install time.
- **Bin/sage patch** — this PR also adds 5 single-line additions to upstream's
  `bin/sage` to register `hermes` in the platform whitelist (line 220 var decl,
  line 226 auto-detect, line 266 PLATFORMS+=, line 276 case dispatch, line 286
  error message). All additive, no breaking change to the other 5 platforms.
- **AGENTS.md** — Hermes reads `AGENTS.md` for the constitution file, NOT
  `CLAUDE.md` (which is claude-code's filename). The hermes generator emits AGENTS.md.

## Cross-platform consistency

The hermes adapter follows the same 7-file shape as the claude-code adapter
(directory, hooks/sage-session-init.sh, platform.yaml, README.md,
setup/generate-{hermes,plugin}.sh, .claude-plugin/{marketplace.json,plugin.json})
so `bin/sage`'s case-branch and run_generators loop treat both platforms uniformly.
The `generate-plugin.sh` is byte-identical to claude-code's because the
`.claude-plugin/{marketplace.json,plugin.json}` format is platform-agnostic per
upstream convention.

## Reference docs

- Hermes plugin authoring: https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin
- Hermes shell hooks: https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks
- Hermes plugin discovery: `G:/hermes/hermes-agent/hermes_cli/plugins.py` lines 1230-1245
- Shell-hook payload shape: `G:/hermes/hermes-agent/agent/shell_hooks.py:_serialize_payload`
- Hermes home resolution: `G:/hermes/hermes-agent/hermes_constants.py:get_hermes_home`
