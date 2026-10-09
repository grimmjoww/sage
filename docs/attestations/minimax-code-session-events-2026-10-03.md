# Attestation — `session-events` on MiniMax Code

**Verified:** 2026-10-03 · **Expires at release:** 1.4 · **Maintainer:** rei-stewart

## Claim

`SessionStart` fires and delivers the active Sage cycle to the model as
`hookSpecificOutput.additionalContext`, and `SessionEnd` is wired for future
use.

## Why attested

Plugin-API surface — the handler lives in the installed Plugin package. See the
R112 note in `platform.yaml`.

## Transcript

```
$ python3 runtime/platforms/community/minimax-code/setup/verify_hooks.py

  PASS  SessionStart injects active cycle on a Sage project
  PASS  SessionStart is silent on a non-Sage project

  4/4 cases matched
```

## Case 1

A fixture project with `.sage/config.yaml`, `.sage/work/cockpit/spec.md`
carrying `status: in-progress` and `phase: specification`. The handler is
invoked with a realistic `SessionStart` payload (`source: startup`,
`session_id`, `cwd`). The assertions:

- stdout parses as one JSON object,
- `hookSpecificOutput.hookEventName == "SessionStart"` — the host rejects a
  mismatch here, so this is the wire contract and not decoration,
- the injected text names the cycle (`Cockpit slice`) and states that it is
  in progress,
- the process exits 0.

## Case 2 — the negative control

The same handler against a project with no `.sage/` must produce **empty
stdout**, byte for byte. A plugin that greets every repository on the machine
is noise, and it trains the user to ignore the channel that matters.

## Two deliberate differences from the Claude original

`session_start.py` was rewritten rather than extracted, because
`sage-session-init.sh` is 170 lines of pure bash with nothing to lift.

1. **The collision lock keys on `session_id`, not `$PPID`.** In Claude the
   hook's parent process *was* the session. In MiniMax the hook's parent is the
   application process, shared by every open session — so `$PPID` would make
   every concurrent session appear to collide with itself. The host supplies
   `session_id` on stdin and it actually identifies the session. This is a fix.

2. **No `kill -0` liveness probe.** That is a POSIX idiom; on Windows
   `os.kill(pid, 0)` does not mean what the Claude hook assumes. The lock only
   ever produces a *warning* and never blocks, so a 6-hour staleness window is
   sufficient and cannot do damage. A warning that is occasionally stale is
   cheap; a wrong signal is not.

## Re-probe instructions

```
python3 runtime/platforms/community/minimax-code/setup/verify_hooks.py
```

Must print `4/4 cases matched`.
