"""Raster-to-Nonogram conversion and validation tests."""

import pytest
from PIL import Image

from pixel_nonograms.importer import GRID_SIZES, ImageImportOptions, import_image
from pixel_nonograms.services import convert_image_to_puzzle
from pixel_nonograms.solver import SolveStatus


@pytest.mark.parametrize("image_format,suffix", [("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")])
def test_supported_formats_generate_grid_and_clues(tmp_path, image_format, suffix):
    path = tmp_path / f"shape.{suffix}"
    image = Image.new("RGB", (10, 10), "white")
    for y in range(10):
        for x in range(5):
            image.putpixel((x, y), (0, 0, 0))
    image.save(path, format=image_format)
    draft = import_image(path, ImageImportOptions(size=10))
    assert (draft.width, draft.height) == (10, 10)
    assert [clue.length for clue in draft.row_clues[0]] == [5]
    assert draft.cell_at(0, 0) == 1
    assert draft.cell_at(9, 0) == 0


@pytest.mark.parametrize("size", GRID_SIZES)
def test_supported_grid_sizes_and_solver_status(tmp_path, size):
    path = tmp_path / "solid.png"
    Image.new("RGB", (5, 5), "black").save(path)
    result = convert_image_to_puzzle(path, ImageImportOptions(size=size))
    assert result.draft.width == size
    assert result.draft.height == size
    assert result.status is SolveStatus.SOLVED


def test_alpha_is_flattened_on_white_and_threshold_is_configurable(tmp_path):
    path = tmp_path / "alpha.png"
    image = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    image.putpixel((0, 0), (0, 0, 0, 255))
    image.putpixel((1, 0), (0, 0, 0, 128))
    image.save(path)
    draft = import_image(path, ImageImportOptions(size=10, threshold=100))
    assert draft.cell_at(0, 0) == 1
    assert draft.cell_at(1, 0) == 0
    assert draft.cell_at(2, 0) == 0
    brighter = import_image(path, ImageImportOptions(size=10, threshold=180))
    assert brighter.cell_at(1, 0) == 1


def test_color_quantization_and_color_clues(tmp_path):
    path = tmp_path / "colors.png"
    image = Image.new("RGB", (10, 10), "white")
    image.putpixel((0, 0), (255, 0, 0))
    image.putpixel((1, 0), (0, 0, 255))
    image.save(path)
    draft = import_image(path, ImageImportOptions(size=10, mode="color", colors=3))
    assert set(draft.palette) == {"#FF0000", "#0000FF"}
    assert draft.cell_at(0, 0) != draft.cell_at(1, 0)
    assert [clue.color_id for clue in draft.row_clues[0]] == [
        draft.cell_at(0, 0),
        draft.cell_at(1, 0),
    ]


def test_wide_image_keeps_aspect_ratio_with_white_padding(tmp_path):
    path = tmp_path / "wide.png"
    Image.new("RGB", (20, 10), "black").save(path)
    draft = import_image(path, ImageImportOptions(size=10))
    assert all(cell == 0 for cell in draft.solution[0])
    assert all(cell == 1 for cell in draft.solution[4])


def test_invalid_options_and_images_are_rejected(tmp_path):
    for options in (
        {"size": 12},
        {"mode": "sepia"},
        {"threshold": 0},
        {"colors": 9},
    ):
        with pytest.raises(ValueError):
            ImageImportOptions(**options)
    empty = tmp_path / "white.png"
    Image.new("RGB", (10, 10), "white").save(empty)
    with pytest.raises(ValueError, match="dolu hücre"):
        import_image(empty, ImageImportOptions(size=10))
    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"not an image")
    with pytest.raises(ValueError, match="okunamadı"):
        import_image(invalid)
    bitmap = tmp_path / "bitmap.bmp"
    Image.new("RGB", (10, 10), "black").save(bitmap)
    with pytest.raises(ValueError, match="PNG"):
        import_image(bitmap)
    too_large = tmp_path / "large.png"
    with too_large.open("wb") as stream:
        stream.seek(20 * 1024 * 1024)
        stream.write(b"x")
    with pytest.raises(ValueError, match="20 MB"):
        import_image(too_large)
