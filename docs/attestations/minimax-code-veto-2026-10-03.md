# Attestation — `pre-tool-veto` on MiniMax Code

**Verified:** 2026-10-03 (second pass, same day) · **Expires at release:** 1.4 · **Maintainer:** rei-stewart

> **Superseded in substance, re-verified in place.** The first version of this
> attestation was written against a four-case proof of a *different* adapter —
> the four-gate one that is still sitting in the installed plugin directory. It
> also predicted, in its own words, the exact defect that then existed. Both
> facts are recorded below rather than quietly edited away.

## Why this is attested rather than true

MiniMax is a plugin-API platform. The `PreToolUse` hook ships inside the
installed Plugin package at `~/.minimax/plugins/sage/hooks/hooks.json`, not as
a file in the user's project, so conformance Level 1 — which generates a
project and inspects what came out — cannot see it. No free check in the
repository can observe this surface. That is the situation R112 exists for.

## Scope of this attestation — read before citing it

**This attests the adapter in the repository source tree, not the copy the
host is running.** As of this pass `validate_package.py --installed` reports:

```
FAIL install-match — content differs: ['scripts\\gates\\config_gate.py', 'scripts\\pre_tool_gate.py']
```

The installed plugin is the pre-fix adapter. It enforces 4 of the 7 routed
gates and its own veto proof still passes, but it predates the tool routing,
the config gate's `Write`/`Bash`/`multiedit` patches, and the wall-clock
budget. **Until the package is reinstalled, conformance's Level 3
`pre-tool-veto: attested` describes source, not the live hook.** Reinstall is
pending user authorisation because it changes live host behaviour.

## What was actually run

The real adapter (`plugin/scripts/pre_tool_gate.py`) invoking the real
extracted gates (`plugin/scripts/gates/*.py`, byte-identical to the Claude
Code adapter's embedded Python apart from asserted build-time patches), against
throwaway fixtures, with MiniMax-shaped hook JSON on stdin:

```
$ python3 runtime/platforms/community/minimax-code/setup/verify_veto.py

  PASS  pre-spec edit of source file is DENIED
  PASS  same edit ALLOWED once gate_state is building
  PASS  hard_enforcement: false is ALLOWED
  PASS  non-Sage project is ALLOWED
  PASS  write that weakens .sage/config.yaml is DENIED
  PASS  bash redirect that disables hard_enforcement is DENIED
  PASS  bash that only reads .sage/config.yaml is ALLOWED
  PASS  bash that writes an ordinary file is ALLOWED
  PASS  write to an ordinary source file is ALLOWED
  PASS  multiedit that weakens .sage/config.yaml is DENIED

  10/10 cases matched

  pre-tool-veto: PROVEN — a pre-spec edit was blocked, and allowed when it should be.
```

## What each case proves

1. **DENY** — a `write` to `src/app.py` while `.sage/work/fixture-cycle/manifest.md`
   carries `gate_state: pre-spec` produced a MiniMax
   `hookSpecificOutput.permissionDecision: "deny"`. This is the wall: the edit
   did not happen.
2. **ALLOW** — the identical edit, with `gate_state: building`, was permitted.
   Without this the veto would be a denial machine, and case 1 alone could not
   distinguish a working gate from one that denies everything.
3. **ALLOW** — `hard_enforcement: false` in `.sage/config.yaml` is honoured.
4. **ALLOW** — a project with no `.sage/` produces no stdout and no side
   effects at all.
5. **DENY** — a `write` to `.sage/config.yaml` that turns `hard_enforcement`
   off. This is the branch the first attestation could not have caught: the
   gate's `if tool == "Write"` never matched MiniMax's lowercase `write`, so
   the gate compared the config against itself and allowed the weakening.
6. **DENY** — the same weakening expressed as a shell redirect
   (`echo "hard_enforcement: false" > .sage/config.yaml`). Its branch,
   `if tool == "Bash"`, was likewise dead: `"bash"` never equals `"Bash"`.
7. **ALLOW** — `cat .sage/config.yaml`. The negative control for case 6: a
   branch that was switched back on must stay quiet on reads.
8. **ALLOW** — `echo hi > notes.txt`, and a `write` to an ordinary source file.
9. **DENY** — the same config weakening spelled `multiedit`, which the adapter
   routes but the gate's tool filter did not accept.

Cases 5–9 each name the gate expected to do the blocking (`expect_reason`), so
a case cannot pass because some *other* gate denied the call by accident.

## The checker can fail, and this is how we know

An attestation that only ever observed a pass proves nothing. Each group was
reverted in a throwaway copy and the suite re-run:

| Reverted in a scratch copy | Result |
|---|---|
| config gate `Write` + `Bash` patches | **7/9**, cases 5 and 6 flip to ALLOW |
| only the `multiedit` token | **9/10**, case 9 flips to ALLOW |
| a neutered adapter | **3/4**, exit 1 |
| a no-op adapter | **3/4**, exit 1 |

The original four cases pass in every one of those runs. The first version of
this attestation cited `4/4` as proof, and `4/4` was **true** while two thirds
of the gate surface was failing open. The count was never the evidence; the
negative controls are.

## The budget is measured, not arithmetic

`hooks/hooks.json` allows this hook 10s for the whole `PreToolUse` event, and
the host kills the process at that mark and skips the hook — so exceeding the
budget does not degrade the veto, it silently disables it. The six edit-path
gate ceilings sum to 14.0s, so the adapter keeps a wall-clock deadline
(`EVENT_BUDGET = 8.5s`) and reports on stderr any gate it declines to start.

Independent review found this was not sufficient: with `capture_output=True`,
`subprocess.run` kills the direct child on timeout and then blocks in
`communicate()` until every writer holding the pipe closes it, so a gate's
grandchild held the hook open for **25.0s**. Gate output now goes to temp
files. Measured worst case, all six gates hanging *and* each holding a
grandchild: **8.67s** on the edit path, 3.68s on the bash path.

## The patches between Claude and MiniMax

Every divergence below is a silent total failure if missed — a gate that
matches nothing matches every call:

| | Claude | MiniMax |
|---|---|---|
| tool names | `Edit` `Write` `MultiEdit` `Bash` | `edit` `write` `multiedit` `bash` |
| path field | `file_path` | `path` |
| project root env | `CLAUDE_PROJECT_DIR` | `MINIMAX_PROJECT_DIR` |
| verdict transport | exit 2 / `BLOCK` on stdout | one `permissionDecision` JSON object |

`setup/extract_gates.py` asserts each patch applied and aborts the build if an
anchor has moved, so a future upstream edit cannot quietly produce a gate that
allows everything.

**Three tool-name patches were in fact missed on first pass**, all in
`config_gate.py`: `if tool == "Write"`, `if tool == "Bash"`, and the absence
of lowercase `multiedit` from the config and tdd filters. The table above is
the corrected one. This is the concrete form of the rule the rest of this port
exists to enforce — a gate must assert the property, not a proxy for it.

## Re-probe instructions

```
python3 runtime/platforms/community/minimax-code/setup/verify_veto.py
python3 runtime/platforms/community/minimax-code/setup/validate_package.py
python3 runtime/platforms/community/minimax-code/setup/validate_package.py --installed
```

Must print `10/10 cases matched` and `12/12 checks passed`. If it does not,
this capability is not `attested` — it is false. The `--installed` run is part
of the probe on purpose: until it passes, the live host is not running the
adapter this document describes.
