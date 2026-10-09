# Attestation — `native-skill-discovery` on MiniMax Code

**Verified:** 2026-10-03 · **Expires at release:** 1.4 · **Maintainer:** rei-stewart

## Claim

Sage's skills are delivered on demand by the host rather than inlined into
every session's context.

## Why attested (R112)

R112 is explicit that a plugin-API platform registers skills through the host
plugin system and must not be graded against Claude Code's file layout. Level 1
generates a project and counts `SKILL.md` files under `skills-dir`; for a
plugin platform there are none, because the registration is not a file. Level 3
carries the proof instead.

## What the mechanism actually is

The plugin manifest declares each skill explicitly:

```json
"skills": [
  "skills/sage/SKILL.md",
  "skills/sage-gates/SKILL.md"
]
```

MiniMax matches a skill's frontmatter `description` against the incoming
request and loads the body on demand. This is not a Sage-specific feature —
it is the mechanism behind the host's own built-in catalog of several hundred
skills, which is why it is claimed as `true`-shaped rather than `false`.

## Why this matters for context budget

ADR-9 moved roughly 220 lines out of the always-loaded instructions body and
into skills. `platform.yaml` declares `skills-dir: null`, and the generator
therefore **must not** call `emit_system_skills_inline`.

Conformance Level 1 checks this from the other side too: a platform declaring
`native-skill-discovery: false` must either emit the skills or inline them,
because otherwise its users do not have that content at all while their
instructions file still points at it as though they did. That check is what
caught the identical bug on all four earlier community ports. Re-read
`docs/porting-sage.md` §2 before changing this file.

## Known gap

**Two of twenty-three skills are ported** — `sage` and `sage-gates`. The
remaining twenty-one still exist only in the Claude Code adapter. A skill that
is not in the manifest is not delivered to a MiniMax user, and no amount of
prose in a README changes that.

## Re-probe instructions

```
python3 runtime/platforms/community/minimax-code/setup/validate_package.py
```

`PASS skill-frontmatter` confirms every skill the manifest declares has a
directory-matching `name` and a non-empty `description`. The count of
declared skills is the honest measure of coverage — read it off
`.minimax-plugin/plugin.json`, not from this file.
