"""Editor draft and local puzzle save integration."""

import pytest

from pixel_nonograms.core import ColorClue, EditorDraft
from pixel_nonograms.importer import read_puzzle
from pixel_nonograms.services import load_user_puzzles, save_editor_puzzle
from pixel_nonograms.solver import SolveStatus


def test_drawing_updates_clues_and_flood_fill_respects_boundaries():
    draft = EditorDraft(3, 3)
    assert all(not clues for clues in draft.row_clues)
    assert draft.set_cell(0, 0, 1)
    assert draft.set_cell(2, 0, 1)
    assert [clue.length for clue in draft.row_clues[0]] == [1, 1]
    assert [clue.length for clue in draft.column_clues[0]] == [1]
    assert not draft.set_cell(2, 0, 1)
    assert draft.flood_fill(1, 0, 1) == 7
    assert [clue.length for clue in draft.row_clues[0]] == [3]
    assert draft.set_cell(1, 0, 0)
    assert [clue.length for clue in draft.row_clues[0]] == [1, 1]
    assert draft.clear()
    assert not draft.has_filled_cells
    assert all(not clues for clues in draft.column_clues)


def test_palette_resize_and_metadata_validation():
    draft = EditorDraft(2, 2)
    draft.set_cell(1, 1, 1)
    second = draft.add_color("#ff0000")
    assert second == 2
    draft.set_cell(0, 1, 2)
    assert draft.row_clues[1] == (ColorClue(1, 2), ColorClue(1, 1))
    draft.set_palette_color(2, "#00ff00")
    assert draft.palette[1] == "#00FF00"
    draft.resize(3, 1)
    assert draft.solution == ((0, 0, 0),)
    draft.resize(2, 2)
    draft.set_cell(0, 0, 2)
    draft.remove_color(1)
    assert draft.palette == ("#00FF00",)
    assert draft.cell_at(0, 0) == 1
    with pytest.raises(ValueError, match="En az bir"):
        EditorDraft(1, 1).to_puzzle(title="A", author="B")
    with pytest.raises(ValueError, match="Açıklama"):
        draft.to_puzzle(title="A", author="B", description=None)
    with pytest.raises(ValueError, match="boyut"):
        EditorDraft(101, 1)
    with pytest.raises(ValueError, match="Renk"):
        draft.set_cell(0, 0, 2)


def test_unique_solution_is_saved_and_reloaded(tmp_path):
    draft = EditorDraft(1, 1)
    draft.set_cell(0, 0, 1)
    result = save_editor_puzzle(draft, tmp_path, title="Benim Bulmacam", author="Oyuncu")
    assert result.status is SolveStatus.SOLVED
    assert result.path.exists()
    assert read_puzzle(result.path) == result.puzzle
    loaded, errors = load_user_puzzles(tmp_path)
    assert loaded == (result.puzzle,)
    assert errors == ()


def test_ambiguous_clues_do_not_create_file(tmp_path):
    draft = EditorDraft(2, 2)
    draft.set_cell(0, 0, 1)
    draft.set_cell(1, 1, 1)
    result = save_editor_puzzle(draft, tmp_path, title="Belirsiz", author="Oyuncu")
    assert result.status is SolveStatus.MULTIPLE_SOLUTIONS
    assert result.path is None
    assert not list(tmp_path.glob("*.nono"))


def test_loader_skips_corrupt_and_duplicate_files(tmp_path):
    draft = EditorDraft(1, 1)
    draft.set_cell(0, 0, 1)
    result = save_editor_puzzle(draft, tmp_path, title="A", author="B")
    (tmp_path / "invalid.nono").write_bytes(b"bad archive")
    loaded, errors = load_user_puzzles(tmp_path, existing_ids=frozenset({result.puzzle.id}))
    assert loaded == ()
    assert len(errors) == 2
