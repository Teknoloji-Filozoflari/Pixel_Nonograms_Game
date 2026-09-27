import pytest

from pixel_nonograms.core import Clue, ColorClue, calculate_clues
from pixel_nonograms.core.validation import validate_clue_line


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ([0, 0, 0], ()),
        ([0], ()),
        ([1], (Clue(1),)),
        ([0, 1, 1, 1, 0, 1, 1], (Clue(3), Clue(2))),
        ([1, 1, 1, 1, 1], (Clue(5),)),
        ([1, 0, 1, 0, 1], (Clue(1), Clue(1), Clue(1))),
    ],
)
def test_monochrome_clues(line, expected):
    assert calculate_clues(line) == expected


def test_color_changes_split_adjacent_runs():
    assert calculate_clues([0, 1, 1, 2, 2, 1, 0, 1], colored=True) == (
        ColorClue(2, 1),
        ColorClue(2, 2),
        ColorClue(1, 1),
        ColorClue(1, 1),
    )


def test_same_color_requires_gap_different_colors_may_touch():
    assert validate_clue_line([ColorClue(2, 1), ColorClue(2, 2)], 4, 2, True)
    with pytest.raises(ValueError, match="sığmıyor"):
        validate_clue_line([ColorClue(2, 1), ColorClue(2, 1)], 4, 2, True)


@pytest.mark.parametrize("line", [[-1], [True], [1.0], [2]])
def test_invalid_monochrome_cells(line):
    with pytest.raises(ValueError):
        calculate_clues(line)


@pytest.mark.parametrize("line", [[-1], [False], [1.0], ["1"]])
def test_invalid_colored_cells(line):
    with pytest.raises(ValueError):
        calculate_clues(line, colored=True)


@pytest.mark.parametrize("clue", [0, -1, True, 1.5])
def test_invalid_clue_length(clue):
    with pytest.raises(ValueError):
        Clue(clue)


@pytest.mark.parametrize("color_id", [0, -1, False, 1.5])
def test_invalid_color_id(color_id):
    with pytest.raises(ValueError):
        ColorClue(1, color_id)


def test_invalid_clue_type_or_color_range():
    with pytest.raises(ValueError):
        validate_clue_line([Clue(1)], 1, 2, True)
    with pytest.raises(ValueError):
        validate_clue_line([ColorClue(1, 3)], 1, 2, True)
