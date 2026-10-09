# Sage for MiniMax Code

MiniMax Code exposes the capability the whole Tier A tier is defined by: a
hook that can **reject a tool call before it runs**. Sage's docs are blunt
about why that is the one worth fighting for — *"if you are choosing which
capability to fight for, fight for the veto. Everything else is a
convenience. That one is the product."*

```
Tier A = pre-tool-veto ∧ post-tool-events ∧ subagent-dispatch
```

`runtime/tools/contract.py --check` derives **tier A** for this platform.
It joins claude-code, hermes, opencode and zcode at that tier; the platforms
that are not there are the ones where a rule is only prose. Sage's v1.2.1 eval
measured exactly that situation and found a **behavioural delta of zero**.

### Conformance

```
$ develop/conformance/run-conformance.sh minimax-code --level 1,3
  pass 8 · fail 0 · skip 1
```

The one skip is `subagent-dispatch`, which Level 1 cannot observe from
generated output and which needs a Level-2 live probe. It is declared `true`
on the strength of the host's `task` tool, not a probe — stated plainly rather
than dressed up as verified.

## What is actually enforced here

| Capability | Value | Evidence |
|---|---|---|
| `pre-tool-veto` | **true** | `setup/verify_veto.py` — 4/4, both directions |
| `post-tool-events` | true | `setup/verify_hooks.py` — audit record written |
| `subagent-dispatch` | true | host `task` tool; needs a Level-2 probe |
| `context-injection` | true | `setup/verify_hooks.py` — cycle injected |
| `session-events` | true | `SessionStart` fires |
| `native-skill-discovery` | true | host plugin API (R112) |
| `command-delivery` | **false** | MiniMax Plugin V1 has no command field |
| `context-injection-midstream` | **false** | scope judge not ported |

Nothing here is `attested`. Every `true` above has a check that can fail.

## How the port was done

The four `PreToolUse` gates are not rewritten. They are **extracted** from
the Claude Code adapter's bash wrappers — which turned out to be 91%/79%/
78%/87% Python, with bash doing nothing but plumbing — and patched by a
build script that asserts every patch applied:

| Patch | Claude | MiniMax | Failure if missed |
|---|---|---|---|
| P1 tool names | `Edit` `Write` `Bash` | `edit` `write` `bash` | gate allows everything |
| P2 path field | `file_path` | `path` | gate allows everything |
| P3 project root | `CLAUDE_PROJECT_DIR` | `MINIMAX_PROJECT_DIR` | gate reads the wrong tree |
| P4 verdict | `exit 2` + stderr | one JSON object on stdout | denial never reaches the host |

The first three are silent failures by construction: a gate that matches
nothing matches every edit. That is the failure mode this framework exists to
eliminate, so `setup/extract_gates.py` refuses to emit a gate whose patch
anchor has moved.

`SessionStart` was the exception — `sage-session-init.sh` is 170 lines of
pure bash, so there was nothing to extract and it was rewritten. Its
collision lock keys on the host's `session_id` rather than `$PPID`, because in
MiniMax the hook's parent is the app process shared by every session; `$PPID`
would make every concurrent session collide with itself.

## What is NOT ported

Honest scope, so nobody assumes coverage that is not there:

- **scope gate** — the largest gate upstream (632 lines). Needs its own port.
- **bookkeeping gate, config gate** — not ported.
- **scope journal / scope judge** — ships disabled upstream anyway.
- **degradation log, manifest sync, verify tracker** — not ported.
- **Level-2 conformance probes** — require a live headless MCode driver, which
  does not exist yet. `subagent-dispatch` is declared `true` on the strength
  of the primitive, not a probe.
- **21 of 23 Skills** — the plugin ships `sage` and `sage-gates`. The rest
  still live only in the Claude adapter.

## Layout

```
minimax-code/
├── platform.yaml            the contract (schema v2, tier derived)
├── GATES.md                 the acceptance ledger for this port
├── plugin/                  the Local Plugin package
│   ├── .minimax-plugin/plugin.json
│   ├── hooks/hooks.json
│   ├── scripts/
│   │   ├── pre_tool_gate.py     ← the veto
│   │   ├── session_start.py     ← context injection
│   │   ├── post_tool_journal.py ← audit trail
│   │   └── gates/*.py           ← GENERATED, do not edit
│   └── skills/
└── setup/
    ├── extract_gates.py     gates out of the Claude adapter, patches asserted
    ├── validate_package.py  structural validation of the package
    ├── verify_veto.py       the proof that matters
    └── verify_hooks.py      lifecycle hook proof
```

## Running the proof

```
python3 setup/verify_veto.py      # does the veto actually block?
python3 setup/verify_hooks.py     # do the lifecycle hooks actually fire?
python3 setup/validate_package.py # is the package structurally valid?
```

If `verify_veto.py` does not print `4/4 cases matched`, do not claim Tier A.
