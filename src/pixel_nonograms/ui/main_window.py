"""Navigation between the puzzle library and an active board."""

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QSettings
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from pixel_nonograms.core import GameSession
from pixel_nonograms.i18n import tr
from pixel_nonograms.persistence import SaveManager
from pixel_nonograms.services import InventoryService, PuzzleLibrary, PuzzleStatus

from .collection_screen import CollectionScreen
from .theme import CONTROL_STYLE, apply_theme, set_theme_style, theme_for

if TYPE_CHECKING:
    from .editor_screen import EditorScreen
    from .game_screen import GameScreen


class MainWindow(QMainWindow):
    def __init__(
        self,
        library: PuzzleLibrary,
        save_manager: SaveManager,
        *,
        settings: QSettings | None = None,
        user_puzzles_dir: str | Path | None = None,
    ) -> None:
        super().__init__()
        self.library = library
        self.save_manager = save_manager
        self.inventory = InventoryService(library.database, save_manager)
        self.settings = (
            settings
            if settings is not None
            else QSettings(
                QSettings.Format.IniFormat,
                QSettings.Scope.UserScope,
                "Pixel Nonograms",
                "Pixel Nonograms",
            )
        )
        from pixel_nonograms.i18n import set_language

        set_language(self.settings.value("language", "tr"))
        self.settings.setValue("appearance/theme", "night")
        self.setProperty("theme_name", "night")
        self.user_puzzles_dir = (
            Path(user_puzzles_dir)
            if user_puzzles_dir is not None
            else library.database.path.parent / "puzzles"
        )
        self.setWindowTitle(tr("Piksel Nonogram"))
        self.resize(1180, 820)
        self.setMinimumSize(820, 640)
        self.fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        self.fullscreen_shortcut.activated.connect(self.toggle_fullscreen)
        set_theme_style(self, CONTROL_STYLE)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.collection = CollectionScreen(library, settings=self.settings)
        self.collection.language_changed.connect(self.set_language)
        self.collection.settings_requested.connect(self.open_settings)
        self.collection.puzzle_requested.connect(self.open_puzzle)
        self.collection.editor_requested.connect(self.open_editor)
        self.stack.addWidget(self.collection)
        self.game_screen: GameScreen | None = None
        self.editor_screen: EditorScreen | None = None
        apply_theme(self, "night")

    def toggle_fullscreen(self) -> None:
        if self.game_screen is not None:
            self.game_screen.toggle_board_fullscreen()

    def set_language(self, code: str) -> None:
        from pixel_nonograms.i18n import set_language, translate_widgets

        self.settings.setValue("language", code)
        self.settings.sync()
        set_language(code)
        translate_widgets(self)

    def open_settings(self) -> None:
        from .settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.settings, self)
        dialog.editor_requested.connect(self.open_editor)
        dialog.tutorial_requested.connect(self.collection.open_tutorial)
        dialog.exec()

    def open_puzzle(self, puzzle_id: str) -> None:
        if self.game_screen is not None or self.editor_screen is not None:
            return
        try:
            puzzle = self.library.get(puzzle_id)
            session = self.save_manager.load(puzzle) or GameSession(puzzle)
        except Exception as exc:
            QMessageBox.warning(self, tr("Bulmaca açılamadı"), tr(str(exc)))
            return
        from .game_screen import GameScreen

        game = GameScreen(
            session,
            parent=self,
            settings=self.settings,
            save_manager=self.save_manager,
            inventory=self.inventory,
            show_back_button=True,
        )
        try:
            game.has_next_puzzle = self._next_puzzle_id(puzzle_id) is not None
        except Exception:
            game.has_next_puzzle = False
        game.next_requested.connect(self.open_next_puzzle)
        game.language_changed.connect(self.set_language)
        game.back_requested.connect(self.return_to_library)
        self.game_screen = game
        self.stack.addWidget(game)
        self.stack.setCurrentWidget(game)

    def _next_puzzle_id(self, current_id: str) -> str | None:
        entries = sorted(
            self.library.entries(),
            key=lambda e: (
                e.puzzle.width * e.puzzle.height,
                e.puzzle.title.casefold(),
                e.puzzle.id,
            ),
        )
        current = next(i for i, entry in enumerate(entries) if entry.puzzle.id == current_id)
        for entry in entries[current + 1 :] + entries[:current]:
            if entry.status in (PuzzleStatus.UNSTARTED, PuzzleStatus.IN_PROGRESS):
                return entry.puzzle.id
        return None

    def open_next_puzzle(self) -> None:
        game = self.game_screen
        if game is None or not game.session.completed or not game.save_before_exit():
            return
        try:
            next_id = self._next_puzzle_id(game.session.puzzle.id)
        except Exception as exc:
            QMessageBox.warning(self, tr("Sonraki bulmaca açılamadı"), tr(str(exc)))
            return
        if next_id is None:
            return
        if game.completion_dialog is not None:
            game.completion_dialog.accept()
        self.return_to_library()
        self.open_puzzle(next_id)

    def open_editor(self) -> None:
        if self.game_screen is not None or self.editor_screen is not None:
            return
        from .editor_screen import EditorScreen

        editor = EditorScreen(self.user_puzzles_dir, parent=self)
        editor.back_requested.connect(self.return_from_editor)
        editor.saved.connect(self._on_editor_saved)
        self.editor_screen = editor
        self.stack.addWidget(editor)
        self.stack.setCurrentWidget(editor)
        apply_theme(editor, theme_for(self).name)

    def _on_editor_saved(self, puzzle) -> None:
        try:
            self.library.add_puzzle(puzzle)
            self.collection.refresh()
        except ValueError as exc:
            QMessageBox.warning(self, tr("Bulmaca eklenemedi"), tr(str(exc)))

    def return_from_editor(self) -> None:
        editor = self.editor_screen
        if editor is None:
            return
        self.stack.setCurrentWidget(self.collection)
        self.stack.removeWidget(editor)
        editor.deleteLater()
        self.editor_screen = None
        self.collection.refresh()

    def return_to_library(self) -> None:
        game = self.game_screen
        if game is None:
            return
        game.exit_board_fullscreen()
        self.stack.setCurrentWidget(self.collection)
        self.stack.removeWidget(game)
        game.deleteLater()
        self.game_screen = None
        self.collection.refresh()

    def save_before_exit(self) -> bool:
        return self.game_screen is None or self.game_screen.save_before_exit()

    def closeEvent(self, event) -> None:
        if not self.save_before_exit():
            event.ignore()
            return
        if self.game_screen is not None:
            self.game_screen.exit_board_fullscreen()
        super().closeEvent(event)
