"""Offscreen puzzle browser and board navigation checks."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pixel_nonograms.core import CellState, GameSession
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import PuzzleLibrary, PuzzleSort, PuzzleStatus, built_in_puzzles
from pixel_nonograms.ui.collection_screen import CollectionScreen
from pixel_nonograms.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def build_library(tmp_path):
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    library = PuzzleLibrary(built_in_puzzles(), manager, database)
    return database, manager, library


def cell_point(board, x, y):
    origin = board.camera.cell_origin(x, y, board.grid_viewport())
    half = board.camera.cell_size / 2
    return QPoint(round(origin.x() + half), round(origin.y() + half))


def test_collection_cards_filters_sorting_and_favorites(app, tmp_path):
    database, manager, library = build_library(tmp_path)
    first = library.get("ilk-adim-01")
    session = GameSession(first)
    session.fill_cell(2, 0)
    manager.save(session)
    screen = CollectionScreen(library)
    screen.resize(1180, 820)
    screen.show()
    app.processEvents()
    assert len(screen.cards) == 12
    card = next(card for card in screen.cards if card.entry.puzzle.id == first.id)
    assert card.open_button.text() == "DEVAM ET"
    assert card.progress_label.text() == "Devam ediyor"
    assert card.preview.image.width() == first.width
    assert any(card.entry.puzzle.title == "Kapadokya" for card in screen.cards)

    for category in ("Kolay", "Orta", "Zor", "Uzman"):
        screen.category_buttons[category].click()
        assert len(screen.visible_entries) == 3
    screen.category_buttons["Tümü"].click()
    screen.color_combo.setCurrentIndex(screen.color_combo.findData("color"))
    assert len(screen.visible_entries) == 1
    assert screen.visible_entries[0].puzzle.is_colored
    screen.color_combo.setCurrentIndex(0)
    screen.color_combo.setCurrentIndex(screen.color_combo.findData("mono"))
    assert all(not entry.puzzle.is_colored for entry in screen.visible_entries)
    screen.color_combo.setCurrentIndex(0)
    screen.status_combo.setCurrentIndex(
        screen.status_combo.findData(PuzzleStatus.IN_PROGRESS.value)
    )
    assert [entry.puzzle.id for entry in screen.visible_entries] == [first.id]
    screen.status_combo.setCurrentIndex(0)
    screen.size_combo.setCurrentIndex(screen.size_combo.findData("20x20"))
    assert [entry.puzzle.title for entry in screen.visible_entries] == ["Kapadokya"]
    screen.size_combo.setCurrentIndex(0)
    screen.difficulty_combo.setCurrentIndex(screen.difficulty_combo.findData("expert"))
    assert {entry.puzzle.title for entry in screen.visible_entries} == {
        "Mozaik", "Yıldız Haritası", "Büyük Çiçek"
    }
    screen.difficulty_combo.setCurrentIndex(0)
    screen.sort_combo.setCurrentIndex(screen.sort_combo.findData(PuzzleSort.SIZE.value))
    assert screen.visible_entries[0].puzzle.title == "İlk Adım"

    card = next(card for card in screen.cards if card.entry.puzzle.id == first.id)
    card.favorite_button.click()
    screen.favorites_checkbox.setChecked(True)
    assert [entry.puzzle.id for entry in screen.visible_entries] == [first.id]
    assert database.favorite_ids() == frozenset({first.id})
    screen.close()
    database.close()


def test_main_window_open_continue_return_and_close(app, tmp_path):
    database, manager, library = build_library(tmp_path)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    window = MainWindow(
        library,
        manager,
        settings=settings,
    )
    window.show()
    app.processEvents()
    assert window.stack.currentWidget() is window.collection
    card = next(card for card in window.collection.cards if card.entry.puzzle.id == "ilk-adim-01")
    card.open_button.click()
    assert window.game_screen is not None
    assert window.game_screen.back_button.isVisible()
    board = window.game_screen.board
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 2, 0))
    assert window.game_screen.session.cell_at(2, 0).state is CellState.FILLED
    window.game_screen.back_button.click()
    assert window.game_screen is None
    assert window.stack.currentWidget() is window.collection
    card = next(card for card in window.collection.cards if card.entry.puzzle.id == "ilk-adim-01")
    assert card.open_button.text() == "DEVAM ET"
    card.open_button.click()
    assert window.game_screen.session.cell_at(2, 0).state is CellState.FILLED
    assert window.close()
    assert manager.load(library.get("ilk-adim-01")).cell_at(2, 0).state is CellState.FILLED
    database.close()


def test_corrupt_progress_card_is_visible_but_cannot_open(app, tmp_path):
    database, manager, library = build_library(tmp_path)
    first = library.get("ilk-adim-01")
    manager.save(GameSession(first))
    database.connection.execute(
        "UPDATE progress SET grid_state = x'99' WHERE puzzle_id = ?", (first.id,)
    )
    database.connection.commit()
    screen = CollectionScreen(library)
    screen.show()
    app.processEvents()
    card = next(card for card in screen.cards if card.entry.puzzle.id == first.id)
    assert card.entry.status is PuzzleStatus.ERROR
    assert not card.open_button.isEnabled()
    assert "Kayıt hatası" in card.progress_label.text()
    screen.close()
    database.close()
