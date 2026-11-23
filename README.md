# bild

One command with verbs for image tasks. `bild --help` lists the verbs, `bild <verb> --help`
the options.

Loose image scripts are being consolidated into these verbs one at a time; see
[docs/PLAN.md](docs/PLAN.md) for the migration plan, the verb registry and the
mapping from old script names.

| Verb | Does |
|---|---|
| `blur` | Detects faces (InsightFace buffalo_l) and blurs them with soft, feathered ellipses. Extra regions with `--add`, faces to leave with `--keep`, review image with `--preview`. |
| `contact` | Contact sheet: thumbnails with index and file name. |
| `level` | Straightens from measured lines (`--line`, averaged) or `--angle`, crops around `--corners`/`--crop`, warns about fill from outside the photo. |
| `strip` | Removes metadata (keeps orientation and ICC), sets photographer; with `-o` copies first and can rename via a tab-separated map. |
| `flytta` | Moves images. `--spegla` puts developed images in the same relative folders as their raw sources (default `~/Pictures/nerladdat` → target directory); `--datum` groups files into `YYMMDD/` folders. With no mode, the files in the target directory decide. Always preview with `-n` first. |
| `namna` | Renames files from EXIF `CreateDate` to `YYMMDD_HHMMSS`, with `-N` suffixes for same-second frames; XMP sidecars follow. Requires `exiftool`. |
| `farg` | Recolours PNG icons with the mean or a chosen RGB, keeping transparency and dark outlines. Output goes to `./recolored`; `--overwrite` (`-o`) writes in place instead. |
| `mindre` | Downscaled JPG/PNG copies in `./mindre`. Thin entry point for `gor_mindre`, which must be on `PATH`; it owns the metadata-preserving pipeline. |
| `tider` | Shifts EXIF dates and the `HHMMSS` part of file names by an offset (`-t -01:01:00 -f '250419*'`). Prints the plan first; `-n` previews only. Requires `exiftool`. |
| `upscale` | AI upscaling via `gor_upscale.py` in the `realesrgan` conda env (subprocess). Override with `BILD_UPSCALE_PYTHON` / `BILD_UPSCALE_SCRIPT`. |

## Anonymising photos for publication

```sh
bild blur photo.jpg -o out/ --preview review/      # 1. look at review/*_preview.jpg
# 2. red ellipses are blurred (score or 'manual'), green are kept.
#    Add what the detector missed (profiles, mirrors, people at the edge),
#    keep the people who may be shown. Boxes are fractions x0,y0,x1,y1.
bild blur photo.jpg -o out/ --preview review/ \
    --add 0.355,0.44,0.405,0.51 --keep 0.27,0.18,0.33,0.31
# 3. strip metadata and drop personal names from file names
printf 'photo__blur.jpg\t09_lecture_2024.jpg\n' > names.tsv
bild strip out/photo__blur.jpg -o to_paper/ --rename-map names.tsv --artist "Kristian Niemi"
```

Detection runs on a copy at most 2400 px on the long side, `det_size` 1280 and threshold 0.25:
for anonymising a missed face costs more than a blurred patch of wall. Always look at the
preview; backs of heads, strong profiles and reflections are not detected.

## Install

```sh
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -e '.[raw,heic,dev]'
ln -s ~/dev/bild/.venv/bin/bild ~/bin/bild
```

The console script's shebang points at the venv, so `bild` works from anywhere without
activating anything. Python 3.11–3.13 (onnxruntime has no wheels for newer versions yet).
The face model `buffalo_l` is downloaded by InsightFace to `~/.insightface/models/` on first use.

## Tests

```sh
.venv/bin/pytest            # fast tests
.venv/bin/pytest -m slow    # also runs the detection model
.venv/bin/ruff check src tests
```
