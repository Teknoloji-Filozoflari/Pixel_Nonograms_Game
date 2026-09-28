"""Persistence tests use real SQLite files in temporary directories."""

import sqlite3
from datetime import timedelta

import pytest

from pixel_nonograms.core import CellMark, CellState, Difficulty, GameSession, Puzzle
from pixel_nonograms.persistence import Database, SaveManager, migrations
from pixel_nonograms.persistence.migrations import UnsupportedDatabaseVersion


def puzzle_for(solution, *, puzzle_id="save-test", palette=("#112233",)):
    return Puzzle(
        id=puzzle_id,
        title="Kayıt",
        author="Test",
        description="",
        width=len(solution[0]),
        height=len(solution),
        difficulty=Difficulty.EASY,
        tags=(),
        palette=palette,
        solution=solution,
    )


def test_database_initial_migration_and_reopen(tmp_path):
    path = tmp_path / "nested" / "progress.sqlite3"
    database = Database(path)
    assert path.is_file()
    assert database.connection.execute("PRAGMA user_version").fetchone()[0] == 8
    columns = {
        row[1] for row in database.connection.execute("PRAGMA table_info(progress)").fetchall()
    }
    assert {
        "puzzle_id",
        "grid_state",
        "elapsed_ms",
        "move_count",
        "mistakes",
        "hints_used",
        "started",
        "completed",
        "last_played",
    } <= columns
    assert (
        database.connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'favorites'"
        ).fetchone()
        is not None
    )
    database.close()
    reopened = Database(path)
    assert reopened.connection.execute("PRAGMA user_version").fetchone()[0] == 8
    reopened.close()


def test_v1_database_upgrades_with_backup_and_favorites_persist(tmp_path):
    path = tmp_path / "v1.sqlite3"
    connection = sqlite3.connect(path)
    migrations.MIGRATIONS[1](connection)
    connection.execute("PRAGMA user_version = 1")
    connection.execute(
        """INSERT INTO progress VALUES (
            'legacy', 1, 'old-fingerprint', 1, 1, 1, x'0000',
            25, 0, 0, 0, '2026-01-01T00:00:00+00:00', 0,
            '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00'
        )"""
    )
    connection.commit()
    connection.close()
    database = Database(path)
    assert database.connection.execute("PRAGMA user_version").fetchone()[0] == 8
    assert database.load_progress("legacy").elapsed_ms == 25
    backups = list(tmp_path.glob("v1.sqlite3.v1.*.bak"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as backup:
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 1
    database.set_favorite("one", True)
    database.set_favorite("one", True)
    assert database.favorite_ids() == frozenset({"one"})
    database.close()
    database = Database(path)
    assert database.favorite_ids() == frozenset({"one"})
    database.set_favorite("one", False)
    assert database.favorite_ids() == frozenset()
    database.close()


def test_v2_database_upgrades_inventory_without_losing_favorites(tmp_path):
    path = tmp_path / "v2.sqlite3"
    connection = sqlite3.connect(path)
    migrations.MIGRATIONS[1](connection)
    migrations.MIGRATIONS[2](connection)
    connection.execute("PRAGMA user_version = 2")
    connection.execute(
        "INSERT INTO favorites(puzzle_id, created_at) VALUES ('saved', '2026-01-01T00:00:00+00:00')"
    )
    connection.commit()
    connection.close()
    database = Database(path)
    assert database.connection.execute("PRAGMA user_version").fetchone()[0] == 8
    assert database.favorite_ids() == frozenset({"saved"})
    assert database.connection.execute("SELECT count(*) FROM inventory").fetchone()[0] == 0
    assert len(list(tmp_path.glob("v2.sqlite3.v2.*.bak"))) == 1
    database.close()


def test_rejects_future_and_unversioned_existing_database(tmp_path):
    future_path = tmp_path / "future.sqlite3"
    connection = sqlite3.connect(future_path)
    connection.execute("PRAGMA user_version = 99")
    connection.close()
    with pytest.raises(UnsupportedDatabaseVersion, match="çok yeni"):
        Database(future_path)

    unknown_path = tmp_path / "unknown.sqlite3"
    connection = sqlite3.connect(unknown_path)
    connection.execute("CREATE TABLE progress (unexpected TEXT)")
    connection.close()
    with pytest.raises(UnsupportedDatabaseVersion, match="Sürümü olmayan"):
        Database(unknown_path)
    connection = sqlite3.connect(unknown_path)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    connection.close()


def test_failed_migration_rolls_back_schema_and_version(tmp_path, monkeypatch):
    path = tmp_path / "failed.sqlite3"

    def broken_upgrade(connection):
        connection.execute("CREATE TABLE partial (id INTEGER)")
        raise RuntimeError("migration failed")

    monkeypatch.setitem(migrations.MIGRATIONS, 1, broken_upgrade)
    with pytest.raises(RuntimeError, match="migration failed"):
        Database(path)
    connection = sqlite3.connect(path)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    assert (
        connection.execute("SELECT name FROM sqlite_master WHERE name = 'partial'").fetchone()
        is None
    )
    connection.close()


def test_roundtrip_two_puzzles_and_statistics(tmp_path):
    path = tmp_path / "progress.sqlite3"
    database = Database(path)
    manager = SaveManager(database)
    first = puzzle_for(((1, 0), (0, 2)), palette=("#112233", "#445566"))
    second = puzzle_for(((1,),), puzzle_id="second")
    session = GameSession(first)
    session.fill_cell(0, 0, 1)
    session.mark_empty(1, 0)
    session.fill_cell(1, 1, 1)  # Mistake and color information must survive the roundtrip.
    session.record_hint()
    session.pause()
    snapshot = session.snapshot()
    assert manager.save(session)
    another = GameSession(second)
    another.fill_cell(0, 0)
    assert manager.save(another)
    assert manager.load(puzzle_for(((0,),), puzzle_id="missing")) is None
    database.close()

    database = Database(path)
    manager = SaveManager(database)
    restored = manager.load(first)
    assert restored.cells == session.cells
    assert restored.move_count == 3
    assert restored.mistake_count == 1
    assert restored.hint_count == 1
    assert restored.started_at == snapshot.started_at
    assert restored.last_played_at == snapshot.last_played_at
    assert abs(restored.elapsed_time - snapshot.elapsed_time) < 0.02
    assert not restored.can_undo and not restored.can_redo
    assert manager.load(second).completed
    database.close()


def test_manual_clue_marks_survive_save_and_reload(tmp_path):
    database = Database(tmp_path / "clues.sqlite3")
    manager = SaveManager(database)
    puzzle = puzzle_for(((1, 0, 1), (0, 1, 0)))
    session = GameSession(puzzle)
    session.toggle_clue("row", 0, 0)
    session.toggle_clue("column", 1, 0)
    assert manager.save(session)
    restored = manager.load(puzzle)
    assert restored.is_clue_crossed("row", 0, 0)
    assert restored.is_clue_crossed("column", 1, 0)
    assert not restored.is_clue_crossed("row", 0, 1)
    database.close()


def test_completed_record_keeps_frozen_elapsed_time(tmp_path):
    database = Database(tmp_path / "completed.sqlite3")
    manager = SaveManager(database)
    puzzle = puzzle_for(((1,),))
    session = GameSession(puzzle)
    session.fill_cell(0, 0)
    elapsed = session.elapsed_time
    assert manager.save(session)
    restored = manager.load(puzzle)
    assert restored.completed
    assert restored.elapsed_time == pytest.approx(elapsed, abs=0.002)
    database.close()


def test_trial_is_not_saved_and_active_stroke_is_deferred(tmp_path):
    database = Database(tmp_path / "trial.sqlite3")
    manager = SaveManager(database)
    puzzle = puzzle_for(((1, 1),))
    session = GameSession(puzzle)
    session.fill_cell(0, 0)
    session.begin_assumption()
    session.fill_cell(1, 0)
    assert manager.save(session)
    restored = manager.load(puzzle)
    assert restored.cells == ((CellMark(CellState.FILLED, 1), CellMark()),)
    assert not restored.assumption_active
    session.cancel_assumption()
    session.begin_stroke()
    session.fill_cell(1, 0)
    assert not manager.save(session)
    assert manager.load(puzzle).cells == restored.cells
    session.end_stroke()
    assert manager.save(session)
    assert manager.load(puzzle).completed
    database.close()


def test_corrupt_grid_or_changed_puzzle_is_rejected_without_overwrite(tmp_path):
    database = Database(tmp_path / "invalid.sqlite3")
    manager = SaveManager(database)
    puzzle = puzzle_for(((1, 0),))
    session = GameSession(puzzle)
    session.fill_cell(0, 0)
    manager.save(session)
    with pytest.raises(ValueError, match="eşleşmiyor"):
        manager.load(puzzle_for(((0, 1),)))
    database.connection.execute(
        "UPDATE progress SET grid_state = ? WHERE puzzle_id = ?",
        (bytes((9, 0, 0, 0, 0, 0, 0, 0)), puzzle.id),
    )
    database.connection.commit()
    with pytest.raises(ValueError, match="geçersiz hücre"):
        manager.load(puzzle)
    row = database.load_progress(puzzle.id)
    assert row.grid_state == bytes((9, 0, 0, 0, 0, 0, 0, 0))
    database.close()


def test_invalid_session_snapshot_does_not_restore(tmp_path):
    database = Database(tmp_path / "invalid_snapshot.sqlite3")
    manager = SaveManager(database)
    puzzle = puzzle_for(((1,),))
    session = GameSession(puzzle)
    manager.save(session)
    database.connection.execute(
        "UPDATE progress SET completed = 1 WHERE puzzle_id = ?", (puzzle.id,)
    )
    database.connection.commit()
    with pytest.raises(ValueError, match="tamamlanma"):
        manager.load(puzzle)
    database.connection.execute(
        "UPDATE progress SET completed = 0, last_played = ? WHERE puzzle_id = ?",
        ((session.started_at - timedelta(days=1)).isoformat(), puzzle.id),
    )
    database.connection.commit()
    with pytest.raises(ValueError, match="tarih"):
        manager.load(puzzle)
    database.close()


def test_notes_and_x_sources_roundtrip_and_legacy_v4_upgrade(tmp_path):
    from pixel_nonograms.persistence.save_manager import _fingerprint

    path = tmp_path / "v4.sqlite3"
    puzzle = puzzle_for(((1, 0), (0, 1)))
    connection = sqlite3.connect(path)
    for version in range(1, 5):
        migrations.MIGRATIONS[version](connection)
    connection.execute("PRAGMA user_version = 4")
    connection.execute(
        """INSERT INTO progress VALUES (
        ?, 1, ?, 1, 2, 2, ?, 100, 1, 0, 0,
        '2026-01-01T00:00:00+00:00', 0, '2026-01-01T00:00:00+00:00',
        '2026-01-01T00:00:00+00:00', '[["row",0,0]]')""",
        (puzzle.id, _fingerprint(puzzle), bytes((0, 0, 2, 0, 0, 0, 0, 0))),
    )
    connection.commit()
    connection.close()
    db = Database(path)
    assert len(list(tmp_path.glob("v4.sqlite3.v4.*.bak"))) == 1
    manager = SaveManager(db)
    legacy = manager.load(puzzle)
    assert legacy.cell_at(1, 0).auto_sources == 0
    legacy.toggle_clue("row", 0, 0)
    assert legacy.cell_at(1, 0).state is CellState.EMPTY
    legacy.mark_note(0, 0)
    legacy.toggle_clue("row", 1, 0)
    manager.save(legacy)
    assert db.load_progress(puzzle.id).state_version == 3
    restored = manager.load(puzzle)
    assert restored.cells == legacy.cells
    restored.toggle_clue("row", 1, 0)
    assert restored.cell_at(0, 1).state is CellState.UNKNOWN
    assert restored.cell_at(0, 0).note
    db.close()


@pytest.mark.parametrize("cell", [(0, 0, 2, 0), (0, 0, 0, 8), (1, 1, 1, 0), (1, 1, 0, 1)])
def test_invalid_v2_cell_metadata_is_rejected(tmp_path, cell):
    db = Database(tmp_path / "bad-meta.sqlite3")
    manager = SaveManager(db)
    puzzle = puzzle_for(((1, 0),))
    manager.save(GameSession(puzzle))
    db.connection.execute("UPDATE progress SET grid_state = ?, state_version = 2", (bytes(cell + (0, 0, 0, 0)),))
    db.connection.commit()
    with pytest.raises(ValueError, match="geçersiz hücre"):
        manager.load(puzzle)
    db.close()
