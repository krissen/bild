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

Planned: Python scripts from `~/Documents/scripts` as verbs (`gor_bildflytt`,
`gor_snittfarg`, `rensa_metadata`; `upscale` calls the conda env `realesrgan` in a
subprocess), old names kept as symlinked shims; bash scripts as thin verbs later;
name-based "blur everyone except X" from `~/.local/share/faceid/encodings.pkl`.

## Conventions

- Commits: Conventional Commits with scope, English, imperative, no AI references.
- No imports from `~/dev/ansikten`; copy small helpers if needed.
