"""Run the offline Nonogram library and game."""

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from .persistence import Database, SaveManager
from .services import PuzzleLibrary, built_in_puzzles, load_user_puzzles
from .ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Pixel Nonograms")
    database = None
    try:
        data_location = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if not data_location:
            raise OSError("Uygulama veri dizini bulunamadı")
        path = Path(data_location)
        database = Database(path / "progress.sqlite3")
        save_manager = SaveManager(database)
        builtins = built_in_puzzles()
        user_puzzles_dir = path / "puzzles"
        user_puzzles, load_errors = load_user_puzzles(
            user_puzzles_dir, existing_ids=frozenset(puzzle.id for puzzle in builtins)
        )
        library = PuzzleLibrary(builtins + user_puzzles, save_manager, database)
    except Exception as exc:
        if database is not None:
            database.close()
        QMessageBox.critical(None, "Kayıt açılamadı", str(exc))
        return 1
    window = MainWindow(library, save_manager, user_puzzles_dir=user_puzzles_dir)
    app.aboutToQuit.connect(window.save_before_exit)
    window.show()
    if load_errors:
        QMessageBox.warning(
            window,
            "Bazı bulmacalar yüklenemedi",
            "\n".join(load_errors[:5])
            + (f"\n... ve {len(load_errors) - 5} başka dosya" if len(load_errors) > 5 else ""),
        )
    try:
        return app.exec()
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
