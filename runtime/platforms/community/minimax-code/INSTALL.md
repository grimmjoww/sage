# Installing Sage for MiniMax Code

Under five minutes, no network, no package manager.

## Requirements

- MiniMax Code Desktop
- **Python 3.9+** on `PATH`. Sage's gates are Python upstream; this port
  keeps them that way rather than transpiling ~1,200 lines to JavaScript and
  hoping the translation is faithful.
- Git in the project you want to guard (only for the collision warning).

## Install

1. **Generate the gates.** They are derived from the Claude Code adapter and
   are not checked in:

   ```
   python3 runtime/platforms/community/minimax-code/setup/extract_gates.py \
     --claude-code-hooks runtime/platforms/claude-code/hooks \
     --out runtime/platforms/community/minimax-code/plugin/scripts/gates
   ```

   Expect `4 gate(s) extracted, all patches applied, all compile.` A patch
   that does not apply aborts here — that is deliberate. See `README.md` for
   the four patches and what each one silently breaks if it is missed.

2. **Validate before installing.** Do not skip this; it is the difference
   between "the plugin is present" and "the plugin enforces":

   ```
   python3 runtime/platforms/community/minimax-code/setup/validate_package.py
   python3 runtime/platforms/community/minimax-code/setup/verify_veto.py
   ```

   Both must be clean. `verify_veto.py` must print `4/4 cases matched`.

3. **Copy the package** into the local plugin directory:

   ```
   xcopy /E /I /Y runtime\platforms\community\minimax-code\plugin ^
     "%USERPROFILE%\.minimax\plugins\sage"
   ```

   On macOS/Linux, copy `plugin/` to `~/.minimax/plugins/sage/`.

4. **Check the interpreter path.** Every hook's `commandWindows` names an
   absolute interpreter. If your Python lives somewhere else, edit
   `hooks/hooks.json` — all three `commandWindows` values — to point at yours.
   `validate_package.py` check `PASS interpreter` proves the path you shipped
   resolves; it cannot prove it resolves on someone else's machine.

5. **Restart MiniMax Code** if the plugin does not appear under Local
   Plugins on its own. The automatic rescan usually catches it first.

## Using it

Sage is inert outside a Sage project. In a repo with `.sage/` and
`hard_enforcement: true` in `.sage/config.yaml`:

- a source edit while a cycle is `pre-spec` is **denied** by the host;
- a source edit with no covering test is flagged;
- a credential-shaped literal written to a file is denied;
- every completed tool call is journalled to `.sage/gates/audit.jsonl`.

Outside those conditions the hooks emit nothing at all, by design.

## Uninstall

Delete `%USERPROFILE%\.minimax\plugins\sage` and restart. Nothing outside that
directory is touched — the gates write only into a project's `.sage/`.

## Upgrading

Re-run step 1, then step 2, then step 3. Never hand-edit anything under
`plugin/scripts/gates/`; those files are generated and carry the upstream
source's SHA-256 in their header. Edit `extract_gates.py` instead, so the
change survives the next extraction.
