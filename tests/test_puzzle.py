from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from pixel_nonograms.core import CellState, Clue, ColorClue, Difficulty, Puzzle, PuzzleMetadata


def make_puzzle(**changes):
    fields = dict(
        id="sample-1",
        title="Örnek",
        author="Yazar",
        description="Küçük bulmaca",
        width=1,
        height=1,
        difficulty=Difficulty.EASY,
        tags=("başlangıç",),
        palette=("#112233",),
        solution=((1,),),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        metadata=PuzzleMetadata(revision=1, source="bundled", license="CC0"),
    )
    fields.update(changes)
    return Puzzle(**fields)


def test_cell_state_values_and_solution_color_ids_are_distinct_concepts():
    assert [CellState.UNKNOWN.value, CellState.FILLED.value, CellState.EMPTY.value] == [0, 1, 2]
    assert make_puzzle().solution == ((1,),)


def test_1x1_and_empty_1x1():
    filled = make_puzzle()
    assert filled.row_clues == ((Clue(1),),)
    assert filled.column_clues == ((Clue(1),),)
    empty = make_puzzle(solution=((0,),))
    assert empty.row_clues == ((),)
    assert empty.column_clues == ((),)


def test_5x5_clues_and_metadata():
    solution = (
        (0, 1, 1, 1, 0),
        (1, 0, 0, 0, 1),
        (1, 0, 1, 0, 1),
        (1, 0, 0, 0, 1),
        (0, 1, 1, 1, 0),
    )
    puzzle = make_puzzle(width=5, height=5, solution=solution)
    assert puzzle.row_clues == (
        (Clue(3),),
        (Clue(1), Clue(1)),
        (Clue(1), Clue(1), Clue(1)),
        (Clue(1), Clue(1)),
        (Clue(3),),
    )
    assert puzzle.column_clues == puzzle.row_clues
    assert puzzle.metadata.revision == 1


def test_50x50_and_immutable_normalized_data():
    source = [[1 if x == y else 0 for x in range(50)] for y in range(50)]
    tags = ["büyük"]
    puzzle = make_puzzle(width=50, height=50, solution=source, tags=tags)
    source[0][0] = 0
    tags.append("sonradan")
    assert puzzle.solution[0][0] == 1
    assert puzzle.tags == ("büyük",)
    assert len(puzzle.row_clues) == len(puzzle.column_clues) == 50
    assert puzzle.column_clues[49] == (Clue(1),)
    with pytest.raises(FrozenInstanceError):
        puzzle.title = "Değiştir"


def test_colored_puzzle_and_supplied_clues():
    puzzle = make_puzzle(
        width=4,
        palette=("#aabbcc", "#123456"),
        solution=((1, 1, 2, 2),),
        row_clues=((ColorClue(2, 1), ColorClue(2, 2)),),
        column_clues=(
            (ColorClue(1, 1),),
            (ColorClue(1, 1),),
            (ColorClue(1, 2),),
            (ColorClue(1, 2),),
        ),
    )
    assert puzzle.is_colored
    assert puzzle.palette == ("#AABBCC", "#123456")
    assert puzzle.row_clues[0] == (ColorClue(2, 1), ColorClue(2, 2))


@pytest.mark.parametrize(
    "changes",
    [
        {"id": " "},
        {"title": ""},
        {"author": None},
        {"description": None},
        {"width": 0},
        {"height": 101},
        {"width": True},
        {"difficulty": "easy"},
        {"tags": ("",)},
        {"tags": ("a", "a")},
        {"palette": ()},
        {"palette": ("red",)},
        {"palette": ("#ABCDEF", "#abcdef")},
        {"solution": ((2,),)},
        {"solution": ((-1,),)},
        {"solution": ((True,),)},
        {"solution": ((1, 0),)},
        {"solution": ()},
        {"created_at": datetime(2026, 1, 1)},
        {"metadata": {}},
        {"row_clues": ((Clue(2),),)},
        {"row_clues": ((ColorClue(1, 1),),)},
        {"column_clues": ()},
    ],
)
def test_invalid_puzzle_data(changes):
    with pytest.raises(ValueError):
        make_puzzle(**changes)


def test_supplied_clues_must_match_solution():
    with pytest.raises(ValueError, match="eşleşmiyor"):
        make_puzzle(width=2, solution=((1, 0),), row_clues=((Clue(2),),))


@pytest.mark.parametrize(
    "changes",
    [{"revision": 0}, {"revision": True}, {"source": " "}, {"license": ""}],
)
def test_invalid_metadata(changes):
    with pytest.raises(ValueError):
        PuzzleMetadata(**changes)
