# bild

One command with verbs for image tasks. `bild --help` lists the verbs, `bild <verb> --help`
the options.

| Verb | Does |
|---|---|
| `blur` | Detects faces (InsightFace buffalo_l) and blurs them with soft, feathered ellipses. Extra regions with `--add`, faces to leave with `--keep`, review image with `--preview`. |
| `contact` | Contact sheet: thumbnails with index and file name. |
| `level` | Straightens from measured lines (`--line`, averaged) or `--angle`, crops around `--corners`/`--crop`, warns about fill from outside the photo. |
| `strip` | Removes metadata (keeps orientation and ICC), sets photographer; with `-o` copies first and can rename via a tab-separated map. |

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
