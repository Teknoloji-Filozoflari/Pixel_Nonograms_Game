"""Symbol notes stay noncommittal, reversible and compatible with older saves."""
import os
import sqlite3

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtCore import QPointF, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pixel_nonograms.core import CellMark, CellState, EditorDraft, GameSession
from pixel_nonograms.core.commands import NOTE_SYMBOLS
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.persistence.migrations import MIGRATIONS
from pixel_nonograms.persistence.save_manager import _fingerprint
from pixel_nonograms.ui.game_screen import GameScreen


def puzzle():
    draft = EditorDraft(15, 2)
    draft.set_cell(14, 1, 1)
    return draft.to_puzzle(title='Symbols', author='Test')


def test_all_symbols_survive_save_and_undo_without_filling(tmp_path):
    db = Database(tmp_path / 'notes.db')
    manager = SaveManager(db)
    candidate = puzzle()
    session = GameSession(candidate)
    for x, symbol in enumerate(NOTE_SYMBOLS):
        session.mark_note(x, 0, symbol=symbol)
    assert not session.completed
    assert session.mistake_count == 0
    assert all(session.cell_at(x, 0).state is CellState.UNKNOWN for x in range(12))
    manager.save(session)
    restored = manager.load(candidate)
    assert restored.cells == session.cells
    session.undo()
    assert not session.cell_at(len(NOTE_SYMBOLS) - 1, 0).note
    session.redo()
    assert session.cell_at(len(NOTE_SYMBOLS) - 1, 0).note_symbol == '↑↓'
    session.begin_assumption()
    session.mark_note(0, 0, symbol='?')
    session.cancel_assumption()
    assert session.cell_at(0, 0).note_symbol == ''
    session.fill_cell(0, 0)
    assert not session.mark_note(0, 0, symbol='A')
    session.mark_empty(1, 0)
    assert not session.mark_note(1, 0, symbol='B')
    db.close()


def test_invalid_symbol_and_new_byte_are_rejected(tmp_path):
    with pytest.raises(ValueError):
        CellMark(note=True, note_symbol='unsupported')
    with pytest.raises(ValueError):
        CellMark(note_symbol='A')
    db = Database(tmp_path / 'notes.db')
    candidate = puzzle()
    manager = SaveManager(db)
    manager.save(GameSession(candidate))
    record = db.load_progress(candidate.id)
    data = bytearray(record.grid_state)
    data[2] = 255
    db.connection.execute('UPDATE progress SET grid_state = ?', (bytes(data),))
    db.connection.commit()
    with pytest.raises(ValueError, match='geçersiz hücre'):
        manager.load(candidate)
    db.close()


def test_v6_migration_keeps_legacy_dots_and_reads_v2(tmp_path):
    candidate = puzzle()
    path = tmp_path / 'legacy.db'
    old = sqlite3.connect(path)
    for version in range(1, 7):
        MIGRATIONS[version](old)
    old.execute('PRAGMA user_version = 6')
    old.execute('''INSERT INTO progress VALUES (
        ?, 1, ?, 2, 15, 2, ?, 0, 1, 0, 0,
        '2026-01-01T00:00:00+00:00', 0, '2026-01-01T00:00:00+00:00',
        '2026-01-01T00:00:00+00:00', '[]')''',
        (candidate.id, _fingerprint(candidate), bytes((0, 0, 1, 0)) + bytes(29 * 4)))
    old.commit()
    old.close()
    db = Database(path)
    manager = SaveManager(db)
    restored = manager.load(candidate)
    assert restored.cell_at(0, 0) == CellMark(note=True)
    restored.mark_note(1, 0, symbol='A')
    manager.save(restored)
    assert db.load_progress(candidate.id).state_version == 3
    assert manager.load(candidate).cell_at(1, 0).note_symbol == 'A'
    assert list(tmp_path.glob('legacy.db.v6.*.bak'))
    db.close()


def test_picker_replaces_toggles_and_drag_undoes_as_one_action(tmp_path):
    app = QApplication.instance() or QApplication([])
    session = GameSession(puzzle())
    settings = QSettings(str(tmp_path / 'prefs.ini'), QSettings.Format.IniFormat)
    screen = GameScreen(session, settings=settings)
    screen.resize(1180, 820)
    screen.show()
    app.processEvents()
    board = screen.board
    def point(x):
        origin = board.camera.cell_origin(x, 0, board.grid_viewport())
        return (origin + QPointF(board.camera.cell_size / 2, board.camera.cell_size / 2)).toPoint()

    screen.marker_buttons['A'].click()
    assert screen.tool_buttons['note'].isChecked()
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=point(0))
    assert session.cell_at(0, 0).note_symbol == 'A'
    screen.marker_buttons['?'].click()
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=point(0))
    assert session.cell_at(0, 0).note_symbol == '?'
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=point(0))
    assert not session.cell_at(0, 0).note
    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=point(0))
    QTest.mouseMove(board, point(3))
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=point(3))
    assert all(session.cell_at(x, 0).note_symbol == '?' for x in range(4))
    board.undo()
    assert all(not session.cell_at(x, 0).note for x in range(4))
    screen.close()


@pytest.mark.parametrize('first,second,combined', [('←', '→', '←→'), ('↑', '↓', '↑↓')])
def test_opposite_arrows_coexist_and_each_direction_can_be_removed(first, second, combined):
    session = GameSession(puzzle())
    session.mark_note(0, 0, symbol=first)
    session.mark_note(0, 0, symbol=second)
    assert session.cell_at(0, 0).note_symbol == combined
    session.mark_note(0, 0, symbol=first)
    assert session.cell_at(0, 0).note_symbol == second
    session.undo()
    assert session.cell_at(0, 0).note_symbol == combined
    session.mark_note(0, 0, symbol=second)
    assert session.cell_at(0, 0).note_symbol == first
    session.mark_note(0, 0, symbol=first)
    assert not session.cell_at(0, 0).note


def test_marker_popup_and_icon_only_library_button(tmp_path):
    app = QApplication.instance() or QApplication([])
    settings = QSettings(str(tmp_path / 'popup.ini'), QSettings.Format.IniFormat)
    screen = GameScreen(GameSession(puzzle()), settings=settings, show_back_button=True)
    screen.show()
    app.processEvents()
    assert screen.back_button.text() == ''
    assert not screen.back_button.icon().isNull()
    assert not screen.marker_menu.isVisible()
    assert not screen.marker_buttons['A'].isVisible()
    screen.tool_buttons['note'].click()
    app.processEvents()
    assert screen.marker_menu.isVisible()
    assert all(button.isVisible() for button in screen.marker_buttons.values())
    screen.marker_buttons['←'].click()
    assert not screen.marker_menu.isVisible()
    assert screen.board.note_symbol == '←'
    assert screen.tool_buttons['note'].text() == '←'
    screen.tool_buttons['note'].click()
    QTest.keyClick(screen.marker_menu, Qt.Key.Key_Escape)
    assert not screen.marker_menu.isVisible()
    assert screen.board.note_symbol == '←'
    screen.close()
