"""Language switching preserves play state; only the dark theme is available."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from pixel_nonograms.i18n import LANGUAGES, set_language
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import PuzzleLibrary, built_in_puzzles
from pixel_nonograms.ui.main_window import MainWindow
from pixel_nonograms.ui.theme import THEMES, theme_color, theme_for


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, tmp_path):
    db = Database(tmp_path / "themes.sqlite3")
    manager = SaveManager(db)
    library = PuzzleLibrary(built_in_puzzles(), manager, db)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    settings.setValue("appearance/theme", "paper")
    widget = MainWindow(library, manager, settings=settings)
    widget.show()
    app.processEvents()
    yield widget
    widget.close()
    db.close()
    set_language("tr")


def test_language_switch_preserves_moves_zoom_and_saved_preference(app, window):
    assert theme_for(window).name == "night"
    window.open_puzzle("ilk-adim-01")
    game = window.game_screen
    game.session.fill_cell(2, 0)
    game.board.refresh_session()
    game.board.zoom(1.5)
    app.processEvents()
    cells = game.session.cells
    zoom = game.board.camera.cell_size
    game.language_picker.setCurrentIndex(game.language_picker.findData("en"))
    app.processEvents()
    assert game.session.cells == cells
    assert game.session.can_undo
    assert game.board.camera.cell_size == zoom
    assert theme_for(game.board).name == "night"
    assert theme_for(window.collection).name == "night"
    assert window.collection.language_picker.currentData() == "en"
    window.settings.sync()
    saved = QSettings(window.settings.fileName(), QSettings.Format.IniFormat)
    assert saved.value("appearance/theme") == "night"
    assert saved.value("language") == "en"
    assert game.title_label.text() == "First Step"
    game.return_to_library()
    card = next(c for c in window.collection.cards if c.entry.puzzle.id == "ilk-adim-01")
    assert card.preview.image.pixelColor(2, 0) == theme_color(card.preview, "ink")
    window.collection.set_language("tr")
    assert card.preview.image.pixelColor(2, 0) == theme_color(card.preview, "ink")
    assert card.preview.image.pixelColor(0, 0) == theme_color(card.preview, "board")
    window.open_puzzle("ilk-adim-01")
    assert window.game_screen.session.cells == cells


def test_color_swatches_and_compact_toolbar_in_all_languages(app, window):
    puzzle = next(p for p in window.library.puzzles if p.is_colored)
    window.open_puzzle(puzzle.id)
    window.resize(820, 640)
    game = window.game_screen
    for name in LANGUAGES:
        game.set_language(name)
        game.color_picker.setCurrentIndex(1)
        app.processEvents()
        assert game.color_picker.currentData() == 2
        assert game.board.color_id == 2
        icon = game.color_picker.itemIcon(1).pixmap(24, 24).toImage()
        assert icon.pixelColor(12, 12) == QColor(puzzle.palette[1])
        assert window.width() == 820
        for button in [
            *game.tool_buttons.values(),
            game.undo_button,
            game.redo_button,
            game.assumption_start_button,
        ]:
            assert game.toolbar.rect().contains(button.geometry())
        game.board.begin_assumption()
        app.processEvents()
        assert game.assumption_accept_button.isVisible()
        assert game.toolbar.rect().contains(game.assumption_accept_button.geometry())
        assert game.toolbar.rect().contains(game.assumption_cancel_button.geometry())
        game.board.cancel_assumption()


def test_editor_and_completion_dialog_follow_theme(app, window):
    window.open_editor()
    assert theme_for(window.editor_screen.canvas).name == "night"
    window.set_language("ru")
    assert theme_for(window.editor_screen.canvas).name == "night"
    window.return_from_editor()
    window.open_puzzle("ilk-adim-01")
    game = window.game_screen
    for y, row in enumerate(game.session.puzzle.solution):
        for x, color in enumerate(row):
            if color:
                game.session.fill_cell(x, y, color)
    game.board.refresh_session()
    game._on_session_changed()
    assert game.completion_dialog is not None
    game.set_language("es")
    assert theme_for(game.completion_dialog).name == "night"
    assert game.completion_preview.image.pixelColor(2, 0) == theme_color(game, "ink")
    game.completion_dialog.accept()


def test_unknown_saved_theme_falls_back_to_night(app, tmp_path):
    db = Database(tmp_path / "invalid.sqlite3")
    manager = SaveManager(db)
    settings = QSettings(str(tmp_path / "invalid.ini"), QSettings.Format.IniFormat)
    settings.setValue("appearance/theme", "retired-theme")
    widget = MainWindow(PuzzleLibrary(built_in_puzzles(), manager, db), manager, settings=settings)
    assert theme_for(widget).name == "night"
    assert not hasattr(widget.collection, "theme_picker")
    assert tuple(THEMES) == ("night",)
    widget.close()
    db.close()
    set_language("tr")


def test_top_toolbar_combines_markers_and_opens_helpers_without_spending(app, window):
    from test_inventory import grant

    from pixel_nonograms.core import HelperItemId

    grant(window.save_manager, HelperItemId.ROW_SCANNER)
    window.open_puzzle("ilk-adim-01")
    window.resize(820, 640)
    game = window.game_screen
    app.processEvents()
    assert game.toolbar.geometry().bottom() < game.board_stage.geometry().top()
    assert list(game.tool_buttons) == ["fill", "empty", "note", "pan"]
    game._open_marker_menu()
    game.clear_marker_button.click()
    assert game.board.tool == "clear"
    assert game.tool_buttons["note"].isChecked()
    game._open_marker_menu()
    game.marker_buttons["A"].click()
    assert game.board.tool == "note"
    assert game.board.note_symbol == "A"
    counts = window.inventory.counts()
    game.hints_button.click()
    app.processEvents()
    assert game.inventory_toolbar.menu.isVisible()
    assert len(game.inventory_toolbar.item_buttons) == 5
    game.inventory_toolbar.item_buttons[HelperItemId.ROW_SCANNER].click()
    app.processEvents()
    assert not game.inventory_toolbar.menu.isVisible()
    assert not game.inventory_toolbar.isVisible()
    assert game.board.line_helper
    assert window.inventory.counts() == counts
    game.inventory_toolbar.select_item(None)
    assert not game.inventory_toolbar.isVisible()


def test_fullscreen_is_only_the_board_and_restores_same_session(app, window):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window.open_puzzle("ilk-adim-01")
    game = window.game_screen
    game.session.fill_cell(2, 0)
    original = game.session.cells
    game.fullscreen_button.click()
    app.processEvents()
    dialog = game.board_fullscreen_dialog
    assert dialog.isFullScreen()
    assert not window.isFullScreen()
    assert game.board.window() is dialog
    assert game.toolbar.window() is window
    assert game.board_shell.size() == game.board_stage.size()
    assert game.board.camera.cell_size > 80
    assert not game.board_drag_handle.isVisible()
    QTest.keyClick(game.board, Qt.Key.Key_Escape)
    app.processEvents()
    assert game.board_fullscreen_dialog is None
    assert game.board.window() is window
    assert game.board_drag_handle.isVisible()
    assert game.board.camera.max_cell_size == 80
    assert game.session.cells == original
    assert game.session.can_undo
    window.toggle_fullscreen()
    app.processEvents()
    assert game.board_fullscreen_dialog is not None
    window.return_to_library()
    app.processEvents()
    assert window.game_screen is None


def test_smart_helper_ui_changes_grid_and_marks_only_corrected_cell(app, window):
    from test_inventory import puzzle

    from pixel_nonograms.core import CellState, GameSession, HelperItemId

    reward = GameSession(puzzle("smart-reward", ((1,),), reward=HelperItemId.ANALYSIS_LENS))
    reward.fill_cell(0, 0)
    window.save_manager.save(reward)
    window.open_puzzle("ilk-adim-01")
    game = window.game_screen
    game.session.fill_cell(0, 0)
    game.inventory_toolbar.item_buttons[HelperItemId.ANALYSIS_LENS].click()
    app.processEvents()
    assert game.session.cell_at(0, 0).state is CellState.EMPTY
    assert game.board.corrected_cell == (0, 0)
    assert game.board._hint_cell is None
    assert not game.inventory_toolbar.isVisible()
    assert game.inventory_toolbar.item_buttons[HelperItemId.ANALYSIS_LENS].toolTip()
    assert window.save_manager.load(game.session.puzzle).cells == game.session.cells


@pytest.mark.parametrize("name", THEMES)
def test_theme_text_and_puzzle_contrast(name):
    def luminance(value):
        color = QColor(value)
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(v * w for v, w in zip(linear, [0.2126, 0.7152, 0.0722]))

    colors = THEMES[name].colors
    for foreground, background in [
        ("text", "paper"),
        ("text", "button"),
        ("ink", "board"),
        ("ink", "clue"),
        ("muted", "paper"),
        ("on_accent", "accent"),
        ("on_primary", "primary"),
        ("selected_text", "selected"),
    ]:
        values = sorted([luminance(colors[foreground]), luminance(colors[background])])
        assert (values[1] + 0.05) / (values[0] + 0.05) >= 4.5
