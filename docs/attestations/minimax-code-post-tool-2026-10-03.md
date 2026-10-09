# Attestation — `post-tool-events` on MiniMax Code

**Verified:** 2026-10-03 · **Expires at release:** 1.4 · **Maintainer:** rei-stewart

## Claim

Every completed tool call in a Sage project appends one JSONL record to
`.sage/gates/audit.jsonl`, giving the platform the audit trail that separates a
degraded run from a clean one.

## Why attested

Plugin-API surface: the hook lives inside the installed Plugin package, so
conformance Level 1 cannot observe it by inspecting generated project output.

## Transcript

```
$ python3 runtime/platforms/community/minimax-code/setup/verify_hooks.py

── MiniMax Code lifecycle hook probe ──

  PASS  SessionStart injects active cycle on a Sage project
  PASS  SessionStart is silent on a non-Sage project
  PASS  PostToolUse writes one audit record on a Sage project
        1 line(s), tool='write'
  PASS  PostToolUse writes nothing on a non-Sage project
        no files created

  4/4 cases matched
```

## Cases 3 and 4, in detail

Case 3 invokes `post_tool_journal.py` with a realistic `PostToolUse` payload
(`tool_name: write`, `tool_use_id: tu_1`, an input and a response) against a
fixture project containing `.sage/`. It asserts:

- `.sage/gates/audit.jsonl` exists,
- it holds exactly one line,
- the record parses and carries `tool == "write"` and `use_id == "tu_1"`,
- **and stdout is empty** — this is a side-effect-only hook, so the cheapest
  thing the host can process is nothing at all.

Case 4 is the negative control. Without it, a journal that wrote to every
directory on the machine would pass case 3 and quietly leak every tool call
the user ever made into unrelated projects.

## Bounds

The host caps stdout and stderr at 64 KiB per hook and kills commands on
overflow. Each record truncates tool input and response to 2,000 characters
and records the original length, so a large response cannot bloat the journal
without bound or trip the cap.

## Known gap

Sage's fuller PostToolUse set — verify-tracker, degradation-log, manifest-sync
and the scope journal — is **not ported**. The audit trail is the whole of
this capability as shipped. See `README.md` § What is NOT ported.

## Re-probe instructions

```
python3 runtime/platforms/community/minimax-code/setup/verify_hooks.py
```

Must print `4/4 cases matched`.
