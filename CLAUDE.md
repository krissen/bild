# bild

Image tools behind one command with verbs (`src/bild/cli.py`). README has usage.

## Environment

- Venv in `.venv` (Python 3.12 from Homebrew). Always `.venv/bin/python`, `.venv/bin/pytest`.
- `~/bin/bild` is a symlink to `.venv/bin/bild`.

## Adding a verb

1. A module in `src/bild/` with the logic, no argparse in it.
2. A `cmd_<verb>` function and a subparser in `cli.py`; import the module inside `cmd_<verb>`
   so `bild --help` stays fast (insightface is slow to import).
3. Tests in `tests/`; anything that runs a model is marked `@pytest.mark.slow`.
4. A row in the README verb table.

## Consolidation

`docs/PLAN.md` is the authoritative plan for migrating the loose image scripts
into `bild`. Read it before adding a verb that replaces an existing tool: it
holds the verb registry, the `flytta` detection contract, the dependency
decision, the phase breakdown and the shim policy.

Locked decisions (do not re-litigate without updating PLAN.md):

- Verbs: `flytta` with `--datum` / `--spegla` modes, and `namna` for EXIF-date
  renames. `spegla` is a mode, not a verb.
- No runtime imports from `~/dev/ansikten` or other repositories. Copy small
  helpers into `bild` instead; ansikten is left untouched.
- Old executables stay as deprecated shims until migration is complete.

Not covered by the migration: name-based "blur everyone except X" from
`~/.local/share/faceid/encodings.pkl`.

## Conventions

- Commits: Conventional Commits with scope, English, imperative, no AI references.
- No imports from `~/dev/ansikten`; copy small helpers if needed.
