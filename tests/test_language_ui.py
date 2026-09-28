"""Language persistence, header actions and translated dynamic labels."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from string import Formatter

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from pixel_nonograms.i18n import LANGUAGES, _catalog, set_language, tr
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import PuzzleLibrary, built_in_puzzles
from pixel_nonograms.ui.main_window import MainWindow
from pixel_nonograms.ui.settings_dialog import SettingsDialog


@pytest.fixture
def window(tmp_path):
    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "language.sqlite")
    manager = SaveManager(database)
    settings = QSettings(str(tmp_path / "preferences.ini"), QSettings.Format.IniFormat)
    widget = MainWindow(PuzzleLibrary(built_in_puzzles(), manager, database), manager,
                        settings=settings)
    widget.show()
    app.processEvents()
    yield widget
    widget.close()
    database.close()
    set_language("tr")


def test_language_roundtrip_and_restart(window):
    selector = window.collection.language_picker
    assert [selector.itemData(i) for i in range(selector.count())] == list(LANGUAGES)
    for code, easy in (("az", "Asan"), ("es", "Fácil"), ("ru", "Легко"),
                       ("en", "Easy"), ("tr", "Kolay")):
        selector.setCurrentIndex(selector.findData(code))
        assert window.collection.category_buttons["Kolay"].text() == easy
        window.collection.category_buttons["Kolay"].click()
        assert all(entry.puzzle.difficulty.value == "easy"
                   for entry in window.collection.visible_entries)
    selector.setCurrentIndex(selector.findData("es"))
    reopened = MainWindow(window.library, window.save_manager, settings=window.settings)
    assert reopened.collection.language_picker.currentData() == "es"
    assert reopened.collection.category_buttons["Kolay"].text() == "Fácil"
    reopened.close()


def test_settings_save_and_exit_uses_save_guard(window, monkeypatch):
    dialog = SettingsDialog(window.settings, window)
    dialog.checkboxes["assist/auto_x"].setChecked(True)
    dialog.accept()
    window.open_puzzle("ilk-adim-01")
    game = window.game_screen
    assert game.session.auto_x_completed_lines
    game.session.fill_cell(2, 0)
    monkeypatch.setattr(game, "save_before_exit", lambda: False)
    game.exit_button.click()
    assert window.isVisible()
    monkeypatch.undo()
    game.exit_button.click()
    assert not window.isVisible()
    saved = window.save_manager.load(game.session.puzzle)
    assert saved.cells == game.session.cells


def test_catalog_placeholders_and_dynamic_translation():
    def fields(text):
        return sorted(field for _, field, _, _ in Formatter().parse(text) if field is not None)

    for source, translations in _catalog.items():
        assert len(translations) == 4
        assert all(text and fields(text) == fields(source) for text in translations)
    set_language("en")
    assert tr("14 bulmaca") == "14 puzzles"
    assert tr("★ 3 yıldız · Rozet seçilmedi") == "★ 3 stars · No badge selected"
    set_language("tr")
