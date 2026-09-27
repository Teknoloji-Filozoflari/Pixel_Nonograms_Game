"""Catalog content, progress summaries, filters, and ordering."""

from datetime import timedelta

import pytest

from pixel_nonograms.core import Difficulty, GameSession, Puzzle
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import (
    PuzzleLibrary,
    PuzzleQuery,
    PuzzleSort,
    PuzzleStatus,
    built_in_puzzles,
)
from pixel_nonograms.solver import SolveStatus, validate_unique_solution


def puzzle_for(puzzle_id, title, solution, difficulty, *, tags=(), palette=("#123456",)):
    return Puzzle(
        id=puzzle_id,
        title=title,
        author="Test",
        description="",
        width=len(solution[0]),
        height=len(solution),
        difficulty=difficulty,
        tags=tags,
        palette=palette,
        solution=solution,
    )


def test_built_in_categories_and_unique_clue_solutions():
    puzzles = built_in_puzzles()
    assert len(puzzles) == 12
    assert len({p.id for p in puzzles}) == len(puzzles)
    assert {p.difficulty for p in puzzles} == set(Difficulty)
    allowed = {
        Difficulty.EASY: {5, 10},
        Difficulty.MEDIUM: set(range(15, 21)),
        Difficulty.HARD: set(range(25, 31)),
        Difficulty.EXPERT: set(range(30, 51)),
    }
    for difficulty in Difficulty:
        group = [p for p in puzzles if p.difficulty is difficulty]
        assert len(group) == 3
        assert all(p.width == p.height and p.width in allowed[difficulty] for p in group)
    assert any("başlangıç" in p.tags for p in puzzles)
    assert any(p.is_colored for p in puzzles)
    cappadocia = next(p for p in puzzles if p.title == "Kapadokya")
    assert (cappadocia.width, cappadocia.height, cappadocia.difficulty) == (
        20,
        20,
        Difficulty.MEDIUM,
    )
    for puzzle in puzzles:
        result = validate_unique_solution(puzzle, timeout_seconds=3)
        assert result.status is SolveStatus.SOLVED, puzzle.title
        assert result.solution == puzzle.solution


def test_query_progress_status_color_size_favorites_and_sorts(tmp_path):
    database = Database(tmp_path / "library.sqlite3")
    manager = SaveManager(database)
    first = puzzle_for("a", "Ada", ((1, 1),), Difficulty.EASY, tags=("başlangıç",))
    second = puzzle_for("b", "Bahar", ((1,),), Difficulty.MEDIUM)
    colored = puzzle_for(
        "c", "Ceviz", ((1, 2, 0),), Difficulty.HARD, palette=("#123456", "#654321")
    )
    library = PuzzleLibrary((first, second, colored), manager, database)
    first_session = GameSession(first)
    first_session.fill_cell(0, 0)
    first_session.last_played_at = first_session.started_at + timedelta(days=1)
    manager.save(first_session)
    second_session = GameSession(second)
    second_session.fill_cell(0, 0)
    second_session.last_played_at = second_session.started_at + timedelta(days=2)
    manager.save(second_session)
    entries = {entry.puzzle.id: entry for entry in library.entries()}
    assert entries["a"].status is PuzzleStatus.IN_PROGRESS
    assert entries["a"].progress == 50
    assert entries["b"].status is PuzzleStatus.COMPLETED
    assert entries["b"].progress == 100
    assert entries["c"].status is PuzzleStatus.UNSTARTED
    assert entries["c"].last_played is None

    def ids(query):
        return [entry.puzzle.id for entry in library.query(query)]

    assert ids(PuzzleQuery(category="Başlangıç")) == ["a"]
    assert ids(PuzzleQuery(category="Renkli")) == ["c"]
    assert ids(PuzzleQuery(category="Orta")) == ["b"]
    assert ids(PuzzleQuery(size=(2, 1))) == ["a"]
    assert ids(PuzzleQuery(difficulty=Difficulty.HARD)) == ["c"]
    assert ids(PuzzleQuery(color_mode="mono")) == ["a", "b"]
    assert ids(PuzzleQuery(status=PuzzleStatus.IN_PROGRESS)) == ["a"]
    assert ids(PuzzleQuery(status=PuzzleStatus.COMPLETED)) == ["b"]
    assert ids(PuzzleQuery(status=PuzzleStatus.UNSTARTED)) == ["c"]
    library.set_favorite("c", True)
    assert ids(PuzzleQuery(favorites_only=True)) == ["c"]
    assert ids(PuzzleQuery(sort=PuzzleSort.SIZE)) == ["b", "a", "c"]
    assert ids(PuzzleQuery(sort=PuzzleSort.DIFFICULTY)) == ["a", "b", "c"]
    assert ids(PuzzleQuery(sort=PuzzleSort.LAST_PLAYED)) == ["b", "a", "c"]
    assert ids(PuzzleQuery(sort=PuzzleSort.PROGRESS)) == ["b", "a", "c"]
    with pytest.raises(KeyError):
        library.set_favorite("missing", True)
    database.close()


def test_corrupt_progress_remains_visible_as_error_card(tmp_path):
    database = Database(tmp_path / "corrupt.sqlite3")
    manager = SaveManager(database)
    puzzle = puzzle_for("one", "Bir", ((1,),), Difficulty.EASY)
    manager.save(GameSession(puzzle))
    database.connection.execute("UPDATE progress SET grid_state = x'99' WHERE puzzle_id = 'one'")
    database.connection.commit()
    entry = PuzzleLibrary((puzzle,), manager, database).entries()[0]
    assert entry.status is PuzzleStatus.ERROR
    assert entry.error
    assert database.load_progress("one").grid_state == bytes((0x99,))
    database.close()
