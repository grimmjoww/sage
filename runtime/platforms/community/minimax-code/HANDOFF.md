# Handoff — Sage for MiniMax Code

**State as of:** 2026-10-03 (second pass), branch `zcode-platform`, nothing committed
**Read this first, then run Step 1.**

> **Correction to the previous handoff.** It said the adapter was "broken and
> failing open in the live host right now." That was half right, and the half
> that was wrong changes what to do first. The **repo source** was the broken
> one (two `NameError`s, `verify_veto` 1/4). The **installed** copy the live
> host actually runs was the *older* 4-gate adapter, which still passes 4/4 —
> the routing rewrite landed in source and was never reinstalled. So the host
> was *partially* enforcing, not allowing everything. It did have a real
> latent fail-open: `4 × 3.0s = 12s` against a 10s host timeout. Both files are
> now fixed in source; the installed copy is still stale (see G15, UNMET).

---

## TL;DR

Steps 1–3 of the old handoff are done. Four defects were found beyond the ones
it listed, three of them the same fail-open shape it warned about. The veto is
proven at 10/10 and the budget is proven empirically, not by arithmetic.

---

## Where things are

| What | Where |
|---|---|
| Adapter source | `runtime/platforms/community/minimax-code/` |
| Installed plugin (**stale**) | `C:\Users\willi\.minimax\plugins\sage\` |
| Extracted gates (9) | `plugin/scripts/gates/*.py` — generated, do not hand-edit |
| Proof harness | `setup/verify_veto.py`, `setup/verify_hooks.py`, `setup/validate_package.py` |
| Ledger | `runtime/platforms/community/minimax-code/GATES.md` — 21 checked, G15 UNMET, G16 pending |
| Shared file touched | `bin/sage` (2 edits, still uncommitted) |

Run everything from the repo root: `C:\Users\willi\Documents\GitHub\sage`

---

## What is proven now

```
extract_gates.py     9 gates, all patches applied, all compile
verify_veto.py       10/10 cases matched    ← veto blocks AND allows, both directions
verify_hooks.py      4/4 cases matched      ← both lifecycle hooks, both directions
validate_package.py  12/12 checks passed     ← was 9 running; 3 were orphaned
contract.py --check  minimax-code   tier A
hang probe           edit path 8.67s, bash path 3.68s — under the 10s host timeout
```

Every one of those numbers was sensitivity-tested, not just observed green:

| Reverted in a scratch copy | Result |
|---|---|
| config gate `Write` + `Bash` P1 patches | 7/9, both cases flip to **ALLOW** |
| only the `multiedit` token | 9/10, that case flips to **ALLOW** |
| a tenth unrouted gate planted | `validate_package` 11/12, gate-routing FAIL |
| a neutered / no-op adapter | 3/4, exit 1 |

The original four veto cases pass in every one of those runs. **That is the
lesson of this pass: 4/4 was true and still did not mean the veto worked.**

---

## What was fixed

**`pre_tool_gate.py`** — both `NameError`s; tool routing that matches Claude's
matcher table; a real wall-clock budget; a stderr breadcrumb on unexpected
exceptions (fail open, but visibly, so a crash is no longer
`HOOK_PROCESS_EXITED`); stale "three gates" docstring.

**`extract_gates.py`** — the handoff flagged one missed P1 patch. There were
three, all in `config_gate.py`:

1. `if tool == "Write"` — dead, so a `write` that weakened `.sage/config.yaml`
   took the `else` branch, compared `current` to itself, and was **allowed**.
2. `if tool == "Bash"` — dead, so the whole bash-evasion branch never ran.
3. `multiedit` absent from the config and tdd tool tuples, so a config
   weakening under that spelling was **allowed**. Latent while the matcher is
   `edit|write|bash`; a live fail-open the moment the matcher widens.

**`validate_package.py`** — added `check_gate_routing`; fixed `check_docs`
(never tallied a pass, so `--docs-only` printed `0/0 OK`); fixed
`check_install` (returned early on file-set drift, so a stray `__pycache__/*.pyc`
hid the content comparison where a stale adapter actually lives); wired
`docs-ok` and `contract-ok` into the default run.

---

## Step 1 — Decide the two open questions

1. **`degradation_log.py` and `verify_tracker.py` are extracted, installed, and
   executed by nothing.** `post_tool_journal.py` appends its own audit line
   and returns. `check_gate_routing` now names them as `STAGED_GATES` — a
   declared admission, not a silent one, and adding a tenth unrouted gate
   turns the check red. Either wire them into a PostToolUse adapter or drop
   them from `OUTPUT_NAMES`. Not decided here; it changes what the platform ships.
2. **Reinstall is unauthorised.** G15 is UNMET. Reinstalling changes live host
   behaviour: the config, scope, and bookkeeping gates start actually running,
   so things currently allowed will start being blocked.

---

## Known gaps — do not claim these

- **`context-injection-midstream: false`** — scope judge not ported (ships disabled upstream anyway)
- **`command-delivery: false`** — MiniMax Plugin V1 has no commands field
- **21 of 23 skills** not packaged; only `sage` and `sage-gates` ship
- **`subagent-dispatch`** declared `true` from the host's `task` tool, never probed. Needs a Level-2 conformance probe.
- **2 of 9 extracted gates never run** (above).
- **G16 pending** — plugin discovery as a Local Plugin, no scan diagnostics.
- **On timeout we kill the direct child only.** A grandchild it spawned can
  outlive us. That costs an orphan, not a stall; the shipped gates bound their
  own subprocesses.

---

## The `bin/sage` change — shared code, read this before reverting

Two edits, 16 insertions / 5 deletions. It is used by every platform.

1. `--platform <anything>` no longer rejected. Was a hardcoded 7-name allowlist.
2. `run_generators()` no longer defaults to claude-code for an unknown platform.

**Cause:** `--platform minimax-code` printed "Unknown platform", left `PLATFORMS`
empty, fell through to auto-detect, and wrote Claude Code files while reporting
success. `hermes` had the same blind spot.

If a hermes generator fix you commissioned never took effect, this is why.

---

## Port gaps for the skills

`sage-fix` and `sage-review` both call `delegate_task`. MiniMax has no
equivalent tool. MCode's subagents are `verifier` / `explore` / `worker` / `mavis`,
dispatched via `task` — **not available in phone-connected sessions.**

**Map `sage-reviewer` → MCode `verifier`.** A desktop session's `task` tool
works; it found two real defects in this pass's adapter that self-review missed.

---

## Lessons from this port, worth not repeating

1. **A gate must assert the property, not a proxy.** Eight instances now.
2. **`py_compile` does not catch `NameError`.** Re-run the proof after every edit.
3. **A green check that cannot fail is worse than no check** — `--docs-only`
   reporting `0/0 OK` sat in the ledger as evidence for a whole session.
4. **`communicate()` waits for grandchildren, not just children.** Pipes make
   your timeout a suggestion.
5. **Read the upstream table, don't paraphrase it.** The routing comment
   misdescribed what `scope`/`secrets` do on a bash call; only measurement
   settled it.
6. **A misspelled tool name is a silent veto bypass.** Three lived in one file.
7. **Replacing a hardcoded allowlist is the durable fix.** Adding the next
   platform name to a list is the same trap with a longer fuse.
8. **Do not offer a self-review as a substitute for an independent review.**
   Offer a named skip or nothing.
9. **Gate-check runs CHECK through `cmd.exe /d /s /c`.** A command *beginning*
   with a quoted path dies with "The filename, directory name, or volume label
   syntax is incorrect." No spaces in the path, or use a `.cmd` shim.
10. **`.cmd` files need CRLF.** LF-only makes cmd mis-parse every `REM` line.

---

## Quick reference — every proof command

```
cd C:\Users\willi\Documents\GitHub\sage
python3 runtime\platforms\community\minimax-code\setup\extract_gates.py ^
  --claude-code-hooks runtime\platforms\claude-code\hooks ^
  --out runtime\platforms\community\minimax-code\plugin\scripts\gates
python3 runtime\platforms\community\minimax-code\setup\verify_veto.py
python3 runtime\platforms\community\minimax-code\setup\verify_hooks.py
python3 runtime\platforms\community\minimax-code\setup\validate_package.py
python3 runtime\platforms\community\minimax-code\setup\validate_package.py --installed
python3 runtime\tools\contract.py --check
"C:\Program Files\Git\bin\bash.exe" develop/conformance/run-conformance.sh minimax-code --level 1,3
```

Conformance has **not** been re-run since these edits — `run-conformance.sh`
(Step 1 of the old quick reference's tail) still needs a pass before G18 is
re-asserted.
