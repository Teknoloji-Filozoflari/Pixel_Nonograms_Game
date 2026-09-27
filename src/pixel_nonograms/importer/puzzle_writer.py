"""Write canonical .nono v1 archives with atomic replacement."""

import hashlib
import json
import os
import tempfile
import zipfile
from datetime import timezone
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from pixel_nonograms.core import Puzzle

from .nono_format import (
    ENTRY_LIMITS,
    MAX_ARCHIVE_BYTES,
    MAX_TOTAL_UNCOMPRESSED,
    PuzzleFormatError,
    validate_preview,
)
from .puzzle_reader import _metadata


def _preview(puzzle: Puzzle) -> bytes:
    image = Image.new("RGB", (puzzle.width, puzzle.height), "#FFFFFF")
    pixels = image.load()
    for y, row in enumerate(puzzle.solution):
        for x, color_id in enumerate(row):
            if color_id:
                color = puzzle.palette[color_id - 1]
                pixels[x, y] = tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))
    enlarged = image.resize((puzzle.width * 4, puzzle.height * 4), Image.Resampling.NEAREST)
    output = BytesIO()
    enlarged.save(output, format="WEBP", lossless=True)
    return output.getvalue()


def _zip_entry(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)


def write_puzzle(
    puzzle: Puzzle,
    path: str | Path,
    *,
    preview_webp: bytes | None = None,
    overwrite: bool = False,
) -> None:
    """Write puzzle contents only; progress remains in the SQLite database."""
    if type(puzzle) is not Puzzle:
        raise TypeError("Puzzle gerekli")
    path = Path(path)
    if path.suffix.lower() != ".nono":
        raise PuzzleFormatError("Bulmaca dosyası .nono uzantılı olmalı")
    if type(overwrite) is not bool:
        raise TypeError("overwrite bool olmalı")
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    preview = _preview(puzzle) if preview_webp is None else preview_webp
    validate_preview(preview)
    solution_io = BytesIO()
    np.save(solution_io, np.asarray(puzzle.solution, dtype=np.uint8), allow_pickle=False)
    solution_bytes = solution_io.getvalue()
    metadata = {
        "format_version": 1,
        "id": puzzle.id,
        "title": puzzle.title,
        "author": puzzle.author,
        "description": puzzle.description,
        "width": puzzle.width,
        "height": puzzle.height,
        "difficulty": puzzle.difficulty.value,
        "tags": list(puzzle.tags),
        "created_at": puzzle.created_at.astimezone(timezone.utc).isoformat(),
        "revision": puzzle.metadata.revision,
        "source": puzzle.metadata.source,
        "license": puzzle.metadata.license,
        "solution_sha256": hashlib.sha256(solution_bytes).hexdigest(),
    }
    if puzzle.reward_item_id is not None:
        metadata["reward_item_id"] = puzzle.reward_item_id.value
    metadata_bytes = json.dumps(metadata, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    palette_bytes = json.dumps(puzzle.palette, separators=(",", ":")).encode("utf-8")
    entries = (
        ("metadata.json", metadata_bytes),
        ("palette.json", palette_bytes),
        ("solution.npy", solution_bytes),
        ("preview.webp", preview),
    )
    _metadata(metadata_bytes)
    if any(not 0 < len(data) <= ENTRY_LIMITS[name] for name, data in entries):
        raise PuzzleFormatError("Bulmaca girdisi boyut sınırını aşıyor")
    if sum(len(data) for _, data in entries) > MAX_TOTAL_UNCOMPRESSED:
        raise PuzzleFormatError("Arşiv açılmış boyut sınırını aşıyor")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(temp_name, "w", allowZip64=False) as archive:
            for name, data in entries:
                _zip_entry(archive, name, data)
        if os.path.getsize(temp_name) > MAX_ARCHIVE_BYTES:
            raise PuzzleFormatError("Arşiv boyut sınırını aşıyor")
        with open(temp_name, "rb") as written:
            os.fsync(written.fileno())
        if overwrite:
            os.replace(temp_name, path)
        else:
            os.link(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
