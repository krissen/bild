"""Contact sheets: a grid of thumbnails with an index and file name under each."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


def make_sheet(files: list[Path], cols: int = 5, size: int = 300, label_len: int = 40) -> Image.Image:
    rows = (len(files) + cols - 1) // cols
    cell_h = size + 20
    sheet = Image.new("RGB", (cols * size, max(1, rows) * cell_h), "white")
    draw = ImageDraw.Draw(sheet)
    for i, f in enumerate(files):
        x, y = (i % cols) * size, (i // cols) * cell_h
        try:
            with Image.open(f) as im:
                im = ImageOps.exif_transpose(im).convert("RGB")
                im.thumbnail((size, size))
                sheet.paste(im, (x, y))
        except OSError as e:
            draw.text((x + 4, y + 4), f"unreadable: {e}", fill="red")
        draw.text((x + 2, y + size + 2), f"{i} {Path(f).name[:label_len]}", fill="black")
    return sheet
