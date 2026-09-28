"""Check the installed/frozen application without touching a player's files."""
import tempfile
from collections import Counter
from pathlib import Path


def main():
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    from pixel_nonograms.core import Difficulty
    from pixel_nonograms.i18n import set_language, tr
    from pixel_nonograms.persistence import Database, SaveManager
    from pixel_nonograms.services import PuzzleLibrary, built_in_puzzles
    from pixel_nonograms.ui.main_window import MainWindow

    app = QApplication([])
    app.setApplicationName('Pixel Nonograms Distribution Check')
    with tempfile.TemporaryDirectory(prefix='pixel-nonograms-check-') as temporary:
        root = Path(temporary)
        database = Database(root / 'progress.sqlite3')
        try:
            puzzles = built_in_puzzles()
            counts = Counter((p.difficulty, p.is_colored) for p in puzzles)
            expected = {(difficulty, colored): count
                        for difficulty, mono, color in zip(Difficulty, (275,225,175,125), (100,50,25,25))
                        for colored, count in ((False, mono), (True, color))}
            if counts != expected or len(puzzles) != 1000:
                raise RuntimeError('Bundled puzzle catalog is incomplete')
            for language in ('az', 'es', 'ru', 'en'):
                set_language(language)
                if tr('Ekrana sığdır') == 'Ekrana sığdır' and language != 'az':
                    raise RuntimeError(f'Missing translation: {language}')
            set_language('tr')
            manager = SaveManager(database)
            settings = QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat)
            window = MainWindow(PuzzleLibrary(puzzles, manager, database), manager, settings=settings,
                                user_puzzles_dir=root / 'puzzles')
            window.show()
            app.processEvents()
            window.open_puzzle('ilk-adim-01')
            game = window.game_screen
            game.session.fill_cell(0, 0)
            game.board.refresh_session()
            if not game.save_now():
                raise RuntimeError('Save failed')
            if manager.load(game.session.puzzle).cells != game.session.cells:
                raise RuntimeError('Save round trip failed')
            game.toggle_board_fullscreen()
            app.processEvents()
            if not game.board.fullscreen_clues:
                raise RuntimeError('Fullscreen setup failed')
            game.exit_board_fullscreen()
            window.close()
            app.processEvents()
        finally:
            database.close()
    print('OK: Qt GUI, 1000 puzzles, translations, SQLite save/load and fullscreen')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
