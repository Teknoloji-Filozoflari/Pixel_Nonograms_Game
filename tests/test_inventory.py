"""One-time rewards, deterministic aids, and atomic SQLite consumption."""

import os
import sqlite3

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from pixel_nonograms.core import CellState, Difficulty, GameSession, HelperItemId, Puzzle
from pixel_nonograms.importer import read_puzzle, write_puzzle
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.persistence.database import OutOfStockError
from pixel_nonograms.services import InventoryService, built_in_puzzles
from pixel_nonograms.ui.collection_screen import PuzzleCard
from pixel_nonograms.ui.game_screen import GameScreen


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


def test_builtin_rewards_are_fixed_and_cover_each_aid_once():
    rewards = [
        entry.reward_item_id for entry in built_in_puzzles()
        if entry.reward_item_id is not None
    ]
    assert set(rewards) == set(HelperItemId)
    assert len(rewards) == len(set(rewards))


def test_reward_claimed_once_after_first_completion_and_survives_restart(tmp_path):
    path = tmp_path / "progress.sqlite3"
    database = Database(path)
    manager = SaveManager(database)
    item = HelperItemId.LOGIC_HINT
    source, session = grant(manager, item)
    assert database.reward_claimed(source.id)
    assert database.item_count(item) == 1
    assert manager.save(session)
    assert database.item_count(item) == 1
    session.undo()
    assert manager.save(session)
    session.redo()
    assert manager.save(session)
    assert database.item_count(item) == 1
    database.close()
    database = Database(path)
    assert database.reward_claimed(source.id)
    assert database.item_count(item) == 1
    assert SaveManager(database).save(SaveManager(database).load(source))
    assert database.item_count(item) == 1
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
    assert not database.reward_claimed("old")
    database.close()


@pytest.mark.parametrize(
    "item_id,axis,line_index,expected",
    [
        (HelperItemId.ANALYSIS_LENS, "row", 0, "olası yerleşim"),
        (HelperItemId.LOGIC_HINT, None, None, "satır ipuçlarına bak"),
        (HelperItemId.ROW_SCANNER, None, 0, "kesin hücreler"),
        (HelperItemId.COLUMN_SCANNER, None, 1, "kesin hücreler"),
        (HelperItemId.ERROR_CHECK, None, None, "uyuşmuyor"),
        (HelperItemId.SECOND_LOOK, None, None, "çelişiyor"),
    ],
)
def test_each_aid_consumes_one_and_saves_hint_count(tmp_path, item_id, axis, line_index, expected):
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    inventory = InventoryService(database, manager)
    source, _ = grant(manager, item_id)
    session = target()
    if item_id in {HelperItemId.ERROR_CHECK, HelperItemId.SECOND_LOOK}:
        session.mark_empty(0, 0)
    result = inventory.use(item_id, session, axis=axis, line_index=line_index)
    assert result is not None
    assert result.item_id is item_id
    assert expected in result.message
    assert inventory.counts()[item_id] == 0
    assert session.hint_count == 1
    assert manager.load(session.puzzle).hint_count == 1
    assert manager.save(manager.load(source))
    assert database.item_count(item_id) == 0
    if item_id in {HelperItemId.ROW_SCANNER, HelperItemId.COLUMN_SCANNER}:
        assert result.cells
        assert all(mark.state is CellState.FILLED for _, _, mark in result.cells)
        assert all(session.cell_at(x, y).state is CellState.UNKNOWN for x, y, _ in result.cells)
    database.close()


def test_no_useful_result_or_no_stock_does_not_consume(tmp_path):
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    inventory = InventoryService(database, manager)
    grant(manager, HelperItemId.SECOND_LOOK)
    session = target()
    assert inventory.use(HelperItemId.SECOND_LOOK, session) is None
    assert session.hint_count == 0
    assert database.item_count(HelperItemId.SECOND_LOOK) == 1
    with pytest.raises(OutOfStockError):
        inventory.use(HelperItemId.LOGIC_HINT, session)
    assert manager.load(session.puzzle) is None
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
        inventory.use(HelperItemId.LOGIC_HINT, session)
    assert session.hint_count == 0
    assert database.item_count(HelperItemId.LOGIC_HINT) == 1
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


def test_game_screen_can_use_aid_without_changing_grid(tmp_path):
    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    inventory = InventoryService(database, manager)
    grant(manager, HelperItemId.LOGIC_HINT)
    session = target()
    screen = GameScreen(
        session,
        settings=QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
        save_manager=manager,
        inventory=inventory,
    )
    screen.show()
    app.processEvents()
    toolbar = screen.inventory_toolbar
    toolbar.item_buttons[HelperItemId.LOGIC_HINT].click()
    assert toolbar.use_button.isEnabled()
    toolbar.use_button.click()
    assert "1/3" in toolbar.message_label.text()
    assert screen.board._hint_row == 0
    assert screen.board._hint_cell is None
    assert toolbar.next_hint_button.isEnabled()
    toolbar.item_buttons[HelperItemId.ERROR_CHECK].click()
    assert screen.board._hint_row is None
    toolbar.item_buttons[HelperItemId.LOGIC_HINT].click()
    assert "1/3" in toolbar.message_label.text()
    assert screen.board._hint_row == 0
    toolbar.next_hint_button.click()
    assert "2/3" in toolbar.message_label.text()
    assert "blok" in toolbar.message_label.text()
    assert inventory.counts()[HelperItemId.LOGIC_HINT] == 0
    assert session.hint_count == 1
    toolbar.next_hint_button.click()
    assert "3/3" in toolbar.message_label.text()
    assert screen.board._hint_cell == (0, 0)
    assert session.hint_count == 1
    assert all(mark.state is CellState.UNKNOWN for row in session.cells for mark in row)
    assert not toolbar.use_button.isEnabled()
    assert not toolbar.next_hint_button.isVisible()
    screen.close()
    database.close()


def test_hint_chain_closes_after_board_change(tmp_path):
    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    inventory = InventoryService(database, manager)
    grant(manager, HelperItemId.LOGIC_HINT)
    session = target()
    screen = GameScreen(
        session,
        settings=QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
        save_manager=manager,
        inventory=inventory,
    )
    screen.show()
    app.processEvents()
    toolbar = screen.inventory_toolbar
    toolbar.item_buttons[HelperItemId.LOGIC_HINT].click()
    toolbar.use_button.click()
    assert screen._active_hint_plan is not None
    session.mark_empty(2, 2)
    screen.board.refresh_session()
    assert screen._active_hint_plan is None
    assert not toolbar.next_hint_button.isVisible()
    assert screen.board._hint_row is None
    assert inventory.counts()[HelperItemId.LOGIC_HINT] == 0
    screen.close()
    database.close()


def test_logic_hint_without_forced_move_keeps_item(tmp_path):
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    inventory = InventoryService(database, manager)
    grant(manager, HelperItemId.LOGIC_HINT)
    ambiguous = GameSession(puzzle("ambiguous", ((1, 0), (0, 1))))
    assert inventory.use(HelperItemId.LOGIC_HINT, ambiguous) is None
    assert ambiguous.hint_count == 0
    assert database.item_count(HelperItemId.LOGIC_HINT) == 1
    database.close()


def test_game_screen_targeted_aid_waits_for_explicit_line(tmp_path):
    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    inventory = InventoryService(database, manager)
    grant(manager, HelperItemId.ROW_SCANNER)
    session = target()
    screen = GameScreen(
        session,
        settings=QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
        save_manager=manager,
        inventory=inventory,
    )
    screen.show()
    app.processEvents()
    toolbar = screen.inventory_toolbar
    toolbar.item_buttons[HelperItemId.ROW_SCANNER].click()
    assert not toolbar.use_button.isEnabled()
    assert inventory.counts()[HelperItemId.ROW_SCANNER] == 1
    toolbar.line_box.setCurrentIndex(1)
    assert toolbar.target_label.text() == "Hedef: 1. satır"
    toolbar.use_button.click()
    assert "kesin hücreler" in toolbar.message_label.text()
    assert inventory.counts()[HelperItemId.ROW_SCANNER] == 0
    assert session.hint_count == 1
    assert toolbar.target_label.text() == "Hedef: seçilmedi"
    screen.close()
    database.close()


def test_collection_card_shows_reward_and_claim_state(tmp_path):
    app = QApplication.instance() or QApplication([])
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    source = puzzle("card-reward", ((1,),), reward=HelperItemId.LOGIC_HINT)
    from pixel_nonograms.services import PuzzleLibrary

    library = PuzzleLibrary((source,), manager, database)
    card = PuzzleCard(library.entries()[0])
    assert "İlk tamamlama ödülü" in card.reward_label.text()
    card.close()
    grant_source = GameSession(source)
    grant_source.fill_cell(0, 0)
    assert manager.save(grant_source)
    card = PuzzleCard(library.entries()[0])
    assert "Ödül alındı" in card.reward_label.text()
    card.close()
    app.processEvents()
    database.close()
