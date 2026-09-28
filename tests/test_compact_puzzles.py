"""Compact catalog geometry and compatible legacy progress."""
from pixel_nonograms.core import CellState, EditorDraft, GameSession
from pixel_nonograms.core.compact import compact_puzzle
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import PuzzleLibrary, built_in_puzzles, save_editor_puzzle


def test_catalog_has_no_empty_lines_and_migrates_legacy_notes(tmp_path):
    db = Database(tmp_path / 'game.db')
    manager = SaveManager(db)
    draft = EditorDraft(5, 5)
    draft.set_cell(1, 1, 1)
    draft.set_cell(3, 3, 1)
    original = draft.to_puzzle(title='Old', author='Test')
    session = GameSession(original)
    session.fill_cell(1, 1)
    session.mark_note(3, 3, symbol='?')
    session.mark_empty(0, 0)
    session.toggle_clue('row', 1, 0)
    manager.save(session)
    old_bytes = db.load_progress(original.id).grid_state
    library = PuzzleLibrary((original,), manager, db)
    compact = library.get(original.id)
    assert (compact.width, compact.height) == (2, 2)
    loaded = manager.load(compact)
    assert loaded.cell_at(0, 0).state is CellState.FILLED
    assert loaded.cell_at(1, 1).note_symbol == '?'
    assert loaded.is_clue_crossed('row', 0, 0)
    assert loaded.move_count == session.move_count
    assert db.load_progress(original.id).grid_state == old_bytes
    manager.save(loaded)
    assert manager.load(compact).cells == loaded.cells
    library = PuzzleLibrary(built_in_puzzles(), manager, db)
    assert all(p.width == p.height and "packaged-grid" in p.tags for p in library.puzzles)
    db.close()


def test_compaction_recalculates_merged_runs_and_editor_validates_result(tmp_path):
    draft = EditorDraft(5, 3)
    draft.set_cell(1, 1, 1)
    draft.set_cell(3, 1, 1)
    compact, rows, columns = compact_puzzle(draft.to_puzzle(title='X', author='Y'))
    assert rows == (1,)
    assert columns == (1, 3)
    assert compact.solution == ((1, 1),)
    assert compact.row_clues[0][0].length == 2
    result = save_editor_puzzle(draft, tmp_path, title='X', author='Y')
    assert result.path.exists()
    assert result.puzzle.solution == ((1, 1),)
