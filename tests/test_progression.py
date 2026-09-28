"""Permanent milestones, rollback, legacy upgrades and badge UI."""
import os
import sqlite3
from dataclasses import replace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PySide6.QtWidgets import QApplication

from pixel_nonograms.core import EditorDraft, GameSession, HelperItemId
from pixel_nonograms.core.progression import STARTER_IDS
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.persistence.migrations import MIGRATIONS
from pixel_nonograms.services.puzzle_library import PuzzleLibrary
from pixel_nonograms.ui.progression import ProgressionDialog, progression_summary


def candidate(identity='one', colored=False):
    draft = EditorDraft(1, 1)
    if colored:
        draft.add_color('#FF0000')
    draft.set_cell(0, 0, 2 if colored else 1)
    return replace(draft.to_puzzle(title='Test', author='Test'), id=identity,
                   reward_item_id=HelperItemId.LOGIC_HINT)


def finish(manager, puzzle):
    session = GameSession(puzzle)
    session.fill_cell(0, 0, puzzle.solution[0][0])
    assert session.completed
    assert manager.save(session)
    return session


def test_replay_undo_and_restart_never_duplicate_rewards(tmp_path):
    path = tmp_path / 'game.db'
    db = Database(path)
    manager = SaveManager(db)
    session = finish(manager, candidate())
    assert db.milestone_ids() == {'first'}
    db.select_badge('first')
    session.undo()
    manager.save(session)
    assert len(db.completion_history()) == 1
    session.redo()
    manager.save(session)
    finish(manager, candidate())
    assert db.item_count(HelperItemId.LOGIC_HINT) == 3
    db.close()
    db = Database(path)
    assert db.selected_badge() == 'first'
    assert db.milestone_ids() == {'first'}
    assert len(db.completion_history()) == 1
    db.close()


def test_all_missions_and_locked_badge(tmp_path):
    db = Database(tmp_path / 'game.db')
    manager = SaveManager(db)
    with pytest.raises(ValueError):
        db.select_badge('ten')
    for identity in STARTER_IDS:
        finish(manager, candidate(identity))
    assert db.milestone_ids() == {'first', 'three', 'starter'}
    for number in range(7):
        finish(manager, candidate(f'other-{number}', colored=True))
    assert db.milestone_ids() == {'first', 'three', 'starter', 'color', 'ten'}
    db.select_badge('ten')
    assert 'Mozaik Ustası' in progression_summary(db)
    db.select_badge(None)
    assert db.selected_badge() is None
    db.close()


def test_failed_milestone_rolls_back_progress_and_item(tmp_path):
    db = Database(tmp_path / 'game.db')
    db.connection.execute('''CREATE TRIGGER reject_milestone BEFORE INSERT ON milestone_claims
        BEGIN SELECT RAISE(ABORT, 'test failure'); END''')
    with pytest.raises(sqlite3.IntegrityError):
        finish(SaveManager(db), candidate())
    assert db.load_progress('one') is None
    assert not db.completion_history()
    assert not db.milestone_ids()
    assert not db.reward_claimed('one')
    assert db.item_count(HelperItemId.LOGIC_HINT) == 0
    db.close()


def test_v5_migration_preserves_inventory_and_old_reward_history(tmp_path):
    path = tmp_path / 'legacy.db'
    old = sqlite3.connect(path)
    for version in range(1, 6):
        MIGRATIONS[version](old)
    old.execute('PRAGMA user_version = 5')
    old.execute("INSERT INTO inventory VALUES ('logic_hint', 7)")
    old.execute("INSERT INTO reward_claims VALUES ('old', 'logic_hint', '2026-01-01')")
    old.commit()
    old.close()
    db = Database(path)
    assert db.completion_history() == {'old': False}
    assert db.milestone_ids() == {'first'}
    assert db.item_count(HelperItemId.LOGIC_HINT) == 9
    assert len(list(tmp_path.glob('legacy.db.v5.*.bak'))) == 1
    db.close()


def test_old_color_history_enriched_only_from_valid_save(tmp_path):
    db = Database(tmp_path / 'game.db')
    manager = SaveManager(db)
    puzzle = candidate(colored=True)
    finish(manager, puzzle)
    db.connection.execute('UPDATE completions SET colored = 0')
    db.connection.execute("DELETE FROM mission_reward_claims WHERE mission_id = 'color'")
    db.connection.execute("DELETE FROM milestone_claims WHERE mission_id = 'color'")
    db.connection.commit()
    PuzzleLibrary((puzzle,), manager, db)
    assert db.completion_history()['one']
    assert 'color' in db.milestone_ids()
    db.close()


def test_badge_selection_ui_persists(tmp_path):
    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / 'game.db')
    finish(SaveManager(db), candidate())
    dialog = ProgressionDialog(db)
    assert dialog.badge_picker.count() == 2
    assert dialog.bars['first'].value() == 1
    dialog.badge_picker.setCurrentIndex(1)
    app.processEvents()
    assert db.selected_badge() == 'first'
    dialog.close()
    db.close()


def test_completion_receipt_only_announces_new_rewards_once(tmp_path):
    from PySide6.QtCore import QSettings

    from pixel_nonograms.ui.game_screen import GameScreen

    app = QApplication.instance() or QApplication([])
    db = Database(tmp_path / 'game.db')
    session = GameSession(candidate())
    settings = QSettings(str(tmp_path / 'settings.ini'), QSettings.Format.IniFormat)
    screen = GameScreen(session, save_manager=SaveManager(db), settings=settings)
    session.fill_cell(0, 0)
    screen._on_session_changed()
    app.processEvents()
    assert '+1 yıldız' in screen.completion_progression_label.text()
    assert 'Yeni rozet: İlk Adım' in screen.completion_progression_label.text()
    screen.completion_dialog.close()
    session.undo()
    screen._on_session_changed()
    session.redo()
    screen._on_session_changed()
    assert '+1 yıldız' not in screen.completion_progression_label.text()
    assert 'Yeni rozet' not in screen.completion_progression_label.text()
    screen.completion_dialog.close()
    screen.close()
    db.close()



def test_mission_packs_and_old_missing_puzzle_rewards_are_paid_once(tmp_path):
    from pixel_nonograms.core.progression import MISSION_REWARDS

    path = tmp_path / 'rewards.db'
    db = Database(path)
    manager = SaveManager(db)
    sources = [candidate(str(i), colored=(i == 2)) for i in range(3)]
    for source in sources:
        finish(manager, source)
    expected = {item: 0 for item in HelperItemId}
    expected[HelperItemId.LOGIC_HINT] = 3
    for mission in ('first', 'three', 'color'):
        for item, count in MISSION_REWARDS[mission]:
            expected[HelperItemId(item)] += count
    assert db.inventory_counts() == expected
    db.close()
    db = Database(path)
    assert db.inventory_counts() == expected
    # Simulate a historical completion without an item award.
    db.connection.execute("INSERT INTO completions VALUES ('old-no-reward', 0, '2026-01-01')")
    db.connection.commit()
    source = candidate('old-no-reward')
    db.grant_missing_puzzle_rewards((source,))
    expected[HelperItemId.LOGIC_HINT] += 1
    db.grant_missing_puzzle_rewards((source,))
    assert db.inventory_counts() == expected
    db.close()


def test_v7_existing_badge_receives_new_pack_once(tmp_path):
    path = tmp_path / 'v7.db'
    connection = sqlite3.connect(path)
    for version in range(1, 8):
        MIGRATIONS[version](connection)
    connection.execute('PRAGMA user_version = 7')
    connection.execute("INSERT INTO milestone_claims VALUES ('three', '2026-01-01')")
    connection.execute("INSERT INTO inventory VALUES ('logic_hint', 4)")
    connection.commit()
    connection.close()
    db = Database(path)
    assert db.item_count(HelperItemId.LOGIC_HINT) == 7
    assert db.item_count(HelperItemId.ERROR_CHECK) == 1
    db.close()
    db = Database(path)
    assert db.item_count(HelperItemId.LOGIC_HINT) == 7
    assert len(list(tmp_path.glob('v7.db.v7.*.bak'))) == 1
    db.close()
