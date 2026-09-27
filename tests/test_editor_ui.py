"""Offscreen editor controls, save feedback, and library navigation."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image
from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pixel_nonograms.importer import ImageImportOptions
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import (
    EditorSaveResult,
    PuzzleLibrary,
    built_in_puzzles,
    load_user_puzzles,
)
from pixel_nonograms.solver import SolveStatus
from pixel_nonograms.ui.editor_screen import EditorScreen
from pixel_nonograms.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _cell_point(canvas, x, y):
    return QPoint(
        canvas.left_margin + x * canvas.cell_size + canvas.cell_size // 2,
        canvas.top_margin + y * canvas.cell_size + canvas.cell_size // 2,
    )


def test_editor_tools_live_clues_palette_resize_and_clear(app, tmp_path, monkeypatch):
    screen = EditorScreen(tmp_path)
    screen.resize(1180, 820)
    screen.show()
    app.processEvents()
    screen.width_box.setValue(2)
    screen.height_box.setValue(2)
    canvas = screen.canvas
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=_cell_point(canvas, 0, 0))
    assert screen.draft.cell_at(0, 0) == 1
    assert [clue.length for clue in screen.draft.row_clues[0]] == [1]
    QTest.mouseClick(canvas, Qt.MouseButton.RightButton, pos=_cell_point(canvas, 0, 0))
    assert screen.draft.cell_at(0, 0) == 0
    screen.tool_buttons["fill"].click()
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=_cell_point(canvas, 0, 0))
    assert screen.draft.solution == ((1, 1), (1, 1))
    assert [clue.length for clue in screen.draft.column_clues[0]] == [2]
    monkeypatch.setattr(
        "pixel_nonograms.ui.editor_screen.QColorDialog.getColor",
        lambda *_args: QColor("#ff0000"),
    )
    screen.add_color_button.click()
    assert len(screen.draft.palette) == 2
    screen.tool_buttons["pencil"].click()
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=_cell_point(canvas, 1, 1))
    assert screen.draft.cell_at(1, 1) == 2
    assert screen.draft.row_clues[1][-1].color_id == 2
    screen.width_box.setValue(3)
    assert screen.draft.solution[1] == (1, 2, 0)
    screen.clear_button.click()
    assert all(not clues for clues in screen.draft.row_clues)
    screen.close()


def test_editor_save_feedback_and_library_play(app, tmp_path):
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    library = PuzzleLibrary(built_in_puzzles(), manager, database)
    directory = tmp_path / "puzzles"
    window = MainWindow(library, manager, user_puzzles_dir=directory)
    window.show()
    app.processEvents()
    window.collection.editor_requested.emit()
    screen = window.editor_screen
    assert screen is not None
    screen.width_box.setValue(2)
    screen.height_box.setValue(2)
    screen.title_edit.setText("Oyuncu Bulmacası")
    QTest.mouseClick(screen.canvas, Qt.MouseButton.LeftButton, pos=_cell_point(screen.canvas, 0, 0))
    QTest.mouseClick(screen.canvas, Qt.MouseButton.LeftButton, pos=_cell_point(screen.canvas, 1, 1))
    screen.save_button.click()
    assert screen.last_result.status is SolveStatus.MULTIPLE_SOLUTIONS
    assert "Birden fazla çözüm" in screen.status_label.text()
    assert not list(directory.glob("*.nono"))
    QTest.mouseClick(screen.canvas, Qt.MouseButton.LeftButton, pos=_cell_point(screen.canvas, 1, 0))
    screen.save_button.click()
    assert screen.last_result.status is SolveStatus.SOLVED
    assert "Tek çözüm" in screen.status_label.text()
    puzzle = screen.last_result.puzzle
    assert library.get(puzzle.id) == puzzle
    assert directory.joinpath(f"{puzzle.id}.nono").exists()
    screen.back_button.click()
    assert window.editor_screen is None
    assert any(card.entry.puzzle.id == puzzle.id for card in window.collection.cards)
    assert window.collection.size_combo.findData("2x2") >= 0
    window.open_puzzle(puzzle.id)
    assert window.game_screen.session.puzzle.id == puzzle.id
    window.game_screen.back_button.click()
    assert window.close()
    loaded, errors = load_user_puzzles(directory)
    assert errors == ()
    assert loaded == (puzzle,)
    database.close()


def test_no_solution_and_limit_feedback(app, tmp_path, monkeypatch):
    screen = EditorScreen(tmp_path)
    screen.draft.set_cell(0, 0, 1)
    puzzle = screen.draft.to_puzzle(title="Test", author="Oyuncu")
    for status, expected in (
        (SolveStatus.NO_SOLUTION, "Çözüm yok"),
        (SolveStatus.UNKNOWN_LIMIT, "Doğrulama sınırına ulaşıldı"),
    ):
        monkeypatch.setattr(
            "pixel_nonograms.ui.editor_screen.save_editor_puzzle",
            lambda *_args, status=status, **_kwargs: EditorSaveResult(status, puzzle, None),
        )
        screen.save()
        assert expected in screen.status_label.text()
        assert screen.save_button.isEnabled()
    assert not list(tmp_path.glob("*.nono"))
    screen.close()


def test_preview_opens_and_closes(app, tmp_path):
    screen = EditorScreen(tmp_path)
    screen.draft.set_cell(0, 0, 1)
    QTimer.singleShot(0, lambda: app.activeModalWidget().accept())
    screen.show_preview()
    assert screen.draft.cell_at(0, 0) == 1
    screen.close()


def test_image_import_is_editable_and_can_be_saved(app, tmp_path):
    image_path = tmp_path / "siyah-kare.png"
    Image.new("RGB", (12, 12), "black").save(image_path)
    screen = EditorScreen(tmp_path / "puzzles")
    screen.resize(900, 700)
    screen.show()
    app.processEvents()
    screen.import_from_path(image_path, ImageImportOptions(size=10))
    assert screen.draft.solution == tuple((1,) * 10 for _ in range(10))
    assert screen.title_edit.text() == "siyah-kare"
    assert screen.width_box.value() == screen.height_box.value() == 10
    assert "Tek çözüm" in screen.status_label.text()
    QTest.mouseClick(
        screen.canvas, Qt.MouseButton.RightButton, pos=_cell_point(screen.canvas, 0, 0)
    )
    assert screen.draft.cell_at(0, 0) == 0
    screen.save_button.click()
    assert screen.last_result.status is SolveStatus.SOLVED
    assert screen.last_result.path.exists()
    screen.close()
