from itertools import product
from math import comb

import pytest

from pixel_nonograms.core import (
    CellMark,
    CellState,
    Clue,
    ColorClue,
    Difficulty,
    GameSession,
    LineStatus,
    Puzzle,
    analyze_board,
    analyze_line,
    calculate_clues,
)

U = CellMark()
X = CellMark(CellState.EMPTY)
F1 = CellMark(CellState.FILLED, 1)
F2 = CellMark(CellState.FILLED, 2)


def make_puzzle(solution, palette=("#112233",)):
    return Puzzle(
        id="analysis-test",
        title="Analiz",
        author="Test",
        description="",
        width=len(solution[0]),
        height=len(solution),
        difficulty=Difficulty.EASY,
        tags=(),
        palette=palette,
        solution=solution,
    )


@pytest.mark.parametrize(
    ("clues", "marks", "status", "count", "forced"),
    [
        ((Clue(1),), (U, U, U), LineStatus.UNRESOLVED, 3, (None, None, None)),
        ((Clue(1),), (X, U, U), LineStatus.VALID_SO_FAR, 2, (X, None, None)),
        ((Clue(1),), (F1, U, U), LineStatus.COMPLETED, 1, (F1, X, X)),
        ((Clue(1),), (F1, F1, U), LineStatus.CONTRADICTION, 0, (None,) * 3),
        ((Clue(3),), (U, U, U), LineStatus.UNRESOLVED, 1, (F1, F1, F1)),
        ((), (U, U), LineStatus.COMPLETED, 1, (X, X)),
        ((), (F1, U), LineStatus.CONTRADICTION, 0, (None, None)),
        ((Clue(1),), (X, X), LineStatus.CONTRADICTION, 0, (None, None)),
        ((Clue(1), Clue(1)), (F1, U, F1), LineStatus.COMPLETED, 1, (F1, X, F1)),
    ],
)
def test_monochrome_line_states(clues, marks, status, count, forced):
    analysis = analyze_line(clues, marks)
    assert analysis.status is status
    assert analysis.possibility_count == count
    assert analysis.forced_cells == forced


def test_colored_neighbors_may_touch_and_same_color_needs_gap():
    adjacent = analyze_line((ColorClue(1, 1), ColorClue(1, 2)), (F1, F2), color_count=2)
    assert adjacent.status is LineStatus.COMPLETED
    assert adjacent.forced_cells == (F1, F2)

    separated = analyze_line((ColorClue(1, 1), ColorClue(1, 1)), (F1, U, F1), color_count=2)
    assert separated.status is LineStatus.COMPLETED
    assert separated.forced_cells == (F1, X, F1)
    wrong_gap = analyze_line((ColorClue(1, 1), ColorClue(1, 1)), (F1, F1, U), color_count=2)
    assert wrong_gap.status is LineStatus.CONTRADICTION


def test_wrong_color_is_contradiction_by_clues():
    result = analyze_line((ColorClue(1, 1),), (F2, U), color_count=2)
    assert result.status is LineStatus.CONTRADICTION


def test_only_proven_completed_clue_is_marked():
    clues = (Clue(3), Clue(2), Clue(4))
    marks = (F1, F1, F1, X) + (U,) * 11
    result = analyze_line(clues, marks)
    assert result.status is LineStatus.VALID_SO_FAR
    assert result.completed_clues == (True, False, False)


def test_ambiguous_equal_blocks_do_not_fade():
    result = analyze_line((Clue(1), Clue(1)), (U, U, F1, U, U))
    assert result.completed_clues == (False, False)


def test_colored_clue_completion_and_contradiction():
    clues = (ColorClue(1, 1), ColorClue(1, 2))
    assert analyze_line(clues, (F1, U), color_count=2).completed_clues == (True, False)
    assert analyze_line(clues, (F1, F2), color_count=2).completed_clues == (True, True)
    assert analyze_line(clues, (F2, F2), color_count=2).completed_clues == (False, False)


def test_board_rows_columns_and_session_marks():
    puzzle = make_puzzle(((1, 0), (0, 1)))
    session = GameSession(puzzle)
    initial = analyze_board(puzzle, session.cells)
    assert [row.status for row in initial.rows] == [LineStatus.UNRESOLVED] * 2
    assert [column.status for column in initial.columns] == [LineStatus.UNRESOLVED] * 2
    session.mark_empty(0, 0)
    session.fill_cell(1, 0)
    session.fill_cell(0, 1)
    session.mark_empty(1, 1)
    result = analyze_board(puzzle, session.cells)
    assert all(line.status is LineStatus.COMPLETED for line in (*result.rows, *result.columns))
    # The player chose the other valid clue solution. This engine does not inspect the answer grid.
    assert not session.completed


def test_board_contradiction_is_local_to_affected_lines():
    puzzle = make_puzzle(((1, 0), (0, 1)))
    session = GameSession(puzzle)
    session.fill_cell(0, 0)
    session.fill_cell(1, 0)
    result = analyze_board(puzzle, session.cells)
    assert result.rows[0].status is LineStatus.CONTRADICTION
    assert result.rows[1].status is LineStatus.UNRESOLVED
    assert result.columns[0].status is LineStatus.COMPLETED
    assert result.columns[1].status is LineStatus.COMPLETED


@pytest.mark.parametrize("color_count", [1, 2])
def test_small_lines_match_brute_force(color_count):
    values = tuple(range(color_count + 1))
    for length in range(1, 5):
        for target in product(values, repeat=length):
            clues = calculate_clues(target, colored=color_count > 1)
            all_answers = [
                candidate
                for candidate in product(values, repeat=length)
                if calculate_clues(candidate, colored=color_count > 1) == clues
            ]
            marks_options = (U, X, F1) if color_count == 1 else (U, X, F1, F2)
            for marks in product(marks_options, repeat=length):
                valid = [
                    answer
                    for answer in all_answers
                    if all(
                        mark.state is CellState.UNKNOWN
                        or (mark.state is CellState.EMPTY and answer[index] == 0)
                        or (mark.state is CellState.FILLED and answer[index] == mark.color_id)
                        for index, mark in enumerate(marks)
                    )
                ]
                result = analyze_line(clues, marks, color_count=color_count)
                assert result.possibility_count == len(valid)
                expected_forced = tuple(
                    (
                        X
                        if answer_values == {0}
                        else CellMark(CellState.FILLED, next(iter(answer_values)))
                    )
                    if len(answer_values := {answer[index] for answer in valid}) == 1
                    else None
                    for index in range(length)
                )
                assert result.forced_cells == expected_forced


def test_many_possible_100_cell_line_uses_dynamic_programming():
    result = analyze_line((Clue(1),) * 25, (U,) * 100)
    assert result.status is LineStatus.UNRESOLVED
    assert result.possibility_count == comb(76, 25)


@pytest.mark.parametrize(
    ("clues", "marks", "colors"),
    [
        ((Clue(1),), (), 1),
        ((Clue(1),), (U,), 0),
        ((Clue(1),), (U,), True),
        ((Clue(1),), (1,), 1),
        ((Clue(1),), (F2,), 1),
        ((Clue(2),), (U,), 1),
        ((ColorClue(1, 1),), (U,), 1),
        ((Clue(1),), (U,), 2),
    ],
)
def test_invalid_line_inputs(clues, marks, colors):
    with pytest.raises(ValueError):
        analyze_line(clues, marks, color_count=colors)


def test_invalid_board_shape():
    puzzle = make_puzzle(((1, 0), (0, 1)))
    with pytest.raises(ValueError):
        analyze_board(puzzle, ((U, U),))
    with pytest.raises(ValueError):
        analyze_board(puzzle, ((U,), (U,)))
