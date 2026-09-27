"""Read bounded .nono v1 archives without extracting paths to disk."""

import hashlib
import re
import stat
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np

from pixel_nonograms.core import Difficulty, Puzzle, PuzzleMetadata
from pixel_nonograms.core.validation import MAX_DIMENSION, validate_palette

from .nono_format import (
    ENTRY_LIMITS,
    FORMAT_VERSION,
    MAX_ARCHIVE_BYTES,
    MAX_COMPRESSION_RATIO,
    MAX_ENTRIES,
    MAX_TOTAL_UNCOMPRESSED,
    REQUIRED_ENTRIES,
    PuzzleFormatError,
    decode_json,
    validate_preview,
)

_REQUIRED_METADATA = frozenset(
    ("format_version", "id", "title", "author", "width", "height", "difficulty", "tags")
)
_OPTIONAL_METADATA = frozenset(
    (
        "description",
        "created_at",
        "revision",
        "source",
        "license",
        "solution_sha256",
        "reward_item_id",
    )
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _read_entry(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    limit = ENTRY_LIMITS[info.filename]
    if info.file_size > limit or info.compress_size > MAX_ARCHIVE_BYTES:
        raise PuzzleFormatError(f"{info.filename} boyut sınırını aşıyor")
    if info.file_size and (
        info.compress_size == 0 or info.file_size / info.compress_size > MAX_COMPRESSION_RATIO
    ):
        raise PuzzleFormatError("Arşiv sıkıştırma oranı güvenli sınırı aşıyor")
    with archive.open(info) as entry:
        data = entry.read(limit + 1)
    if len(data) > limit or len(data) != info.file_size:
        raise PuzzleFormatError(f"{info.filename} boyutu tutarsız")
    return data


def _read_archive(path: Path) -> dict[str, bytes]:
    if path.suffix.lower() != ".nono":
        raise PuzzleFormatError("Bulmaca dosyası .nono uzantılı olmalı")
    if path.stat().st_size > MAX_ARCHIVE_BYTES:
        raise PuzzleFormatError("Arşiv boyut sınırını aşıyor")
    try:
        with zipfile.ZipFile(path, "r") as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(infos) != MAX_ENTRIES or len(set(names)) != len(names):
                raise PuzzleFormatError("Arşiv girdi sayısı veya adları geçersiz")
            if not REQUIRED_ENTRIES.issubset(names) or any(
                name not in ENTRY_LIMITS for name in names
            ):
                raise PuzzleFormatError("Arşiv beklenmeyen veya eksik dosya içeriyor")
            if sum(info.file_size for info in infos) > MAX_TOTAL_UNCOMPRESSED:
                raise PuzzleFormatError("Arşiv açılmış boyut sınırını aşıyor")
            for info in infos:
                if (
                    info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED)
                    or info.flag_bits & 1
                    or stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK
                ):
                    raise PuzzleFormatError("Arşiv girdisi desteklenmiyor")
            return {info.filename: _read_entry(archive, info) for info in infos}
    except (zipfile.BadZipFile, zipfile.LargeZipFile, RuntimeError, EOFError) as exc:
        raise PuzzleFormatError("Geçersiz ZIP arşivi") from exc


def _metadata(data: bytes) -> dict[str, object]:
    value = decode_json(data, "metadata.json")
    if type(value) is not dict:
        raise PuzzleFormatError("Metadata nesne olmalı")
    keys = set(value)
    if not _REQUIRED_METADATA.issubset(keys) or keys - _REQUIRED_METADATA - _OPTIONAL_METADATA:
        raise PuzzleFormatError("Metadata alanları eksik veya bilinmiyor")
    if type(value["format_version"]) is not int or value["format_version"] != FORMAT_VERSION:
        raise PuzzleFormatError("Desteklenmeyen dosya biçimi sürümü")
    if any(type(value[name]) is not str for name in ("id", "title", "author", "difficulty")):
        raise PuzzleFormatError("Metadata metin alanları geçersiz")
    if (
        type(value["width"]) is not int
        or type(value["height"]) is not int
        or not (1 <= value["width"] <= MAX_DIMENSION and 1 <= value["height"] <= MAX_DIMENSION)
    ):
        raise PuzzleFormatError("Bulmaca boyutları geçersiz")
    if (
        type(value["tags"]) is not list
        or len(value["tags"]) > 32
        or any(type(tag) is not str or not 1 <= len(tag) <= 64 for tag in value["tags"])
    ):
        raise PuzzleFormatError("Etiketler geçersiz")
    for name, limit in (("id", 128), ("title", 200), ("author", 200), ("description", 4096)):
        field = value.get(name, "")
        if type(field) is not str or len(field) > limit:
            raise PuzzleFormatError(f"Metadata {name} alanı geçersiz")
    for name, limit in (("source", 128), ("license", 128)):
        field = value.get(name)
        if field is not None and (type(field) is not str or len(field) > limit):
            raise PuzzleFormatError(f"Metadata {name} alanı geçersiz")
    if "revision" in value and (type(value["revision"]) is not int or value["revision"] < 1):
        raise PuzzleFormatError("Metadata revision alanı geçersiz")
    digest = value.get("solution_sha256")
    if digest is not None and (type(digest) is not str or _SHA256.fullmatch(digest) is None):
        raise PuzzleFormatError("Çözüm özeti geçersiz")
    if (
        "reward_item_id" in value
        and value["reward_item_id"] is not None
        and type(value["reward_item_id"]) is not str
    ):
        raise PuzzleFormatError("Ödül kimliği geçersiz")
    return value


def _solution(
    data: bytes, width: int, height: int, color_count: int
) -> tuple[tuple[int, ...], ...]:
    stream = BytesIO(data)
    try:
        version = np.lib.format.read_magic(stream)
        if version == (1, 0):
            shape, fortran_order, dtype = np.lib.format.read_array_header_1_0(
                stream, max_header_size=1024
            )
        elif version == (2, 0):
            shape, fortran_order, dtype = np.lib.format.read_array_header_2_0(
                stream, max_header_size=1024
            )
        else:
            raise PuzzleFormatError("NPY sürümü desteklenmiyor")
        if shape != (height, width) or fortran_order or dtype != np.dtype("uint8"):
            raise PuzzleFormatError("Çözüm dizisinin türü veya boyutu geçersiz")
        if len(data) - stream.tell() != width * height:
            raise PuzzleFormatError("Çözüm dizisinin veri uzunluğu geçersiz")
        stream.seek(0)
        array = np.load(stream, allow_pickle=False, max_header_size=1024)
    except (ValueError, TypeError, EOFError, OSError) as exc:
        if isinstance(exc, PuzzleFormatError):
            raise
        raise PuzzleFormatError("Geçersiz NPY çözüm dosyası") from exc
    if array.shape != (height, width) or array.dtype != np.dtype("uint8"):
        raise PuzzleFormatError("Çözüm dizisi geçersiz")
    if int(array.max()) > color_count:
        raise PuzzleFormatError("Çözüm palette olmayan renk içeriyor")
    return tuple(tuple(int(cell) for cell in row) for row in array)


def read_puzzle(path: str | Path) -> Puzzle:
    """Read only puzzle definition data; no save state is accepted or loaded."""
    content = _read_archive(Path(path))
    metadata = _metadata(content["metadata.json"])
    palette_data = decode_json(content["palette.json"], "palette.json")
    if type(palette_data) is not list:
        raise PuzzleFormatError("Palette JSON dizisi olmalı")
    try:
        palette = validate_palette(palette_data)
    except ValueError as exc:
        raise PuzzleFormatError("Palette geçersiz") from exc
    raw_solution = content["solution.npy"]
    digest = metadata.get("solution_sha256")
    if digest is not None and hashlib.sha256(raw_solution).hexdigest() != digest:
        raise PuzzleFormatError("Çözüm özeti eşleşmiyor")
    validate_preview(content["preview.webp"])
    created_at = metadata.get("created_at")
    try:
        created = datetime.fromisoformat(created_at) if created_at is not None else None
        puzzle_metadata = PuzzleMetadata(
            revision=metadata.get("revision", 1),
            source=metadata.get("source", "local"),
            license=metadata.get("license"),
        )
        fields = {"created_at": created} if created is not None else {}
        return Puzzle(
            id=metadata["id"],
            title=metadata["title"],
            author=metadata["author"],
            description=metadata.get("description", ""),
            width=metadata["width"],
            height=metadata["height"],
            difficulty=Difficulty(metadata["difficulty"]),
            tags=tuple(metadata["tags"]),
            palette=palette,
            solution=_solution(raw_solution, metadata["width"], metadata["height"], len(palette)),
            metadata=puzzle_metadata,
            reward_item_id=metadata.get("reward_item_id"),
            **fields,
        )
    except (ValueError, TypeError, OverflowError) as exc:
        if isinstance(exc, PuzzleFormatError):
            raise
        raise PuzzleFormatError("Bulmaca metadata veya çözümü geçersiz") from exc
