# Gates: Sage for MiniMax Code (community platform port)

Scope: a working MiniMax Code Sage adapter — the platform contract, the MCode plugin package, the extracted gates, a generator Sage's own `sage init` can find, and runnable proof that the pre-tool veto actually blocks. Owned paths: `runtime/platforms/community/minimax-code/`, the `bin/sage` platform-routing lines, the attestation evidence under `docs/attestations/`, and the installed package `C:/Users/willi/.minimax/plugins/sage/`.

**Why the paths below are unquoted and absolute.** gate-check executes every
CHECK through `cmd.exe /d /s /c`. The `/s` flag strips the first and last quote
of the whole command, so a command that *begins* with a quoted path is
reassembled into a filename that includes quote characters and dies with "The
filename, directory name, or volume label syntax is incorrect". Every path
used here is space-free, so it needs no quotes. The one tool that does live
under a path with a space — Git Bash, at `C:\Program Files\Git\bin\bash.exe` —
is reached through the two `.cmd` shims in `setup/`, which do their own
quoting.

    PY = C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe
    S  = C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup
    R  = C:\Users\willi\Documents\GitHub\sage

## Extraction and veto

- [x] G1: The extractor lifts every PreToolUse gate out of the Claude adapter plus the PostToolUse observers, every patch asserted, every file compiling.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\extract_gates.py --claude-code-hooks C:\Users\willi\Documents\GitHub\sage\runtime\platforms\claude-code\hooks --out C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\plugin\scripts\gates
  EXPECT: 9 gate(s) extracted, all patches applied, all compile.
  EVIDENCE: ok  config_gate.py      compiles | 9 gate(s) extracted, all patches applied, all compile.

- [x] G2: The veto blocks a pre-spec source edit AND allows the same edit once the cycle advances AND honours hard_enforcement AND stays silent in a non-Sage repo — and blocks all three spellings of a config-weakening edit (`write`, `multiedit`, `Bash` redirect) while staying quiet on the bash and write commands it must not touch. A veto only ever observed to allow is indistinguishable from a hook that is not wired up.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\verify_veto.py
  EXPECT: 10/10 cases matched
  EVIDENCE: 10/10 cases matched | pre-tool-veto: PROVEN — a pre-spec edit was blocked, and allowed when it should be.
  NOTE: the six cases past the original four each name the gate expected to do the blocking (`expect_reason`), so a case cannot pass because the wrong gate denied. Sensitivity measured, not assumed: reverting the config gate's `Write`/`Bash` P1 patches in a scratch copy drops it to 7/9 with both cases flipping to ALLOW; reverting only the `multiedit` token drops it to 9/10 the same way. The original four still pass in every one of those runs, which is why four cases were not sufficient evidence.

## Contract

- [x] G3: `platform.yaml` declares all eight capabilities with no key missing, names a maintainer, and uses schema v2.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py --contract-only
  EXPECT: contract-ok
  EVIDENCE: contract-ok | OK — 1/1

- [x] G4: The three documents `platform.contract.md` requires of every adapter are present: `platform.yaml`, `README.md`, `INSTALL.md`.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py --docs-only
  EXPECT: docs-ok
  EVIDENCE: PASS docs-ok — 3 required adapter doc(s) present | 12/12 checks passed
  NOTE: this gate previously read `OK — 0/0`. `check_docs` recorded a result only on failure, so a passing docs check was never tallied and `--docs-only` reported zero of zero. The old evidence line was the bug, quoted as proof. Fixed to record both paths; the same check is now also part of the default run.

## Plugin package validity

- [x] G5: Every JSON file in the package parses strictly — no BOM, no duplicate key, no non-object root.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS json-parse
  EVIDENCE: PASS no-secrets — no credential-shaped literal in the package | 12/12 checks passed

- [x] G6: The manifest carries every required Local Plugin V1 field, `apps` is empty, and at least one capability is effective.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS manifest-fields
  EVIDENCE: PASS no-secrets — no credential-shaped literal in the package | 12/12 checks passed

- [x] G7: Every manifest-referenced file exists inside the package, uses forward slashes, and escapes no path.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS manifest-refs
  EVIDENCE: PASS no-secrets — no credential-shaped literal in the package | 12/12 checks passed

- [x] G8: Both icons exist and their bytes are a real PNG, not a renamed text file.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS icons
  EVIDENCE: PASS no-secrets — no credential-shaped literal in the package | 12/12 checks passed

- [x] G9: `hooks.json` uses only supported events, only synchronous `command` handlers, no unsupported fields, and every command uses `${PLUGIN_ROOT}`.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS hook-contract
  EVIDENCE: PASS no-secrets — no credential-shaped literal in the package | 12/12 checks passed

- [x] G10: The exact interpreter named in every `commandWindows` actually resolves on this machine.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS interpreter
  EVIDENCE: PASS no-secrets — no credential-shaped literal in the package | 12/12 checks passed

- [x] G11: Every Python script in the package compiles.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS compiles
  EVIDENCE: PASS no-secrets — no credential-shaped literal in the package | 12/12 checks passed

- [x] G12: Every skill's frontmatter `name` equals its directory name and its description is non-empty.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS skill-frontmatter
  EVIDENCE: PASS no-secrets — no credential-shaped literal in the package | 12/12 checks passed

- [x] G13: No credential-shaped literal appears anywhere in the package.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS no-secrets
  EVIDENCE: PASS no-secrets — no credential-shaped literal in the package | 12/12 checks passed

## Lifecycle hooks, observed

- [x] G14: `SessionStart` injects cycle context on a Sage project and says nothing on a non-Sage project; `PostToolUse` journals on a Sage project and writes nothing on a non-Sage one.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\verify_hooks.py
  EXPECT: 4/4 cases matched
  EVIDENCE: no files created | 4/4 cases matched

## Installed

- [ ] G15: The package is installed at `C:/Users/willi/.minimax/plugins/sage/` and is byte-identical to the source tree.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py --installed
  EXPECT: PASS install-match
  EVIDENCE: FAIL install-match — content differs: ['scripts\\gates\\config_gate.py', 'scripts\\pre_tool_gate.py'] | 12/13 checks passed
  UNMET: the installed copy is the pre-fix adapter. It still enforces 4 gates and passes verify_veto 4/4 on its own, but it predates the routing rewrite and both config-gate P1 patches, and it carries a `4 x 3.0s = 12s` worst case against a 10s host timeout. Reinstall is pending user authorisation — it changes live host behaviour, not just the repo.

- [x] G20: Every extracted gate is reachable from some adapter. The extractor emits nine and the adapters route seven; nothing compared the two, so a gate could be generated, compiled, installed, and never execute. `check_gate_routing` reads the routing tables out of the adapters themselves, and any unrouted gate must be declared in `STAGED_GATES` or the check goes red. Verified sensitive: planting a tenth unrouted gate in a scratch copy turns it FAIL at 11/12.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py
  EXPECT: PASS gate-routing
  EVIDENCE: PASS gate-routing — 7/9 gate(s) routed by an adapter; staged-not-routed (declared): ['degradation_log.py', 'verify_tracker.py'] | 12/12 checks passed

- [x] G21: The `install-match` check cannot be masked by build artefacts. It used to compare raw file sets and return early on a mismatch, so a stray `scripts/__pycache__/*.pyc` — which appears as soon as any harness byte-compiles a script — hid the content comparison where a stale adapter actually lives. It now ignores `__pycache__`/`.pyc` and reports set and content drift together.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\validate_package.py --installed
  EXPECT: install-match names content drift, not only file-set drift
  EVIDENCE: FAIL install-match — content differs: ['scripts\\gates\\config_gate.py', 'scripts\\pre_tool_gate.py']

- [x] G22: The adapter's wall time stays under the host's 10s PreToolUse timeout even when a gate spawns a grandchild that holds the inherited stdout/stderr. Found by independent review, not by inspection: with `capture_output=True`, `subprocess.run` kills the direct child on timeout and then blocks in `communicate()` until every writer holding the pipe closes it — 25.0s on the edit path, which is past the host limit, so the budget's loud fail-open became the silent `HOOK_PROCESS_EXITED` one. Gate output now goes to temp files, which nothing waits on.
  CHECK: python C:\Users\willi\AppData\Local\Temp\sage-hang-probe\hang_probe.py
  EXPECT: edit path under 10s with all six gates hanging and holding a grandchild
  EVIDENCE: PASS edit path, ALL SIX gates hanging + grandchild — 8.67s rc=0 under-10s=yes | PASS bash path, BOTH gates hanging + grandchild — 3.68s rc=0
  NOTE: the probe lives outside the repo (`$env:TEMP\sage-hang-probe`) because it has to overwrite gates with deliberately broken ones. Promote it into `setup/` if this port gets a permanent home.

- [ ] G16: MiniMax Code discovers the plugin as a Local Plugin with no scan diagnostics.
  EVIDENCE: pending

## Sage's own gates, not mine

The instruction was to use the repo's tests rather than a hand-rolled validator. These are the three that decide whether the port is real, and all three live in the Sage repo itself.

- [x] G17: `contract.py --check` parses every contract, derives minimax-code's tier, and finds no legacy mismatch.
  CHECK: C:\Users\willi\AppData\Local\Programs\Python\Python313\python.exe C:\Users\willi\Documents\GitHub\sage\runtime\tools\contract.py --check
  EXPECT: minimax-code   tier A
  EVIDENCE: opencode       tier A  (community) | zcode          tier A  (community)

- [x] G18: Sage's own conformance suite passes for this platform at Levels 1 and 3 — zero failures. The shim derives its marker from the suite's exit code, not from grepping its prose, because parsing coloured output for a word is how a gate passes for the wrong reason.
  CHECK: C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\run-conformance.cmd
  EXPECT: CONFORMANCE_PASS
  EVIDENCE: pass 8 · fail 0 · skip 1 | CONFORMANCE_PASS

- [x] G19: `bin/sage` still parses after the two platform-routing fixes. A syntax error there breaks every platform's init, not just this one.
  CHECK: C:\Users\willi\Documents\GitHub\sage\runtime\platforms\community\minimax-code\setup\check-bash-syntax.cmd
  EXPECT: BASH_SYNTAX_OK
  EVIDENCE: BASH_SYNTAX_OK

<!--
Rules (full spec in references/gates.md):
- One box per outcome. Boxes flip when CHECK output matches EXPECT.
- A checked box with EVIDENCE still reading "pending" counts as UNMET.
- Evidence is the deciding lines only, never a full log.
- If a gate becomes impossible, do not delete it. Add a line:
    ABANDON: G<n> <reason>
  and report it. Visible surrender is honest; silent scope-narrowing is not.
-->
