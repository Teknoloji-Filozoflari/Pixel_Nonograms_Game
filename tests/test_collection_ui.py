"""Offscreen puzzle browser and board navigation checks."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pixel_nonograms.core import CellState, GameSession
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import PuzzleLibrary, PuzzleStatus, built_in_puzzles
from pixel_nonograms.ui.collection_screen import CollectionScreen
from pixel_nonograms.ui.main_window import MainWindow
from pixel_nonograms.ui.theme import BOARD, PuzzlePreview, theme_color


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


def test_library_has_only_four_filters_and_reads_entries_once(app, tmp_path, monkeypatch):
    database, manager, library = build_library(tmp_path)
    calls = 0
    original = library.entries
    def entries():
        nonlocal calls
        calls += 1
        return original()
    monkeypatch.setattr(library, "entries", entries)
    screen = CollectionScreen(library)
    assert calls == 1
    assert tuple(screen.category_buttons) == ("Tümü", "Kolay", "Orta", "Zor", "Uzman", "Renkli")
    for obsolete in ("show_names_checkbox", "size_combo", "color_combo", "status_combo",
                     "difficulty_combo", "collection_combo", "sort_combo", "album_button"):
        assert not hasattr(screen, obsolete)
    screen.category_buttons["Kolay"].click()
    assert all(e.puzzle.difficulty.value == "easy" for e in screen.visible_entries)
    screen.category_buttons["Uzman"].click()
    assert all(e.puzzle.difficulty.value == "expert" for e in screen.visible_entries)
    screen.category_buttons["Tümü"].click()
    assert len(screen.cards) == len(library.puzzles)
    assert all(c.title_label.text() == c.entry.puzzle.title for c in screen.cards)
    screen.cards[0].favorite_button.click()
    assert database.favorite_ids()
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
    assert card.open_button.text() == "▶"
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
    assert card.preview.hidden
    assert "Kayıt hatası" in card.progress_label.toolTip()
    screen.close()
    database.close()


def test_discovery_preview_uses_saved_moves_and_reveals_only_on_completion(app, tmp_path):
    database, manager, library = build_library(tmp_path)
    settings = QSettings(str(tmp_path / "discovery.ini"), QSettings.Format.IniFormat)
    puzzle = library.get("ilk-adim-01")
    screen = CollectionScreen(library, settings=settings)

    def card():
        return next(item for item in screen.cards if item.entry.puzzle.id == puzzle.id)

    assert card().preview.hidden
    assert card().title_label.text() == puzzle.title
    assert all(
        card().preview.image.pixelColor(x, y) == theme_color(card().preview, "board")
        for y in range(puzzle.height)
        for x in range(puzzle.width)
    )

    session = GameSession(puzzle)
    empty = next(
        (x, y) for y, row in enumerate(puzzle.solution) for x, color in enumerate(row) if not color
    )
    filled = next(
        (x, y) for y, row in enumerate(puzzle.solution) for x, color in enumerate(row) if color
    )
    # A wrong player mark must be displayed without consulting the answer.
    session.fill_cell(*empty)
    manager.save(session)
    screen.refresh()
    assert not card().preview.hidden
    assert card().preview.image.pixelColor(*empty) == theme_color(card().preview, "ink")
    assert card().preview.image.pixelColor(*filled) == theme_color(card().preview, "board")
    assert card().title_label.text() == puzzle.title

    session.clear_cell(*empty)
    for y, row in enumerate(puzzle.solution):
        for x, color in enumerate(row):
            if color:
                session.fill_cell(x, y)
    assert session.completed
    manager.save(session)
    screen.refresh()
    assert card().title_label.text() == puzzle.title
    assert card().preview.image.pixelColor(*filled) == theme_color(card().preview, "ink")
    assert card().preview.image.pixelColor(*empty) == theme_color(card().preview, "board")
    screen.close()
    database.close()


def test_names_are_always_visible_despite_legacy_preference(app, tmp_path):
    database, manager, library = build_library(tmp_path)
    settings = QSettings(str(tmp_path / "names.ini"), QSettings.Format.IniFormat)
    settings.setValue("discovery/show_names", False)
    window = MainWindow(library, manager, settings=settings)
    puzzle = library.get("ilk-adim-01")
    assert all(c.title_label.text() == c.entry.puzzle.title for c in window.collection.cards)
    window.open_puzzle(puzzle.id)
    assert window.game_screen.title_label.text() == puzzle.title
    window.close()
    database.close()


def test_colored_preview_preserves_player_palette(app):
    from PySide6.QtGui import QColor

    puzzle = next(puzzle for puzzle in built_in_puzzles() if puzzle.is_colored)
    session = GameSession(puzzle)
    session.fill_cell(0, 0, color_id=2)
    preview = PuzzlePreview(puzzle, cells=session.cells)
    assert preview.image.pixelColor(0, 0) == QColor(puzzle.palette[1])
    assert preview.image.pixelColor(1, 0) == BOARD
    preview.close()


def test_resume_collections_album_and_next_puzzle(app, tmp_path):
    database, manager, library = build_library(tmp_path)
    settings = QSettings(str(tmp_path / "phase23.ini"), QSettings.Format.IniFormat)
    settings.setValue("appearance/reduce_motion", True)
    window = MainWindow(library, manager, settings=settings)
    window.show()
    first = library.get("ilk-adim-01")
    session = GameSession(first)
    session.fill_cell(2, 0)
    manager.save(session)
    window.collection.refresh()
    window.open_puzzle(first.id)
    assert window.game_screen.session.cell_at(2, 0).state is CellState.FILLED
    game = window.game_screen
    for y, row in enumerate(first.solution):
        for x, color in enumerate(row):
            if color:
                game.session.fill_cell(x, y, color)
    game.board.refresh_session()
    assert game.completion_dialog is not None
    assert game.reveal_animation is None
    next_id = window._next_puzzle_id(first.id)
    game.next_button.click()
    assert window.game_screen.session.puzzle.id == next_id
    assert manager.load(first).completed
    window.game_screen.return_to_library()
    screen = window.collection
    card = next(c for c in screen.cards if c.entry.puzzle.id == first.id)
    assert card.entry.status is PuzzleStatus.COMPLETED
    assert card.title_label.text() == first.title
    window.close()
    database.close()


def test_no_next_when_catalog_completed_and_reveal_animation(app, tmp_path):
    from pixel_nonograms.ui.game_screen import GameScreen

    database, manager, library = build_library(tmp_path)
    settings = QSettings(str(tmp_path / "animation.ini"), QSettings.Format.IniFormat)
    first = library.get("ilk-adim-01")
    tiny_library = PuzzleLibrary((first,), manager, database)
    window = MainWindow(tiny_library, manager, settings=settings)
    assert window._next_puzzle_id(first.id) is None
    screen = GameScreen(GameSession(first), settings=settings)
    screen._show_completion(False, False)
    assert screen.reveal_animation is not None
    assert screen.reveal_animation.duration() == 450
    assert not screen.next_button.isVisible()
    screen.completion_dialog.accept()
    screen.close()
    window.close()
    database.close()
