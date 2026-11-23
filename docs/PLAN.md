# Consolidation plan

Status: agreed 2026-11-23; phases 0–5 implemented the same day. Scope: make `bild` the single entry point for image
work, migrating the loose scripts one verb at a time. This document is the
authoritative record of the decisions; update it when a decision changes, and
record the change in the decision log at the bottom.

## Vision

`bild` is one command with verbs. Each verb is one user intent and is
discoverable from `bild --help` and `bild <verb> --help`. Old script names stay
as deprecated shims during the migration, but the documentation points at the
verbs.

## Principles

1. **One verb = one intent**, named after what the user wants, not after the
   mechanism. The help line describes the intent.
2. **One module per verb** (`src/bild/<verb>.py`) with no argparse in it; all CLI
   wiring lives in `cli.py`. Logic modules stay importable and testable on
   their own.
3. **No runtime imports from other repositories** (see Decision 2). Shared
   helpers live in `bild`; a helper is only extracted into its own package when
   there are two real consumers and a stable API.
4. **Mutating verbs are safe by construction**: `-n/--dry-run`, never overwrite,
   sidecars move atomically with the main file, and any failed step rolls the
   whole unit back.
5. **Auto-detect may choose *how*, never *what* silently.** It must print what it
   decided and why, refuse ambiguous input without touching the filesystem, and
   let explicit flags override it completely.
6. **Stepwise migration.** One verb per phase, with tests and a README row. No
   big-bang replacement.

## Verb registry

| Verb | Replaces | Intent | Phase |
|---|---|---|---|
| `blur` | — | blur detected/manual face regions | shipped |
| `contact` | — | contact sheet | shipped |
| `level` | — | straighten and crop | shipped |
| `strip` | — | strip metadata, set photographer | shipped |
| `flytta` | `filer2mappar matcha-kalla`, `gor_bildflytt` | move images: mirror source folders (`--spegla`) or group by date (`--datum`); auto-detect when no mode is given | 1 / 2 |
| `namna` | `rename_nef` | rename files from EXIF `CreateDate` to `YYMMDD_HHMMSS` | 2 |
| `farg` | `gor_snittfarg` | compute average colour | 3 |
| `mindre` | `gor_mindre` | make downscaled copies, preserving EXIF | 3 |
| `tider` | `fixa_fototider`, `fotodatum` | adjust/repair photo timestamps | 3 |
| `upscale` | `gor_upscale` | upscale via an external tool in a subprocess | 4 |

Deliberately out of scope: `rensa_metadata.py` handles documents
(docx/xlsx/pdf/pptx/odf), not images. It stays in `~/Documents/scripts`.

## The `flytta` detection contract

`bild flytta [MÅLMAPP]` inspects the target directory (default `./`) and picks a
mode. Detection **never mutates anything**; it only reports or asks.

| Contents of target root | Interpretation | Action |
|---|---|---|
| `DSC_*.NEF` dominant | raw files not named yet | do nothing; ask *"Menade du `bild namna`?"* |
| `YYMMDD_*.{NEF,xmp}` | grouping by date | run `--datum` |
| `YYMMDD_*.jpg` with matching sources under `nerladdat` | mirroring | run `--spegla` |
| `YYMMDD_*.jpg` without matching sources | mirroring with unresolved files | run `--spegla`, report every unresolved file |
| mixed / unknown / empty | ambiguous | abort, show what was found, suggest `--datum` / `--spegla` |

Three rules:

1. Ambiguity or `DSC_*.NEF` never causes a move — only a question or message.
2. The chosen mode, and the evidence for it, is always printed, e.g. *"Hittade
   49 `YYMMDD_*.jpg` och 47 matchande källor → tolkar som `--spegla`. Ändra med
   `--datum`."*
3. Explicit `--datum` / `--spegla` skip detection entirely and always win.

`--spegla` takes `--kallrot` (default `~/Pictures/nerladdat`); the target root is
the positional argument or `./`. A separate `--spegla-nef` flag is unnecessary:
matching is by timestamp and accepts NEF/JPG/TIFF sources. `--datum` is a mode
selector, so date *filters* are named `--fran`, `--till`, `--fore`, `--efter`
(the old `--datum` alias for an exact date is retired).

## Dependency decision

`core` in the ansikten repo is that application's domain library, not a generic
toolkit. Importing it from `bild` was rejected:

| Module | Size | Reason |
|---|---|---|
| `core/files.py` | 29 lines | trivial, copied |
| `core/exiftool.py` | 36 lines | trivial, copied |
| `core/fs_ops.py` | 947 lines | undo journal, batch rename, import semantics and face-DB path repair. Only `new_batch_id` + `rename_with_sidecars` + journal are used by `filer2mappar`; the journal belongs to ansikten's undo feature. |

Importing `core` would also pull in `ansikten-backend`'s dependency tree
(fastapi, uvicorn, rawpy, pyxdg and a pinned insightface), couple bild's
releases to another repository's API, and force ansikten to keep an internal
module stable as a public surface. None of that buys anything for a small CLI.

Consequence: copy the roughly 120 lines that are actually needed into
`src/bild/moves.py` and `src/bild/exiftool.py`. **Ansikten is left untouched.**
This matches the existing rule in `CLAUDE.md`: "No imports from
`~/dev/ansikten`; copy small helpers if needed."

The conservative "guess nearest source folder" heuristic from `matcha-kalla`
(about 100 lines of timeline/neighbour logic) is **not** ported initially. Exact
timestamp matching plus a clear list of unresolved files is simpler and less
likely to put a photo in the wrong folder. It can be added later as an opt-in
flag if the need appears.

## Phases

| Phase | Content | Acceptance |
|---|---|---|
| 0 | This document; point `CLAUDE.md` and `README.md` at it | Plan lives in the repo; no code changed |
| 1 | `src/bild/moves.py`; `bild flytta --spegla`; tests | `bild flytta -n --spegla` produces the same move plan as `filer2mappar matcha-kalla` (34 safe / 1 unresolved at verification time); `filer2mappar` still works |
| 2 | `bild flytta --datum`; auto-detect; `bild namna` (so the "Menade du namna?" hint resolves) | every row of the detection matrix tested; ambiguous input never mutates |
| 3 | `farg`, `mindre`, `tider` | one verb per commit, each with tests |
| 4 | `upscale` via subprocess with an explicit environment contract | works without making bild's venv heavy |
| 5 | shim cleanup; update `~/Documents/scripts/CLAUDE.md` | no duplicated guidance |

## Shim policy

Keep the old executables, but mark them deprecated in their `--help` with a
pointer to the new verb. Remove them only once every caller has migrated. No
removal in phases 1–4.

| Old name | New |
|---|---|
| `~/bin/filer2mappar` | `bild flytta --spegla` |
| `~/bin/scripts/gor_bildflytt` | `bild flytta --datum` |
| `~/bin/rename_nef` | `bild namna` |

## Decision log

- **2026-11-23 — verb names.** `flytta` (Swedish infinitive) for moving images,
  with `--datum` / `--spegla` modes; `namna` for renaming from EXIF date.
  `spegla` is a mode, not a verb, to avoid giving one verb several unrelated
  meanings. `flytt` was rejected in favour of `flytta` for consistency with
  `namna`.
- **2026-11-23 — no cross-repo imports.** Copy small helpers into `bild`;
  ansikten stays untouched.
- **2026-11-23 — no guessing heuristic in phase 1.** Exact matching only.
- **2026-11-23 — shims stay, marked deprecated.**

## Magick warning in `gor_mindre` (fixed)

`gor_mindre` (in `~/Documents/scripts`) used to print
`magick: ParseError missing > @ warning/xml-tree.c/NewXMLTree/1808.` for every
scaled image. Investigated 2026-11-23: ImageMagick 7.1.2's XML scanner misreads
Lightroom's valid `stEvt:changed="/"` attribute. Output metadata was intact
(XMP byte-identical, EXIF preserved), so the warning was cosmetic. Fixed in the
`scripts` repo with a separate commit (`5e66c1c` on the PR branch): `-quiet` on the `magick`
command. `gor_mindre` stays the engine behind `bild mindre`.

## Follow-ups from the final review (2026-11-23)

Nagelfararna returned `approved with follow-ups`. None of these block merge;
they are tracked here so they are not lost. Full issue files live in the
central coms channel `nagelfar/bild-image-cli-consolidation`.

1. **`farg -o` documentation.** Fixed before merge: `-o` is `--overwrite`
   (in place), not an output-directory switch. README now says so. The flag
   name is still inconsistent with `-o/--output` in the other verbs — consider
   renaming it in a later, separate change.
2. **`tider` midnight wrap.** The filename time wraps at midnight without
   rolling the date, so the name and EXIF date diverge for offsets crossing
   00:00. This is inherited from `fixa_fototider.zsh` and covered by a test;
   confirm whether that is the intended behaviour before changing it.
3. **Bare `bild namna` only matches `*.NEF`.** Other RAW formats (CR3, ARW,
   DNG, …) are renamed when named explicitly but skipped by a bare invocation.
   Consider widening the default glob to all supported RAW extensions.

## Open questions

- Should `filer2mappar.py` eventually be removed from ansikten, or kept as that
  application's own journal-aware tool? Left as-is for now.
- Should the nearest-timestamp guessing heuristic return as an opt-in flag?
- Should short aliases (`flytt` → `flytta`) be added, or would that undermine
  discoverability?
