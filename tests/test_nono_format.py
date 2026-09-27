"""Interoperability and hostile-input tests for the .nono v1 format."""

import hashlib
import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO

import numpy as np
import pytest
from PIL import Image

from pixel_nonograms.core import Difficulty, GameSession, Puzzle, PuzzleMetadata
from pixel_nonograms.importer import PuzzleFormatError, read_puzzle, write_puzzle
from pixel_nonograms.importer.nono_format import MAX_ARCHIVE_BYTES
from pixel_nonograms.persistence import Database, SaveManager


def puzzle(**changes):
    fields = dict(
        id="format-test",
        title="Kapadokya",
        author="Yerel Yazar",
        description="Renkli bir örnek",
        width=3,
        height=2,
        difficulty=Difficulty.MEDIUM,
        tags=("manzara",),
        palette=("#AA3300", "#0099CC"),
        solution=((1, 0, 2), (1, 2, 0)),
        created_at=datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
        metadata=PuzzleMetadata(revision=2, source="bundled", license="CC0"),
    )
    fields.update(changes)
    return Puzzle(**fields)


def entries(path):
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def rewrite(path, *, replacements=None, delete=(), extra=None, compression=zipfile.ZIP_DEFLATED):
    content = entries(path)
    content.update(replacements or {})
    for name in delete:
        content.pop(name)
    content.update(extra or {})
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in content.items():
            archive.writestr(name, data, compress_type=compression)


def change_metadata(path, **changes):
    content = entries(path)
    metadata = json.loads(content["metadata.json"])
    metadata.update(changes)
    rewrite(path, replacements={"metadata.json": json.dumps(metadata).encode()})


def npy(values, dtype=np.uint8):
    output = BytesIO()
    np.save(output, np.asarray(values, dtype=dtype), allow_pickle=False)
    return output.getvalue()


def test_roundtrip_colored_and_canonical_entries(tmp_path):
    source = puzzle()
    path = tmp_path / "colored.nono"
    write_puzzle(source, path)
    assert read_puzzle(path) == source
    content = entries(path)
    assert set(content) == {"metadata.json", "palette.json", "solution.npy", "preview.webp"}
    metadata = json.loads(content["metadata.json"])
    assert metadata["format_version"] == 1
    assert metadata["solution_sha256"] == hashlib.sha256(content["solution.npy"]).hexdigest()
    assert np.load(BytesIO(content["solution.npy"]), allow_pickle=False).tolist() == [
        [1, 0, 2],
        [1, 2, 0],
    ]
    assert content["preview.webp"][:4] == b"RIFF"


@pytest.mark.parametrize("side", [1, 5, 100])
def test_monochrome_sizes(tmp_path, side):
    source = puzzle(
        width=side,
        height=side,
        palette=("#000000",),
        solution=tuple(tuple(1 if x == y else 0 for x in range(side)) for y in range(side)),
    )
    path = tmp_path / "mono.nono"
    write_puzzle(source, path)
    assert read_puzzle(path) == source


def test_progress_stays_in_sqlite(tmp_path):
    source = puzzle()
    database = Database(tmp_path / "progress.sqlite3")
    session = GameSession(source)
    session.fill_cell(0, 0, 1)
    assert SaveManager(database).save(session)
    path = tmp_path / "share.nono"
    write_puzzle(source, path)
    assert "grid_state" not in path.read_bytes().decode("latin1")
    assert read_puzzle(path) == source
    assert SaveManager(database).load(read_puzzle(path)).cells == session.cells
    database.close()


def test_writer_rejects_overwrite_and_invalid_output_without_replacing(tmp_path):
    path = tmp_path / "safe.nono"
    write_puzzle(puzzle(), path)
    before = path.read_bytes()
    with pytest.raises(FileExistsError):
        write_puzzle(puzzle(), path)
    with pytest.raises(PuzzleFormatError):
        write_puzzle(puzzle(), path, preview_webp=b"bad", overwrite=True)
    assert path.read_bytes() == before
    with pytest.raises(PuzzleFormatError):
        write_puzzle(puzzle(description="X" * 4097), tmp_path / "too-long.nono")
    assert not (tmp_path / "too-long.nono").exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"format_version": 2},
        {"width": 101},
        {"height": True},
        {"difficulty": "impossible"},
        {"tags": ["same", "same"]},
        {"tags": [3]},
        {"author": 4},
        {"revision": 0},
        {"solution_sha256": "bad"},
        {"grid_state": [1, 2, 3]},
        {"reward_item_id": "gold"},
        {"reward_item_id": 42},
    ],
)
def test_invalid_metadata_rejected(tmp_path, changes):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    change_metadata(path, **changes)
    with pytest.raises(PuzzleFormatError):
        read_puzzle(path)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"id":"a","id":"b"}',
        b'{"format_version":NaN}',
        b"\xff",
        b"[]",
    ],
)
def test_bad_json_rejected(tmp_path, raw):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    rewrite(path, replacements={"metadata.json": raw})
    with pytest.raises(PuzzleFormatError):
        read_puzzle(path)


@pytest.mark.parametrize("palette", [[], ["red"], ["#ABCDEF", "#abcdef"], [1]])
def test_bad_palette_rejected(tmp_path, palette):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    rewrite(path, replacements={"palette.json": json.dumps(palette).encode()})
    with pytest.raises(PuzzleFormatError):
        read_puzzle(path)


@pytest.mark.parametrize(
    "solution",
    [
        npy([[1, 0, 2], [1, 2, 0]], dtype=np.int32),
        npy([[1, 0, 2]]),
        npy([[3, 0, 2], [1, 2, 0]]),
        b"not npy",
    ],
)
def test_bad_solution_rejected(tmp_path, solution):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    content = entries(path)
    metadata = json.loads(content["metadata.json"])
    metadata.pop("solution_sha256")
    rewrite(
        path,
        replacements={
            "metadata.json": json.dumps(metadata).encode(),
            "solution.npy": solution,
        },
    )
    with pytest.raises(PuzzleFormatError):
        read_puzzle(path)


def test_solution_hash_and_trailing_bytes_rejected(tmp_path):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    content = entries(path)
    rewrite(path, replacements={"solution.npy": content["solution.npy"] + b"x"})
    with pytest.raises(PuzzleFormatError, match="özeti"):
        read_puzzle(path)
    change_metadata(path, solution_sha256=hashlib.sha256(entries(path)["solution.npy"]).hexdigest())
    with pytest.raises(PuzzleFormatError, match="uzunluğu"):
        read_puzzle(path)


def test_object_array_cannot_load_pickle(tmp_path):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    stream = BytesIO()
    np.save(stream, np.array([[object()] * 3] * 2, dtype=object))
    content = entries(path)
    metadata = json.loads(content["metadata.json"])
    metadata.pop("solution_sha256")
    rewrite(
        path,
        replacements={
            "metadata.json": json.dumps(metadata).encode(),
            "solution.npy": stream.getvalue(),
        },
    )
    with pytest.raises(PuzzleFormatError):
        read_puzzle(path)


@pytest.mark.parametrize(
    "mutation",
    [
        {"delete": ("palette.json",)},
        {"delete": ("preview.webp",)},
        {"extra": {"save.json": b"{}"}},
        {"extra": {"../state.sqlite3": b"x"}},
        {"replacements": {"preview.webp": b"not webp"}},
        {"replacements": {"metadata.json": b" " * 32769}},
    ],
)
def test_malformed_archive_rejected(tmp_path, mutation):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    rewrite(path, **mutation)
    with pytest.raises(PuzzleFormatError):
        read_puzzle(path)


def test_duplicate_entry_and_archive_size_rejected(tmp_path):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    with pytest.warns(UserWarning, match="Duplicate name"):
        with zipfile.ZipFile(path, "a") as archive:
            archive.writestr("metadata.json", b"{}")
    with pytest.raises(PuzzleFormatError):
        read_puzzle(path)
    path.write_bytes(b"x" * (MAX_ARCHIVE_BYTES + 1))
    with pytest.raises(PuzzleFormatError, match="boyut"):
        read_puzzle(path)


def test_invalid_extension_and_zip(tmp_path):
    path = tmp_path / "bad.txt"
    with pytest.raises(PuzzleFormatError):
        write_puzzle(puzzle(), path)
    path = tmp_path / "bad.nono"
    path.write_bytes(b"not a ZIP")
    with pytest.raises(PuzzleFormatError):
        read_puzzle(path)


def test_preview_dimensions_rejected(tmp_path):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    preview = BytesIO()
    Image.new("RGB", (513, 1), "white").save(preview, format="WEBP")
    rewrite(path, replacements={"preview.webp": preview.getvalue()})
    with pytest.raises(PuzzleFormatError, match="Önizleme"):
        read_puzzle(path)


def test_compression_ratio_rejected(tmp_path):
    path = tmp_path / "bad.nono"
    write_puzzle(puzzle(), path)
    rewrite(path, replacements={"metadata.json": b" " * 30000})
    with pytest.raises(PuzzleFormatError, match="sıkıştırma oranı"):
        read_puzzle(path)
