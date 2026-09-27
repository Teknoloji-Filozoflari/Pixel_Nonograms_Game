"""Navigation between the puzzle library and an active board."""

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMainWindow, QMessageBox, QStackedWidget

from pixel_nonograms.core import GameSession
from pixel_nonograms.persistence import SaveManager
from pixel_nonograms.services import InventoryService, PuzzleLibrary

from .collection_screen import CollectionScreen
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
        self.settings = settings
        self.user_puzzles_dir = (
            Path(user_puzzles_dir)
            if user_puzzles_dir is not None
            else library.database.path.parent / "puzzles"
        )
        self.setWindowTitle("Pixel Nonograms")
        self.resize(1180, 820)
        self.setMinimumSize(820, 640)
        self.setStyleSheet("QMainWindow, QStackedWidget { background: #171D24; }")
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.collection = CollectionScreen(library)
        self.collection.puzzle_requested.connect(self.open_puzzle)
        self.collection.editor_requested.connect(self.open_editor)
        self.stack.addWidget(self.collection)
        self.game_screen: GameScreen | None = None
        self.editor_screen: EditorScreen | None = None

    def open_puzzle(self, puzzle_id: str) -> None:
        if self.game_screen is not None or self.editor_screen is not None:
            return
        try:
            puzzle = self.library.get(puzzle_id)
            session = self.save_manager.load(puzzle) or GameSession(puzzle)
        except Exception as exc:
            QMessageBox.warning(self, "Bulmaca açılamadı", str(exc))
            return
        game = GameScreen(
            session,
            parent=self,
            settings=self.settings,
            save_manager=self.save_manager,
            inventory=self.inventory,
            show_back_button=True,
        )
        game.back_requested.connect(self.return_to_library)
        self.game_screen = game
        self.stack.addWidget(game)
        self.stack.setCurrentWidget(game)

    def open_editor(self) -> None:
        if self.game_screen is not None or self.editor_screen is not None:
            return
        editor = EditorScreen(self.user_puzzles_dir, parent=self)
        editor.back_requested.connect(self.return_from_editor)
        editor.saved.connect(self._on_editor_saved)
        self.editor_screen = editor
        self.stack.addWidget(editor)
        self.stack.setCurrentWidget(editor)

    def _on_editor_saved(self, puzzle) -> None:
        try:
            self.library.add_puzzle(puzzle)
            self.collection.refresh()
        except ValueError as exc:
            QMessageBox.warning(self, "Bulmaca eklenemedi", str(exc))

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
        super().closeEvent(event)
