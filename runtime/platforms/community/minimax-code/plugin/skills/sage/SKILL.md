---
name: sage
description: Sage's entry point for MiniMax Code. Load this before writing code in a repo that has a .sage/ directory, or when the user asks to fix, build, architect, review, or debug something non-trivial. Routes to the right Sage mode and explains which gates are currently enforcing.
---

# Sage

Sage is a framework for **orchestrated, resilient, governed engineering**.
Three modes, differing in depth:

| Mode | Use for | Shape |
|---|---|---|
| **FIX** | a known bug | reproduce → failing test → fix → verify. Minutes. |
| **BUILD** | a new feature | spec → plan → task-by-task → gates. Hours. |
| **ARCHITECT** | a system change | full planning team, stories, sprint. Days. |

Pick the lightest mode that fits. BUILD is not "FIX but slower" — it adds a
spec gate, which is the single most-cited reason projects shipped wrong.

## The part that matters

Sage's claims are **enforcement** claims, not documentation claims. On this
platform those claims are backed by a `PreToolUse` hook that can *reject a
tool call before it runs*. That is the whole difference between Sage and a
style guide, and it is why the gates are worth respecting rather than working
around.

Four gates are live. They only fire in a repo with a `.sage/` directory and
`hard_enforcement: true` in `.sage/config.yaml`:

- **spec gate** — no source edits while a cycle is `pre-spec`
- **TDD gate** — a source edit with no covering test is flagged
- **secrets gate** — no writing credential-shaped literals into files
- **verify gate** — shell commands that assert success are checked

## When a gate blocks you

Do not look for a way around it. That is the failure mode the gate exists to
prevent. Read the reason it printed — it names the cycle, the rule, and the
fix — then do that.

Legitimate exits, in order:

1. Write the missing `spec.md` and get it approved. This is the intended path.
2. If the work is genuinely trivial, mark the cycle `tier: tier1`.
3. If the project has decided not to use hard enforcement, set
   `hard_enforcement: false` in `.sage/config.yaml`. That is a project
   decision, not yours to make silently.

## Degraded operation

Not every capability is ported yet. The honest state of this port is in
`runtime/platforms/community/minimax-code/STATUS.md` upstream. If something
Sage would normally enforce does not fire here, say so rather than assuming
it is covered — an unenforced rule that reads as enforced is worse than no
rule at all.
