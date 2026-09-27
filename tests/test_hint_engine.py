"""Teaching hints reveal a line, a reason, then one clue-forced cell."""

import pytest

from pixel_nonograms.core import CellMark, CellState, Difficulty, Puzzle, analyze_line
from pixel_nonograms.solver import create_hint_plan, get_hint

U = CellMark()
X = CellMark(CellState.EMPTY)
F = CellMark(CellState.FILLED, 1)


def puzzle_for(solution, palette=("#112233",)):
    return Puzzle(
        id="hint-test",
        title="İpucu",
        author="Test",
        description="",
        width=len(solution[0]),
        height=len(solution),
        difficulty=Difficulty.EASY,
        tags=(),
        palette=palette,
        solution=solution,
    )


def test_overlap_teaches_block_shared_region_before_revealing_cell():
    puzzle = puzzle_for(((0, 1, 1, 1, 1, 1, 1, 1, 1, 0),))
    cells = ((U,) * 10,)
    plan = create_hint_plan(puzzle, cells)
    assert plan is not None
    assert plan.move.technique == "overlap"
    assert "1. satır" in plan.step(1).message
    assert plan.step(1).cell is None
    assert "8 uzunluğundaki blok" in plan.step(2).message
    assert "6 henüz işaretlenmemiş kesin dolu hücre" in plan.step(2).message
    assert plan.step(2).cell is None
    assert "(3, 1)" in plan.step(3).message
    assert plan.step(3).cell == (2, 0, F)
    assert plan.matches(cells)
    assert not plan.matches(((F,) + (U,) * 9,))


def test_possible_starts_are_computed_from_valid_line_placements():
    from pixel_nonograms.core import Clue

    line = analyze_line((Clue(8),), (U,) * 10)
    assert line.possible_starts == (frozenset({0, 1, 2}),)


def test_completed_block_hint_reveals_empty_mark_only_at_level_three():
    puzzle = puzzle_for(((1, 0, 0),))
    plan = create_hint_plan(puzzle, ((F, U, U),))
    assert "toplamı 1 dolu hücre" in plan.step(2).message
    assert "(2, 1)" in plan.step(3).message
    assert plan.step(3).cell == (1, 0, X)


def test_column_hint_when_rows_have_no_forced_cell():
    puzzle = puzzle_for(((1, 0), (1, 0), (1, 0)))
    plan = create_hint_plan(puzzle, ((U, U),) * 3)
    assert plan.step(1).axis == "column"
    assert "1. sütun" in plan.step(1).message
    assert plan.step(3).cell == (0, 0, F)


def test_hint_uses_clues_even_when_player_follows_an_alternate_solution():
    puzzle = puzzle_for(((1, 0), (0, 1)))
    plan = create_hint_plan(puzzle, ((U, U), (F, U)))
    assert plan is not None
    assert plan.step(3).cell == (1, 1, X)
    assert puzzle.solution[1][1] == 1


def test_colored_hint_mentions_color_without_guessing():
    puzzle = puzzle_for(((1, 2),), ("#112233", "#445566"))
    plan = create_hint_plan(puzzle, ((U, U),))
    assert "renk" in plan.step(2).message
    assert plan.step(3).cell == (0, 0, F)


def test_cross_constraint_hint_focuses_both_lines():
    puzzle = puzzle_for(
        ((1, 0, 2), (0, 1, 0), (0, 2, 0)),
        ("#112233", "#445566"),
    )
    board = ((U, U, U), (U, U, X), (U, U, U))
    plan = create_hint_plan(puzzle, board)
    assert plan.move.axis == "cross"
    assert "satır ve" in plan.step(1).message
    assert "sütuna bak" in plan.step(1).message
    assert "ortak olasılıkları" in plan.step(2).message
    assert plan.step(3).cell == (0, 2, X)


def test_impossible_position_explains_why_cell_is_empty():
    puzzle = puzzle_for(((1, 0, 0, 1, 0),))
    plan = create_hint_plan(puzzle, ((F, U, X, U, U),))
    assert plan.move.technique == "impossible_position"
    assert "hiçbir blok yerleşemediği" in plan.step(2).message


def test_no_forced_move_and_invalid_levels():
    puzzle = puzzle_for(((1, 0), (0, 1)))
    board = ((U, U), (U, U))
    assert create_hint_plan(puzzle, board) is None
    assert get_hint(puzzle, board, 1) is None
    with pytest.raises(ValueError, match="seviyesi"):
        get_hint(puzzle, board, 0)
    plan = create_hint_plan(puzzle_for(((1,),)), ((U,),))
    with pytest.raises(ValueError, match="seviyesi"):
        plan.step(4)


def test_contradictory_marks_do_not_generate_hint():
    puzzle = puzzle_for(((1, 0),))
    with pytest.raises(ValueError, match="çelişiyor"):
        create_hint_plan(puzzle, ((F, F),))
