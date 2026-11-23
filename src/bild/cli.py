"""bild: one command with verbs for image tasks."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

from . import __version__

DEFAULT_SOURCE_ROOT = Path("~/Pictures/nerladdat").expanduser()

EPILOG = """\
Run 'bild <verb> --help' for the options of each verb.

Typical anonymising workflow:
  bild blur photo.jpg -o out/ --preview review/   # check review/*.jpg
  bild blur photo.jpg -o out/ --add 0.35,0.43,0.41,0.52 --keep 0.27,0.18,0.33,0.31
  bild strip out/*.jpg --artist "Kristian Niemi"

Move developed images to the folders their raw files live in:
  bild flytta -n --spegla ~/Pictures/framkallat   # preview first
  bild flytta --spegla ~/Pictures/framkallat
"""


def _out_path(src: Path, outdir: Path | None, suffix: str) -> Path:
    directory = outdir if outdir else src.parent
    return directory / f"{src.stem}{suffix}.jpg"


def _rgb(value: str) -> tuple[int, int, int]:
    parts = value.split(",")
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("RGB must be R,G,B with integers 0-255")
    try:
        colour = tuple(int(part.strip()) for part in parts)
    except ValueError as error:
        raise argparse.ArgumentTypeError("RGB must be R,G,B with integers 0-255") from error
    if not all(0 <= channel <= 255 for channel in colour):
        raise argparse.ArgumentTypeError("RGB channels must be 0-255")
    return colour


def cmd_upscale(args: argparse.Namespace) -> int:
    from .upscale import run_upscale

    passthrough: list[str] = []
    if args.model:
        passthrough += ["-m", args.model]
    if args.output:
        passthrough += ["-o", str(args.output)]
    if args.overwrite:
        passthrough.append("-O")
    if args.tile:
        passthrough += ["--tile", str(args.tile)]
    if args.tile_pad != 10:
        passthrough += ["--tile_pad", str(args.tile_pad)]
    if args.pre_pad:
        passthrough += ["--pre_pad", str(args.pre_pad)]
    if args.half:
        passthrough.append("--half")
    if args.outscale is not None:
        passthrough += ["--outscale", str(args.outscale)]
    if args.test:
        passthrough.append("--test")
    if args.models:
        passthrough.append("--models")
    if args.input:
        passthrough.append(str(args.input))
    return run_upscale(passthrough)


def cmd_tider(args: argparse.Namespace) -> int:
    from .tider import run_tider

    return run_tider(args.pattern, args.offset, dry_run=args.dry_run)


def cmd_mindre(args: argparse.Namespace) -> int:
    from .mindre import run_mindre

    size = args.size
    files = list(args.files)
    if files and files[0].isdigit() and size == 800:
        size = int(files.pop(0))
    return run_mindre(
        size=size,
        quality=args.quality,
        outdir=args.outdir,
        files=files,
        force=args.force,
    )


def cmd_farg(args: argparse.Namespace) -> int:
    from .farg import run_farg

    return run_farg(
        args.files,
        colour=args.colour,
        overwrite=args.overwrite,
        find_mean=args.find_mean,
        preserve_dark=args.preserve_dark,
        threshold=args.threshold,
    )


def cmd_blur(args: argparse.Namespace) -> int:
    from .blur import blur, drop_kept, frac_to_box, parse_frac_box, preview
    from .faces import detect
    from .io import load_image, resized, save_jpg

    adds = [parse_frac_box(t) for t in args.add]
    keeps = [parse_frac_box(t) for t in args.keep]
    if len(args.files) > 1 and (adds or keeps):
        print("note: --add/--keep apply to every file given", file=sys.stderr)
    for src in args.files:
        img = load_image(src)
        h, w = img.shape[:2]
        detected = [] if args.no_detect else detect(
            img, max_side=args.max_side, det_size=args.det_size, threshold=args.threshold)
        boxes = drop_kept(detected, keeps, w, h)
        kept = [b for b in detected if b not in boxes]
        boxes += [frac_to_box(a, w, h) for a in adds]
        dst = _out_path(src, args.output, args.suffix)
        save_jpg(dst, blur(img, boxes, args.style), args.quality)
        if args.preview:
            pv = resized(preview(img, boxes, kept), args.preview_width)
            save_jpg(args.preview / f"{src.stem}__preview.jpg", pv, 85)
        scores = " ".join("manual" if b.score < 0 else f"{b.score:.2f}" for b in boxes)
        print(f"{src.name}: {len(boxes)} blurred, {len(kept)} kept -> {dst}  [{scores}]")
    return 0


def cmd_flytta(args: argparse.Namespace) -> int:
    from .flytta import (
        compute_datum_moves,
        compute_spegla_moves,
        detect_mode,
        execute_datum_moves,
        execute_spegla_moves,
    )
    from .moves import parse_date_arg

    mode = "spegla" if args.spegla else "datum" if args.datum else None
    target_root = args.target.expanduser().resolve()
    if not target_root.is_dir():
        raise SystemExit(f"target root does not exist or is not a directory: {target_root}")
    source_root = args.kallrot.expanduser().resolve()

    if mode is None:
        mode, explanation = detect_mode(target_root, source_root)
        print(f"Auto: {explanation}")
        if mode is None:
            raise SystemExit("ambiguous input: choose --datum or --spegla")
        if mode == "namna":
            # Never act on a question: the user asked to be asked, not to have
            # their raw files renamed behind their back.
            raise SystemExit(explanation)

    if mode == "spegla":
        if not source_root.is_dir():
            raise SystemExit(f"source root does not exist or is not a directory: {source_root}")
        if (
            source_root == target_root
            or source_root in target_root.parents
            or target_root in source_root.parents
        ):
            raise SystemExit("source and target roots must not overlap")
        safe, unresolved = compute_spegla_moves(source_root, target_root)
        print(f"Safe: {len(safe)}, unresolved: {len(unresolved)}.")
        if unresolved:
            print("Unresolved files:", file=sys.stderr)
            for path in unresolved:
                print(f"  {path.name}", file=sys.stderr)
        moved, failed = execute_spegla_moves(
            safe, dry_run=args.dry_run, verbose=args.verbose or args.dry_run
        )
        if not args.dry_run:
            print(f"Moved {moved} images.")
        return 1 if unresolved or failed else 0

    try:
        before = parse_date_arg(args.before) if args.before else None
        after = parse_date_arg(args.after) if args.after else None
        from_date = parse_date_arg(args.from_date) if args.from_date else None
        to_date = parse_date_arg(args.to_date) if args.to_date else None
    except ValueError as error:
        raise SystemExit(str(error)) from error
    groups = compute_datum_moves(
        target_root, before=before, after=after, from_date=from_date, to_date=to_date
    )
    total = sum(len(pairs) for pairs in groups.values())
    print(f"Safe: {total}, date groups: {len(groups)}.")
    moved, failed = execute_datum_moves(
        groups, target_root, dry_run=args.dry_run, verbose=args.verbose or args.dry_run
    )
    if not args.dry_run:
        print(f"Moved {moved} images.")
    return 1 if failed else 0


def cmd_namna(args: argparse.Namespace) -> int:
    from glob import glob

    from .namna import run_namna

    files: list[Path] = []
    for pattern in args.files:
        candidate = Path(pattern)
        matches = (
            [candidate]
            if candidate.is_file()
            else [Path(match) for match in sorted(glob(pattern)) if Path(match).is_file()]
        )
        files.extend(matches)
    return run_namna(
        sorted(set(files)), dry_run=args.dry_run, include_named=args.include_named
    )


def cmd_contact(args: argparse.Namespace) -> int:
    from .contact import make_sheet

    sheet = make_sheet(args.files, cols=args.cols, size=args.size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output)
    print(f"{len(args.files)} images -> {args.output}")
    return 0


def cmd_level(args: argparse.Namespace) -> int:
    from .io import load_image, save_jpg
    from .level import angle_from_lines, level, parse_points

    if args.angle is None and not args.line:
        raise SystemExit("give --angle or at least one --line")
    if args.angle is not None:
        angle = args.angle
    else:
        lines = [tuple(parse_points(t, 2)) for t in args.line]
        angle = angle_from_lines(lines)
    corners = None
    if args.corners:
        corners = parse_points(args.corners, 4)
    elif args.crop:
        (x0, y0), (x1, y1) = parse_points(args.crop, 2)
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    img = load_image(args.file)
    out, black = level(img, angle, corners, args.margin)
    dst = args.output or _out_path(args.file, None, "__level")
    save_jpg(dst, out, args.quality)
    print(f"rotated {angle:.2f} deg -> {dst} ({out.shape[1]}x{out.shape[0]})")
    if black > 50:
        print(f"warning: {black} fill pixels from outside the photo; reduce --margin or the crop", file=sys.stderr)
    return 0


def cmd_strip(args: argparse.Namespace) -> int:
    from .strip import read_rename_map, strip

    files = list(args.files)
    if args.output:
        args.output.mkdir(parents=True, exist_ok=True)
        mapping = read_rename_map(args.rename_map) if args.rename_map else {}
        copied = []
        for f in files:
            dst = args.output / mapping.get(f.name, f.name)
            shutil.copy2(f, dst)
            copied.append(dst)
        missing = set(mapping) - {f.name for f in files}
        if missing:
            print(f"warning: rename map names not among the files: {sorted(missing)}",
                  file=sys.stderr)
        files = copied
    elif args.rename_map:
        raise SystemExit("--rename-map needs -o/--output (originals are never renamed)")
    copyright_ = args.copyright or (f"Foto: {args.artist}" if args.artist else None)
    strip(files, args.artist, copyright_)
    print(f"stripped metadata from {len(files)} files")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bild", description="Image tools behind one command.", epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"bild {__version__}")
    sub = p.add_subparsers(dest="verb", metavar="<verb>", required=True)

    b = sub.add_parser("blur", help="blur faces (detect + manual boxes), with review preview",
                       description="Detect faces and blur them with soft ellipses. Boxes for "
                       "--add/--keep are fractions of width and height: x0,y0,x1,y1.")
    b.add_argument("files", nargs="+", type=Path)
    b.add_argument("-o", "--output", type=Path, help="output directory (default: next to input)")
    b.add_argument("--suffix", default="__blur", help="added to the file name (default: __blur)")
    b.add_argument("--add", action="append", default=[], metavar="BOX",
                   help="extra region to blur, e.g. a missed profile (repeatable)")
    b.add_argument("--keep", action="append", default=[], metavar="BOX",
                   help="leave detected faces whose centre is in this region (repeatable)")
    b.add_argument("--style", choices=["soft", "pixel"], default="soft")
    b.add_argument("--preview", type=Path, metavar="DIR",
                   help="write a preview with ellipses (red blurred, green kept) for review")
    b.add_argument("--preview-width", type=int, default=1600)
    b.add_argument("--threshold", type=float, default=0.25, help="detection score (default 0.25)")
    b.add_argument("--det-size", type=int, default=1280)
    b.add_argument("--max-side", type=int, default=2400, help="detect on a copy this large")
    b.add_argument("--no-detect", action="store_true", help="only blur the --add boxes")
    b.add_argument("--quality", type=int, default=92)
    b.set_defaults(func=cmd_blur)

    c = sub.add_parser("contact", help="contact sheet of thumbnails with index and name")
    c.add_argument("files", nargs="+", type=Path)
    c.add_argument("-o", "--output", type=Path, default=Path("contact.png"))
    c.add_argument("--cols", type=int, default=5)
    c.add_argument("--size", type=int, default=300)
    c.set_defaults(func=cmd_contact)

    lv = sub.add_parser("level", help="straighten from measured lines and crop around a region",
                        description="Coordinates are pixels in the (EXIF-upright) input image. "
                        "--line x0,y0,x1,y1 marks an edge that should be horizontal; several "
                        "lines are averaged. --corners takes four points (x,y;x,y;x,y;x,y) of "
                        "the object to keep, --crop a box x0,y0,x1,y1.")
    lv.add_argument("file", type=Path)
    lv.add_argument("-o", "--output", type=Path)
    lv.add_argument("--line", action="append", default=[])
    lv.add_argument("--angle", type=float, help="rotation in degrees (OpenCV sign: + is ccw)")
    g = lv.add_mutually_exclusive_group()
    g.add_argument("--corners")
    g.add_argument("--crop")
    lv.add_argument("--margin", type=int, default=70)
    lv.add_argument("--quality", type=int, default=93)
    lv.set_defaults(func=cmd_level)

    s = sub.add_parser("strip", help="strip metadata (keeps orientation, ICC); set photographer",
                       description="Without -o the files are changed in place. With -o they "
                       "are copied first, optionally renamed via a tab-separated map "
                       "(old<TAB>new), e.g. to drop personal names from file names.")
    s.add_argument("files", nargs="+", type=Path)
    s.add_argument("-o", "--output", type=Path, help="copy to this directory first")
    s.add_argument("--rename-map", type=Path)
    s.add_argument("--artist")
    s.add_argument("--copyright", help="default: 'Foto: <artist>'")
    s.set_defaults(func=cmd_strip)

    f = sub.add_parser(
        "flytta",
        help="move images into date folders or mirror the source folder structure",
        description="Move images. --datum groups files into YYMMDD folders; --spegla "
        "mirrors the relative folders of the source images (default source root: "
        "~/Pictures/nerladdat). With no mode, the files in MÅLMAPP decide: DSC_ raws "
        "ask for 'bild namna', dated raws mean --datum, dated jpegs mean --spegla. "
        "See docs/PLAN.md.",
    )
    f.add_argument("target", nargs="?", type=Path, default=Path("."), metavar="MÅLMAPP")
    f.add_argument("-n", "--dry-run", action="store_true", help="show what would be done")
    f.add_argument("-v", "--verbose", action="store_true", help="show each move")
    mode = f.add_mutually_exclusive_group()
    mode.add_argument("--datum", action="store_true", help="group files into YYMMDD folders")
    mode.add_argument("--spegla", action="store_true", help="mirror the source folder structure")
    f.add_argument(
        "--kallrot",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help=f"source tree for --spegla (default: {DEFAULT_SOURCE_ROOT})",
    )
    dates = f.add_argument_group("date filters for --datum")
    dates.add_argument("--fran", "--from", dest="from_date", metavar="DATUM")
    dates.add_argument("--till", "--to", dest="to_date", metavar="DATUM")
    dates.add_argument("--fore", "--before", dest="before", metavar="DATUM")
    dates.add_argument("--efter", "--after", dest="after", metavar="DATUM")
    f.set_defaults(func=cmd_flytta)

    n = sub.add_parser(
        "namna",
        help="rename files from EXIF CreateDate to YYMMDD_HHMMSS",
        description="Rename images from their EXIF CreateDate. Files already carrying "
        "their timestamp keep their name and reserve the slot, so a same-second "
        "frame gets a -N suffix. XMP sidecars follow. Requires exiftool.",
    )
    n.add_argument("files", nargs="*", default=["*.NEF"], metavar="FIL")
    n.add_argument("-n", "--dry-run", action="store_true", help="show what would be done")
    n.add_argument(
        "--include-named", action="store_true", help="also rename files that already carry a date"
    )
    n.set_defaults(func=cmd_namna)

    fg = sub.add_parser(
        "farg",
        help="recolour PNG icons with a mean or chosen RGB, keeping transparency",
        description="Recolour PNG icons. By default the light fill pixels take the mean "
        "colour of all visible pixels; dark outlines are preserved. Output goes "
        "to ./recolored unless --overwrite is given.",
    )
    fg.add_argument("files", nargs="+", type=Path)
    fg.add_argument("-c", "--colour", type=_rgb, metavar="R,G,B")
    fg.add_argument("-o", "--overwrite", action="store_true", help="write over the originals")
    fg.add_argument("-f", "--find-mean", action="store_true", help="only report the colour")
    dark = fg.add_mutually_exclusive_group()
    dark.add_argument(
        "--preserve-dark", dest="preserve_dark", action="store_true", default=True,
        help="keep pixels darker than the threshold (default)",
    )
    dark.add_argument(
        "--no-preserve-dark", dest="preserve_dark", action="store_false",
        help="recolour every visible pixel",
    )
    fg.add_argument("--threshold", type=int, default=170, help="luminance threshold 0-255")
    fg.set_defaults(func=cmd_farg)

    mi = sub.add_parser(
        "mindre",
        help="make downscaled copies with gor_mindre (needs it on PATH)",
        description="Downscaled JPG/PNG copies in a subdirectory. Needs the gor_mindre "
        "shell tool on PATH; it owns the ImageMagick/jpegtran/oxipng pipeline so "
        "EXIF and XMP survive. A bare leading number is the size in pixels.",
    )
    mi.add_argument("files", nargs="*", help="files, or SIZE followed by files")
    mi.add_argument("-s", "--size", type=int, default=800, help="longest side in pixels")
    mi.add_argument("-q", "--quality", type=int, default=90, help="JPEG quality 1-100")
    mi.add_argument("-o", "--outdir", type=Path, default=Path("mindre"))
    mi.add_argument("-f", "--force", action="store_true", help="overwrite existing copies")
    mi.set_defaults(func=cmd_mindre)

    ti = sub.add_parser(
        "tider",
        help="shift EXIF dates and the time in photo file names",
        description="Shift all EXIF dates and the HHMMSS part of matching file names "
        "by an offset such as -01:01:00. Prints the plan before writing; use -n "
        "to preview only.",
    )
    ti.add_argument("-t", "--offset", required=True, metavar="±HH:MM:SS")
    ti.add_argument("-f", "--pattern", required=True, metavar="GLOB", help="file pattern")
    ti.add_argument("-n", "--dry-run", action="store_true", help="show the plan only")
    ti.set_defaults(func=cmd_tider)

    up = sub.add_parser(
        "upscale",
        help="AI upscale via gor_upscale in the realesrgan conda env",
        description="AI upscaling with Real-ESRGAN. The heavy dependencies live in a "
        "separate conda environment, invoked as a subprocess. Model defaults to "
        "gor_upscale's own (anime6b). Use --models to list available models.",
    )
    up.add_argument("input", nargs="?", help="input image (PNG)")
    up.add_argument("-m", "--model", help="model name")
    up.add_argument("-o", "--output", type=Path, help="output file")
    up.add_argument("-O", "--overwrite", action="store_true")
    up.add_argument("--tile", type=int, default=0)
    up.add_argument("--tile_pad", type=int, default=10)
    up.add_argument("--pre_pad", type=int, default=0)
    up.add_argument("--half", action="store_true")
    up.add_argument("--outscale", type=float)
    up.add_argument("--test", action="store_true", help="test all models on the input")
    up.add_argument("--models", action="store_true", help="list models and exit")
    up.set_defaults(func=cmd_upscale)
    return p


def _normalise_tider_offsets(argv: list[str]) -> list[str]:
    """Make `-t -01:01:00` work: argparse reads a leading '-' as an option."""
    normalised: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if (
            token in ("-t", "--offset")
            and index + 1 < len(argv)
            and re.fullmatch(r"-\d{2}:\d{2}:\d{2}", argv[index + 1])
        ):
            normalised.append(f"{token}={argv[index + 1]}")
            index += 2
            continue
        normalised.append(token)
        index += 1
    return normalised


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["tider"]:
        argv = _normalise_tider_offsets(argv)
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
