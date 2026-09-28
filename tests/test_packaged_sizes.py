"""Keep bundled board sizes and restore legacy compact coordinates."""
from dataclasses import replace

import pytest

from pixel_nonograms.core import CellState, GameSession
from pixel_nonograms.core.compact import compact_puzzle
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import built_in_puzzles


@pytest.mark.parametrize('puzzle_id', ['renkli-ev-07-01', 'kapadokya-01', 'collection-easy-01'])
@pytest.mark.parametrize('complete', [False, True])
def test_restore_legacy_compacted_save_to_packaged_square(tmp_path, puzzle_id, complete):
    puzzle = next(p for p in built_in_puzzles() if p.id == puzzle_id)
    old, rows, columns = compact_puzzle(replace(puzzle, tags=()))
    assert (old.width, old.height) != (puzzle.width, puzzle.height)
    database = Database(tmp_path / 'saved.sqlite')
    manager = SaveManager(database)
    session = GameSession(old)
    if complete:
        for y, row in enumerate(old.solution):
            for x, color in enumerate(row):
                if color:
                    session.fill_cell(x, y, color)
    else:
        session.fill_cell(0, 0)
        session.mark_empty(1, 0)
        session.toggle_clue('row', 0, 0)
    manager.save(session)
    manager.register_original(puzzle)
    restored = manager.load(puzzle)
    assert restored.completed == session.completed
    assert restored.move_count == session.move_count
    for y, old_y in enumerate(rows):
        for x, old_x in enumerate(columns):
            assert restored.cell_at(old_x, old_y) == session.cell_at(x, y)
    assert all(restored.cell_at(x, y).state is CellState.UNKNOWN
               for y in range(puzzle.height) for x in range(puzzle.width)
               if y not in rows or x not in columns)
    assert restored.snapshot().crossed_clues == tuple(
        (axis, (rows if axis == 'row' else columns)[line], clue)
        for axis, line, clue in session.snapshot().crossed_clues
    )
    manager.save(restored)
    assert manager.load(puzzle).cells == restored.cells
    database.close()
