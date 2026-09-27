"""Shared limits and validation for the .nono ZIP container."""

import json
from io import BytesIO

from PIL import Image, UnidentifiedImageError

FORMAT_VERSION = 1
MAX_ARCHIVE_BYTES = 2_500_000
MAX_TOTAL_UNCOMPRESSED = 1_500_000
MAX_ENTRIES = 4
MAX_METADATA_BYTES = 32_768
MAX_PALETTE_BYTES = 8_192
MAX_SOLUTION_BYTES = 65_536
MAX_PREVIEW_BYTES = 1_000_000
MAX_PREVIEW_SIDE = 512
MAX_COMPRESSION_RATIO = 500
ENTRY_LIMITS = {
    "metadata.json": MAX_METADATA_BYTES,
    "palette.json": MAX_PALETTE_BYTES,
    "solution.npy": MAX_SOLUTION_BYTES,
    "preview.webp": MAX_PREVIEW_BYTES,
}
REQUIRED_ENTRIES = frozenset(ENTRY_LIMITS)


class PuzzleFormatError(ValueError):
    """A .nono archive is unsafe or does not satisfy format version 1."""


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise PuzzleFormatError(f"Yinelenen JSON alanı: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise PuzzleFormatError(f"Geçersiz JSON sabiti: {value}")


def decode_json(data: bytes, name: str) -> object:
    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PuzzleFormatError(f"{name} geçerli UTF-8 JSON değil") from exc


def validate_preview(data: bytes) -> None:
    if type(data) is not bytes or not 0 < len(data) <= MAX_PREVIEW_BYTES:
        raise PuzzleFormatError("Önizleme boyutu geçersiz")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != "WEBP":
                raise PuzzleFormatError("Önizleme WebP olmalı")
            if (
                not 1 <= image.width <= MAX_PREVIEW_SIDE
                or not 1 <= image.height <= MAX_PREVIEW_SIDE
                or getattr(image, "n_frames", 1) != 1
            ):
                raise PuzzleFormatError("Önizleme boyutu veya kare sayısı geçersiz")
            image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        if isinstance(exc, PuzzleFormatError):
            raise
        raise PuzzleFormatError("Önizleme geçerli WebP değil") from exc
