"""Run the offline Nonogram library and game."""

import sys
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtWidgets import QApplication, QMessageBox

from pixel_nonograms.i18n import tr

from .i18n import set_language
from .ui.branding import StartupSplash, application_icon


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("Pixel Nonograms")
    settings = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                         "Pixel Nonograms", "Pixel Nonograms")
    set_language(settings.value("language", "tr"))
    splash = StartupSplash()
    splash.show()
    splash.stage(tr("Kayıtlar hazırlanıyor…"))
    app.processEvents()
    app.setWindowIcon(application_icon())
    database = None
    try:
        from .persistence import Database, SaveManager
        from .services import PuzzleLibrary, built_in_puzzles, load_user_puzzles
        from .ui.main_window import MainWindow

        data_location = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.AppDataLocation
        )
        if not data_location:
            raise OSError("Uygulama veri dizini bulunamadı")
        path = Path(data_location)
        database = Database(path / "progress.sqlite3")
        save_manager = SaveManager(database)
        splash.stage(tr("Bulmacalar yükleniyor…"))
        builtins = built_in_puzzles()
        user_puzzles_dir = path / "puzzles"
        user_puzzles, load_errors = load_user_puzzles(
            user_puzzles_dir, existing_ids=frozenset(puzzle.id for puzzle in builtins)
        )
        library = PuzzleLibrary(builtins + user_puzzles, save_manager, database)
    except Exception as exc:
        if database is not None:
            database.close()
        splash.close()
        QMessageBox.critical(None, tr("Kayıt açılamadı"), tr(str(exc)))
        return 1
    try:
        splash.stage(tr("Oyun hazırlanıyor…"))
        window = MainWindow(library, save_manager, user_puzzles_dir=user_puzzles_dir)
    except Exception as exc:
        splash.close()
        database.close()
        QMessageBox.critical(None, tr("Oyun açılamadı"), tr(str(exc)))
        return 1
    app.aboutToQuit.connect(window.save_before_exit)
    window.showMaximized()
    splash.finish(window)
    if load_errors:
        QMessageBox.warning(
            window,
            tr("Bazı bulmacalar yüklenemedi"),
            tr("\n".join(load_errors[:5])
            + (f"\n... ve {len(load_errors) - 5} başka dosya" if len(load_errors) > 5 else "")),
        )
    try:
        return app.exec()
    finally:
        database.close()


if __name__ == "__main__":
    raise SystemExit(main())
