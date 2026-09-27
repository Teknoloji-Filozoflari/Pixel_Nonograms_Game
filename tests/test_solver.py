from itertools import islice, product

import pytest

from pixel_nonograms.core import (
    CellMark,
    CellState,
    Clue,
    ColorClue,
    Difficulty,
    Puzzle,
    analyze_line,
    calculate_clues,
)
from pixel_nonograms.solver import (
    SolveStatus,
    explain_next_logical_move,
    generate_line_possibilities,
    get_next_logical_move,
    solve,
    validate,
    validate_unique_solution,
)

U = CellMark()
X = CellMark(CellState.EMPTY)
F1 = CellMark(CellState.FILLED, 1)
F2 = CellMark(CellState.FILLED, 2)


def puzzle_for(solution, palette=("#112233",)):
    return Puzzle(
        id="solver-test",
        title="Çözücü",
        author="Test",
        description="",
        width=len(solution[0]),
        height=len(solution),
        difficulty=Difficulty.EASY,
        tags=(),
        palette=palette,
        solution=solution,
    )


def test_line_possibility_generation_monochrome_and_marks():
    assert set(generate_line_possibilities((Clue(1),), (U, U, U))) == {
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
    }
    assert list(generate_line_possibilities((Clue(1),), (X, U, F1))) == [(0, 0, 1)]
    assert list(generate_line_possibilities((Clue(1),), (F1, F1))) == []
    assert list(generate_line_possibilities((), (U, X))) == [(0, 0)]


def test_line_possibility_generation_colored_adjacency():
    clues = (ColorClue(1, 1), ColorClue(1, 2))
    assert list(generate_line_possibilities(clues, (U, U), color_count=2)) == [(1, 2)]
    assert list(islice(generate_line_possibilities(clues, (U, U, U), color_count=2), 10)) == [
        (0, 1, 2),
        (1, 0, 2),
        (1, 2, 0),
    ]


@pytest.mark.parametrize("color_count", [1, 2])
def test_generated_possibilities_match_line_analysis(color_count):
    values = range(color_count + 1)
    mark_options = (U, X, F1) if color_count == 1 else (U, X, F1, F2)
    for answer in product(values, repeat=3):
        clues = calculate_clues(answer, colored=color_count > 1)
        for marks in product(mark_options, repeat=3):
            generated = tuple(generate_line_possibilities(clues, marks, color_count=color_count))
            assert (
                len(generated)
                == analyze_line(clues, marks, color_count=color_count).possibility_count
            )


def test_solve_unique_monochrome_and_validation():
    puzzle = puzzle_for(((0, 1, 0), (1, 1, 1), (0, 1, 0)))
    result = solve(puzzle)
    assert result.status is SolveStatus.SOLVED
    assert result.solution == puzzle.solution
    assert result.alternate_solution is None
    assert result.nodes_explored >= 1
    assert result.elapsed_time >= 0
    report = validate(puzzle)
    assert report.status is SolveStatus.SOLVED
    assert report.is_valid and report.is_unique and report.matches_stored_solution
    assert validate_unique_solution(puzzle).status is SolveStatus.SOLVED


def test_solve_unique_colored():
    puzzle = puzzle_for(((1, 2),), ("#112233", "#445566"))
    assert solve(puzzle).solution == ((1, 2),)


def test_unique_puzzle_can_require_bounded_backtracking():
    puzzle = puzzle_for(((0, 0, 1, 1), (1, 1, 0, 0), (1, 0, 0, 1), (0, 1, 0, 0)))
    solved = solve(puzzle)
    assert solved.status is SolveStatus.SOLVED
    assert solved.solution == puzzle.solution
    assert solved.nodes_explored > 1
    assert solve(puzzle, node_limit=1).status is SolveStatus.UNKNOWN_LIMIT


def test_50x50_forced_puzzle_solves_without_search_branching():
    puzzle = puzzle_for(((1,) * 50,) * 50)
    result = solve(puzzle, timeout_seconds=5.0)
    assert result.status is SolveStatus.SOLVED
    assert result.solution == puzzle.solution
    assert result.nodes_explored == 1


def test_multiple_solutions_and_editor_validation():
    puzzle = puzzle_for(((1, 0), (0, 1)))
    result = validate_unique_solution(puzzle)
    assert result.status is SolveStatus.MULTIPLE_SOLUTIONS
    assert {result.solution, result.alternate_solution} == {((1, 0), (0, 1)), ((0, 1), (1, 0))}
    report = validate(puzzle)
    assert report.is_valid is True
    assert report.is_unique is False
    assert report.matches_stored_solution is True


def test_no_solution_from_player_marks():
    puzzle = puzzle_for(((1, 0),))
    result = solve(puzzle, ((X, X),))
    assert result.status is SolveStatus.NO_SOLUTION
    assert result.solution is None


def test_node_limit_returns_unknown_instead_of_false_uniqueness():
    puzzle = puzzle_for(((1, 0), (0, 1)))
    result = solve(puzzle, node_limit=1)
    assert result.status is SolveStatus.UNKNOWN_LIMIT
    assert result.nodes_explored == 1
    report = validate(puzzle, node_limit=1)
    assert report.status is SolveStatus.UNKNOWN_LIMIT
    assert report.is_valid is True
    assert report.is_unique is None


def test_timeout_returns_unknown(monkeypatch):
    puzzle = puzzle_for(((1,),))
    ticks = iter((0.0, 0.0, 2.0, 2.0))
    monkeypatch.setattr("pixel_nonograms.solver.solver.monotonic", lambda: next(ticks))
    result = solve(puzzle, timeout_seconds=1.0)
    assert result.status is SolveStatus.UNKNOWN_LIMIT


@pytest.mark.parametrize(
    "options",
    [
        {"timeout_seconds": 0},
        {"timeout_seconds": float("nan")},
        {"timeout_seconds": float("inf")},
        {"node_limit": 0},
        {"node_limit": True},
    ],
)
def test_invalid_limits(options):
    with pytest.raises(ValueError):
        solve(puzzle_for(((1,),)), **options)


def test_logical_overlap_and_explanation():
    puzzle = puzzle_for(((1, 1, 1),))
    move = get_next_logical_move(puzzle, ((U, U, U),))
    assert (move.x, move.y, move.mark, move.technique) == (0, 0, F1, "overlap")
    assert "1. satır" in explain_next_logical_move(puzzle, ((U, U, U),))


def test_logical_completed_block_empty_move():
    puzzle = puzzle_for(((1, 0, 0),))
    move = get_next_logical_move(puzzle, ((F1, U, U),))
    assert (move.x, move.y, move.mark, move.technique) == (1, 0, X, "completed_block")


def test_logical_impossible_position():
    puzzle = puzzle_for(((1, 0, 0, 1, 0),))
    move = get_next_logical_move(puzzle, ((F1, U, X, U, U),))
    assert move.mark == X
    assert move.technique == "impossible_position"


def test_colored_row_column_intersection_gives_logical_move():
    puzzle = puzzle_for(
        ((1, 0, 2), (0, 1, 0), (0, 2, 0)),
        ("#112233", "#445566"),
    )
    board = ((U, U, U), (U, U, X), (U, U, U))
    move = get_next_logical_move(puzzle, board)
    assert (move.x, move.y, move.mark) == (0, 2, X)
    assert move.technique == "constraint_propagation"


def test_no_logical_move_when_ambiguous():
    puzzle = puzzle_for(((1, 0), (0, 1)))
    board = ((U, U), (U, U))
    assert get_next_logical_move(puzzle, board) is None
    assert explain_next_logical_move(puzzle, board) is None


def test_logical_hint_rejects_contradiction():
    puzzle = puzzle_for(((1, 0),))
    with pytest.raises(ValueError, match="çelişiyor"):
        get_next_logical_move(puzzle, ((F1, F1),))


def test_solver_uses_clues_not_stored_answer():
    puzzle = puzzle_for(((1, 0), (0, 1)))
    alternate_marks = ((X, F1), (F1, X))
    result = solve(puzzle, alternate_marks)
    assert result.status is SolveStatus.SOLVED
    assert result.solution == ((0, 1), (1, 0))
    assert result.solution != puzzle.solution
