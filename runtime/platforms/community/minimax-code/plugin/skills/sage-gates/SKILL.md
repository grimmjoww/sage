---
name: sage-gates
description: Sage's enforcement doctrine for MiniMax Code — what each gate blocks, the exact reason it prints, and the legitimate ways to clear it. Load when a Sage gate denies a tool call, or before deciding whether to bypass one.
---

# Sage gates

Gates are **binary** and **adversarial by design**. A gate that is hard to
fail is not a gate; it is decoration. Sage's own evaluation found that rules
delivered as prose produced a measured behavioural delta of **zero**, which
is the entire reason this platform was ported to.

## The rules the gates make mechanical

1. **Spec before implementation.** You cannot know what "done" means until
   you wrote it down.
2. **A failing test first.** A fix without a test that failed first is a
   guess with good posture.
3. **No secrets in the repository.** Not in code, not in config, not in a
   commit message.
4. **Verify before claiming done.** Confidence in a reasoning step is not
   verification of the artifact.
5. **Scope is granted, not assumed.** Doing more than asked is still wrong.

## Reading a denial

Every denial names its cycle, the rule, and the fix. Read all three.

### "cycle ... is pre-spec"

You are editing source while a Sage cycle has not been specified yet.

```
Write .sage/work/<cycle>/spec.md, get it approved, then implement.
```

Setting `tier: tier1` in the manifest is legitimate only when the change
really is trivial — a typo, a version bump, a one-line fix. Using it to skip
a spec on anything you find inconvenient converts the gate into a suggestion.

### "no covering test"

The TDD gate found a source edit with no test exercising it. Write the test
first, watch it fail, then make it pass. If the file genuinely has nothing
to test (a constant, a generated artifact), that is worth saying out loud
rather than quietly working around.

### "credential-shaped literal"

The secrets gate matched something that looks like a live key. Use an
environment variable read at runtime — never inline the value, and never
print it while debugging. If it is a false positive, confirm the shape is a
placeholder before proceeding.

### "cannot mark cycle complete"

Rule 5. `gate_state: gates-passed` asserts the quality chain actually ran.
Run the gates, paste the real output, then advance the state. Setting the
field first and backfilling later is the specific behaviour this exists to
prevent.

## If you think a gate is wrong

Say so, in one line, with the reason — then follow it anyway. A wrong gate is
a bug worth reporting; working around it silently is how a framework stops
being one.

The one thing you may not do is disable enforcement to make your own turn
easier.
