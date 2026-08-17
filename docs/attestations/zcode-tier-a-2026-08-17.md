# ZCode attestation — 2026-08-17

Platform: ZCode 0.16.3 (`zcode_protocol` entrypoint), Windows 11, Git Bash,
sage plugin 1.3.21 installed from marketplace. All findings below were
produced on this machine on 2026-08-17; rerunnable probes are listed at the
end. Investigated by `willi` with the ZCode agent itself as the probe harness.

## Host semantics (source-verified)

Read from the shipped host bundle `resources/glm/zcode.cjs` (`core.hooks`):

- Hook events supported (exactly seven): `SessionStart`, `UserPromptSubmit`,
  `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PostToolUseFailure`,
  `Stop`.
- Command hooks run `mode: "shell"` with `${CLAUDE_PLUGIN_ROOT}` /
  `${CLAUDE_PROJECT_DIR}` template expansion and the payload on stdin.
- Exit-code contract: **0 = pass** (stdout parsed as JSON — non-JSON stdout
  that doesn't start with `{` is silently discarded), **2 = block** (for
  PreToolUse/PermissionRequest: `permissionDecision: "deny"`, stderr text
  becomes the model-visible reason), **anything else = run failed**.
- Midstream channel: output `additionalContext` /
  `hookSpecificOutput.additionalContext` is pushed into the conversation for
  PostToolUse, UserPromptSubmit, SessionStart and Stop.
- Subagents: the Agent/Task tool dispatches fresh-context agents; plugin
  `agents/*.md` files register as dispatchable personas (sage's
  `sage-classifier` was registered and listed in a live session).
- Config-file hooks require `hooks.enabled: true`; plugin hooks enable the
  runner automatically. Hooks load at session start — no mid-session reload
  (a config hook added mid-session did not fire).

## Live evidence (log: `~/.zcode/cli/log/zcode-2026-08-17.jsonl`)

- `plugin.sage@sage.SessionStart.1.0` executed at session start.
- 128 PreToolUse + 65 PostToolUse sage hook executions recorded with matcher,
  source and duration — the events fire on every matching tool call.

## The Windows path bug (root cause of every hook failure that day)

Every sage plugin hook failed (~75 ms, `hook.run.failed`) on Windows while
succeeding by hand. Reproduction:

```
$ bash C:\Users\w\...\sage-session-init.sh      # unquoted backslash path
bash: C:Userswilli...: No such file or directory   # rc 127
$ bash 'C:\Users\w\...\sage-session-init.sh'    # quoted
(rc 0)
$ bash "C:/Users/w/.../sage-session-init.sh"    # forward slashes
(rc 0)
```

`sage`'s `hooks/hooks.json` invokes its scripts unquoted
(`bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/x.sh`). On Windows the expansion
contains backslashes, which bash treats as escapes in an unquoted word — the
path is mangled and the script never runs; the host marks the run failed and
the gate fail-opens. The same failure affects every Claude-format plugin that
ships unquoted `${CLAUDE_PLUGIN_ROOT}` commands (observed on the superpowers
plugin too). Fix applied locally: double-quote all 11 commands in the cached
plugin's `hooks.json` (backwards-compatible on macOS/Linux), and the zcode
generator emits only double-quoted `${CLAUDE_PROJECT_DIR}` paths.

Second platform quirk: non-JSON hook stdout is discarded (claude-code feeds
plain SessionStart stdout to the model). The port's generated
`.sage/hooks/zcode-session-start.sh` adapter captures
`sage-session-init.sh` output and re-emits it as
`{"additionalContext": ...}`.

Dependency note: the gate scripts call `python3`. On Windows the Microsoft
Store `python3.exe` stub shadows real Python unless a real `python3.exe`
exists earlier on PATH (the standard per-user Python install provides only
`python.exe`). A `python3.exe` copy beside `python.exe` fixes resolution for
hook contexts, which inherit the app's PATH and load no shell profiles.

## Derived tier

A = pre-tool-veto ∧ post-tool-events ∧ subagent-dispatch — all attested
above. Hooks-firing-inside-subagents (ADR-10's escape-hatch argument) is NOT
yet probed on ZCode; re-probe before relying on independent-review semantics.

## Live probe results (2026-08-17, post-fix)

After three environment fixes — quoted hook paths, `python3.exe` beside
`python.exe`, and `C:\Program Files\Git\bin` on the user PATH (bash.exe is
NOT on the default Windows PATH; Git's installer only adds `Git\cmd`) —
a restart made everything green:

- **pre-tool-veto, proven live 18:22:51Z**: a PreToolUse(Read) hook
  (diag canary in the workspace config) exited 2; the host BLOCKED the
  Read and returned the hook's stderr text to the model verbatim —
  "VETO-CANARY: deliberately blocking this Read to prove pre-tool-veto".
- **Hook execution context captured**: the spawn runs through MSYS bash
  (`/mingw64/bin:/usr/bin` leading PATH); `python3` resolved to the real
  Python 3.13.15; payload JSON arrives on stdin with toolInput, sessionId,
  mode and riskLevel.
- **post-tool-events**: zero `hook.run.failed` records after the restart
  (46 in the preceding hour); the sage plugin's Pre/PostToolUse gates now
  run on every matching tool call without error.
- Prerequisites recorded for reproducibility: Git Bash installed; its
  `bin` dir on PATH; a real `python3` resolvable before WindowsApps.

## Rerunnable probes

1. Veto canary (archived): a PreToolUse(Read) hook that dumps its env and
   exits 2. On a fixed install the Read is blocked with the stderr reason;
   `diag/canary.log` records the hook context's PATH and python3
   resolution.
2. Path bug: run the three bash invocations below against any sage hook
   script; only the unquoted backslash form fails.
3. Event firing: trigger any Bash/Edit tool call with the sage plugin
   enabled and grep the day's log for `hook.run.*` records naming
   `plugin.sage@sage`.
