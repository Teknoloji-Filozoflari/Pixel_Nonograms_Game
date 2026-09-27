"""Convert a local raster image to an editable Nonogram solution."""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from pixel_nonograms.core import EditorDraft

SUPPORTED_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})
GRID_SIZES = (10, 15, 20, 25, 30)
MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_SOURCE_PIXELS = 20_000_000


@dataclass(frozen=True, slots=True)
class ImageImportOptions:
    size: int = 20
    mode: str = "mono"
    threshold: int = 180
    colors: int = 4

    def __post_init__(self) -> None:
        if type(self.size) is not int or self.size not in GRID_SIZES:
            raise ValueError("Izgara boyutu 10, 15, 20, 25 veya 30 olmalı")
        if type(self.mode) is not str or self.mode not in {"mono", "color"}:
            raise ValueError("Görsel modu geçersiz")
        if type(self.threshold) is not int or not 1 <= self.threshold <= 254:
            raise ValueError("Eşik 1–254 arasında olmalı")
        if type(self.colors) is not int or not 2 <= self.colors <= 8:
            raise ValueError("Renk sayısı 2–8 arasında olmalı")


def _read_image(path: Path, size: int) -> Image.Image:
    if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError("Görsel bulunamadı veya 20 MB sınırını aşıyor")
    try:
        with Image.open(path) as source:
            if source.format not in SUPPORTED_FORMATS:
                raise ValueError("Yalnızca PNG, JPEG ve WEBP desteklenir")
            if source.width * source.height > MAX_SOURCE_PIXELS:
                raise ValueError("Görsel 20 milyon piksel sınırını aşıyor")
            oriented = ImageOps.exif_transpose(source)
            rgba = oriented.convert("RGBA")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as exc:
        raise ValueError("Görsel okunamadı") from exc
    flattened = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    flattened.alpha_composite(rgba)
    resized = ImageOps.contain(flattened.convert("RGB"), (size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size, size), "white")
    canvas.paste(resized, ((size - resized.width) // 2, (size - resized.height) // 2))
    return canvas


def import_image(
    path: str | Path, options: ImageImportOptions = ImageImportOptions()
) -> EditorDraft:
    """Resize, flatten transparency, threshold or quantize, then generate clues."""
    if not isinstance(path, (str, Path)):
        raise TypeError("Görsel yolu metin veya Path olmalı")
    if type(options) is not ImageImportOptions:
        raise TypeError("ImageImportOptions gerekli")
    image = _read_image(Path(path), options.size)
    luminance = np.asarray(image.convert("L"), dtype=np.uint8)
    foreground = luminance < options.threshold
    if not foreground.any():
        raise ValueError("Görselde eşik altında dolu hücre bulunamadı")
    if options.mode == "mono":
        grid = foreground.astype(np.uint8)
        palette = ("#3087B9",)
    else:
        quantized = image.quantize(colors=options.colors, method=Image.Quantize.MEDIANCUT)
        indexed = np.asarray(quantized, dtype=np.uint8)
        rgb_palette = quantized.getpalette()
        grid = np.zeros((options.size, options.size), dtype=np.uint8)
        colors: list[str] = []
        color_ids: dict[str, int] = {}
        for index in sorted(set(indexed[foreground].tolist())):
            base = int(index) * 3
            color = "#{:02X}{:02X}{:02X}".format(*rgb_palette[base : base + 3])
            if color not in color_ids:
                color_ids[color] = len(colors) + 1
                colors.append(color)
            grid[foreground & (indexed == index)] = color_ids[color]
        palette = tuple(colors)
    solution = tuple(tuple(int(value) for value in row) for row in grid)
    return EditorDraft.from_solution(solution, palette)
