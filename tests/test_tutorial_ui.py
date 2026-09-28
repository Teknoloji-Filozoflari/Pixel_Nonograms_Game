"""Real input through the tutorial must teach without touching puzzle saves."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QWidget

from pixel_nonograms.core import CellState, HelperItemId
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import PuzzleLibrary, built_in_puzzles
from pixel_nonograms.ui.main_window import MainWindow
from pixel_nonograms.ui.tutorial import LESSONS, TutorialDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def point(board, x):
    origin = board.camera.cell_origin(x, 0, board.grid_viewport())
    return QPoint(
        round(origin.x() + board.camera.cell_size / 2),
        round(origin.y() + board.camera.cell_size / 2),
    )


def test_four_lessons_require_correct_marks_and_teach_both_color_rules(app, tmp_path):
    parent = QWidget()
    settings = QSettings(str(tmp_path / "tutorial.ini"), QSettings.Format.IniFormat)
    dialog = TutorialDialog(parent, settings)
    dialog.show()
    app.processEvents()
    assert not dialog.next_button.isEnabled()
    dialog.go_next()
    assert dialog.index == 0
    QTest.mouseClick(dialog.board, Qt.MouseButton.RightButton, pos=point(dialog.board, 0))
    assert "uyuşmuyor" in dialog.feedback.text()
    dialog.board.undo()
    for index, lesson in enumerate(LESSONS):
        assert dialog.index == index
        app.processEvents()
        for x, color in enumerate(lesson.solution):
            if color:
                dialog.colors.setCurrentIndex(color - 1)
                dialog.tools["fill"].click()
                QTest.mouseClick(
                    dialog.board, Qt.MouseButton.LeftButton, pos=point(dialog.board, x)
                )
            else:
                # A solved picture alone is insufficient: explicitly mark the gap.
                assert not dialog.next_button.isEnabled()
                QTest.mouseClick(
                    dialog.board, Qt.MouseButton.RightButton, pos=point(dialog.board, x)
                )
        assert dialog.next_button.isEnabled()
        dialog.go_next()
    assert dialog.result() == dialog.DialogCode.Accepted
    assert settings.value("tutorial/completed", False, type=bool)
    repeat = TutorialDialog(parent, settings)
    assert repeat.index == 0
    assert not repeat.next_button.isEnabled()
    repeat.close()
    parent.close()


def test_free_three_stage_hint_resets_after_move_and_retry(app, tmp_path):
    parent = QWidget()
    settings = QSettings(str(tmp_path / "hints.ini"), QSettings.Format.IniFormat)
    dialog = TutorialDialog(parent, settings)
    dialog.show()
    app.processEvents()
    original = dialog.board.session.cells
    for level in (1, 2, 3):
        dialog.hint_button.click()
        assert dialog.hint_level == level
        assert "Ücretsiz" in dialog.hint_text.text()
        assert dialog.board.session.cells == original
    assert dialog.board.session.hint_count == 0
    QTest.mouseClick(dialog.board, Qt.MouseButton.LeftButton, pos=point(dialog.board, 0))
    assert dialog.plan is None and not dialog.hint_text.text()
    dialog.load_lesson()
    assert all(mark.state is CellState.UNKNOWN for mark in dialog.board.session.cells[0])
    assert not dialog.next_button.isEnabled()
    dialog.reject()
    assert not settings.value("tutorial/completed", False, type=bool)
    parent.close()


def test_tutorial_can_close_without_changing_active_game_or_inventory(app, tmp_path):
    db = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(db)
    library = PuzzleLibrary(built_in_puzzles(), manager, db)
    settings = QSettings(str(tmp_path / "game.ini"), QSettings.Format.IniFormat)
    window = MainWindow(library, manager, settings=settings)
    window.open_puzzle("ilk-adim-01")
    game = window.game_screen
    game.session.fill_cell(2, 0)
    game.board.refresh_session()
    cells = game.session.cells
    counts = {item: db.item_count(item) for item in HelperItemId}
    game.open_tutorial()
    dialog = game.tutorial_dialog
    dialog.show_hint()
    dialog.reject()
    assert game.session.cells == cells
    assert game.session.can_undo
    assert counts == {item: db.item_count(item) for item in HelperItemId}
    assert db.load_progress("practice-0") is None
    window.close()
    assert manager.load(library.get("ilk-adim-01")).cells == cells
    db.close()
