"""One-time rewards, deterministic aids, and atomic SQLite consumption."""

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from pixel_nonograms.core import Difficulty, GameSession, HelperItemId, Puzzle
from pixel_nonograms.importer import read_puzzle, write_puzzle
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import InventoryService, built_in_puzzles
from pixel_nonograms.ui.collection_screen import PuzzleCard


def puzzle(puzzle_id, solution, *, reward=None):
    return Puzzle(
        id=puzzle_id,
        title="Örnek",
        author="Test",
        description="",
        width=len(solution[0]),
        height=len(solution),
        difficulty=Difficulty.EASY,
        tags=(),
        palette=("#112233",),
        solution=solution,
        reward_item_id=reward,
    )


def grant(manager, item_id):
    source = puzzle(f"reward-{item_id.value}", ((1,),), reward=item_id)
    session = GameSession(source)
    session.fill_cell(0, 0)
    assert session.completed
    assert manager.save(session)
    return source, session


def target():
    return GameSession(puzzle("target", ((1, 1, 1), (0, 1, 0), (0, 1, 0))))


def test_every_builtin_has_a_reward_and_all_aids_are_available():
    rewards = [
        entry.reward_item_id for entry in built_in_puzzles()
        if entry.reward_item_id is not None
    ]
    assert set(rewards) == set(HelperItemId) - {HelperItemId.COLUMN_SCANNER}
    assert len(rewards) == len(built_in_puzzles())


def test_reward_claimed_once_after_first_completion_and_survives_restart(tmp_path):
    path = tmp_path / "progress.sqlite3"
    database = Database(path)
    manager = SaveManager(database)
    item = HelperItemId.LOGIC_HINT
    source, session = grant(manager, item)
    assert database.reward_claimed(source.id)
    assert database.item_count(item) == 3
    assert manager.save(session)
    assert database.item_count(item) == 3
    session.undo()
    assert manager.save(session)
    session.redo()
    assert manager.save(session)
    assert database.item_count(item) == 3
    database.close()
    database = Database(path)
    assert database.reward_claimed(source.id)
    assert database.item_count(item) == 3
    assert SaveManager(database).save(SaveManager(database).load(source))
    assert database.item_count(item) == 3
    database.close()


def test_previously_completed_puzzle_does_not_receive_retroactive_reward(tmp_path):
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    source = puzzle("old", ((1,),))
    session = GameSession(source)
    session.fill_cell(0, 0)
    assert manager.save(session)
    rewarded = puzzle("old", ((1,),), reward=HelperItemId.ANALYSIS_LENS)
    assert manager.save(manager.load(rewarded))
    assert database.item_count(HelperItemId.ANALYSIS_LENS) == 0
    assert database.reward_claimed("old")
    database.close()






def test_database_error_rolls_back_consumption_and_session_hint(tmp_path):
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    inventory = InventoryService(database, manager)
    grant(manager, HelperItemId.LOGIC_HINT)
    database.connection.execute("""
        CREATE TRIGGER reject_target BEFORE INSERT ON progress
        WHEN NEW.puzzle_id = 'target' BEGIN SELECT RAISE(ABORT, 'test failure'); END
    """)
    session = target()
    with pytest.raises(sqlite3.IntegrityError):
        inventory.use(HelperItemId.LOGIC_HINT, session, origin=(0, 0))
    assert session.hint_count == 0
    assert database.item_count(HelperItemId.LOGIC_HINT) == 3
    assert database.load_progress("target") is None
    database.close()


def test_reward_and_completion_roll_back_together_on_database_error(tmp_path):
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    database.connection.execute("""
        CREATE TRIGGER reject_inventory BEFORE INSERT ON inventory
        BEGIN SELECT RAISE(ABORT, 'test failure'); END
    """)
    source = puzzle("rollback-reward", ((1,),), reward=HelperItemId.LOGIC_HINT)
    session = GameSession(source)
    session.fill_cell(0, 0)
    with pytest.raises(sqlite3.IntegrityError):
        manager.save(session)
    assert database.load_progress(source.id) is None
    assert not database.reward_claimed(source.id)
    assert database.item_count(HelperItemId.LOGIC_HINT) == 0
    database.close()


def test_reward_id_roundtrips_in_nono_and_unknown_id_is_rejected(tmp_path):
    source = puzzle("format-reward", ((1,),), reward="logic_hint")
    path = tmp_path / "reward.nono"
    write_puzzle(source, path)
    assert read_puzzle(path).reward_item_id is HelperItemId.LOGIC_HINT
    with pytest.raises(ValueError, match="ödülü"):
        puzzle("bad", ((1,),), reward="gold")










def test_collection_card_shows_reward_and_claim_state(tmp_path):
    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    source = puzzle("card-reward", ((1,),), reward=HelperItemId.LOGIC_HINT)
    from pixel_nonograms.services import PuzzleLibrary

    library = PuzzleLibrary((source,), manager, database)
    card = PuzzleCard(library.entries()[0])
    assert "İlk tamamlama ödülü" in card.reward_label.toolTip()
    card.close()
    grant_source = GameSession(source)
    grant_source.fill_cell(0, 0)
    assert manager.save(grant_source)
    card = PuzzleCard(library.entries()[0])
    assert "Ödül alındı" in card.reward_label.toolTip()
    card.close()
    app.processEvents()
    database.close()
