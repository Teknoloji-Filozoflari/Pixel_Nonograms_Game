"""Versioned, transactional SQLite schema changes."""

import sqlite3
from collections.abc import Callable

SCHEMA_VERSION = 8


class UnsupportedDatabaseVersion(ValueError):
    pass


def _upgrade_to_v1(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE progress (
            puzzle_id TEXT PRIMARY KEY,
            puzzle_revision INTEGER NOT NULL CHECK (puzzle_revision >= 1),
            puzzle_fingerprint TEXT NOT NULL,
            state_version INTEGER NOT NULL CHECK (state_version = 1),
            width INTEGER NOT NULL CHECK (width BETWEEN 1 AND 100),
            height INTEGER NOT NULL CHECK (height BETWEEN 1 AND 100),
            grid_state BLOB NOT NULL,
            elapsed_ms INTEGER NOT NULL CHECK (elapsed_ms >= 0),
            move_count INTEGER NOT NULL CHECK (move_count >= 0),
            mistakes INTEGER NOT NULL CHECK (mistakes >= 0),
            hints_used INTEGER NOT NULL CHECK (hints_used >= 0),
            started TEXT NOT NULL,
            completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
            last_played TEXT NOT NULL,
            saved_at TEXT NOT NULL
        )
    """)


def _upgrade_to_v2(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE favorites (
            puzzle_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL
        )
    """)


def _upgrade_to_v3(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE inventory (
            item_id TEXT PRIMARY KEY,
            quantity INTEGER NOT NULL CHECK (quantity >= 0)
        )
    """)
    connection.execute("""
        CREATE TABLE reward_claims (
            puzzle_id TEXT PRIMARY KEY,
            item_id TEXT NOT NULL,
            claimed_at TEXT NOT NULL
        )
    """)


def _upgrade_to_v4(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE progress ADD COLUMN crossed_clues TEXT NOT NULL DEFAULT '[]'")


def _upgrade_to_v5(connection: sqlite3.Connection) -> None:
    # Rebuild only progress to widen its state-version constraint. All old rows
    # retain their original bytes; the surrounding migration is transactional.
    connection.execute("""
        CREATE TABLE progress_v5 (
            puzzle_id TEXT PRIMARY KEY,
            puzzle_revision INTEGER NOT NULL CHECK (puzzle_revision >= 1),
            puzzle_fingerprint TEXT NOT NULL,
            state_version INTEGER NOT NULL CHECK (state_version IN (1, 2)),
            width INTEGER NOT NULL CHECK (width BETWEEN 1 AND 100),
            height INTEGER NOT NULL CHECK (height BETWEEN 1 AND 100),
            grid_state BLOB NOT NULL,
            elapsed_ms INTEGER NOT NULL CHECK (elapsed_ms >= 0),
            move_count INTEGER NOT NULL CHECK (move_count >= 0),
            mistakes INTEGER NOT NULL CHECK (mistakes >= 0),
            hints_used INTEGER NOT NULL CHECK (hints_used >= 0),
            started TEXT NOT NULL,
            completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
            last_played TEXT NOT NULL,
            saved_at TEXT NOT NULL,
            crossed_clues TEXT NOT NULL DEFAULT '[]'
        )
    """)
    connection.execute("INSERT INTO progress_v5 SELECT * FROM progress")
    connection.execute("DROP TABLE progress")
    connection.execute("ALTER TABLE progress_v5 RENAME TO progress")


def _upgrade_to_v6(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE completions (
            puzzle_id TEXT PRIMARY KEY,
            colored INTEGER NOT NULL CHECK (colored IN (0, 1)),
            completed_at TEXT NOT NULL
        )
    """)
    connection.execute("""
        INSERT INTO completions SELECT puzzle_id, 0, saved_at
        FROM progress WHERE completed = 1
    """)
    connection.execute("""
        INSERT OR IGNORE INTO completions
        SELECT puzzle_id, 0, claimed_at FROM reward_claims
    """)
    connection.execute("""
        CREATE TABLE milestone_claims (
            mission_id TEXT PRIMARY KEY, claimed_at TEXT NOT NULL
        )
    """)
    connection.execute("""
        CREATE TABLE player_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            badge_id TEXT REFERENCES milestone_claims(mission_id)
        )
    """)
    connection.execute("INSERT INTO player_profile(id) VALUES (1)")


def _upgrade_to_v7(connection: sqlite3.Connection) -> None:
    # Rebuild only progress to widen its state-version constraint. All old rows
    # retain their original bytes; the surrounding migration is transactional.
    connection.execute("""
        CREATE TABLE progress_v7 (
            puzzle_id TEXT PRIMARY KEY,
            puzzle_revision INTEGER NOT NULL CHECK (puzzle_revision >= 1),
            puzzle_fingerprint TEXT NOT NULL,
            state_version INTEGER NOT NULL CHECK (state_version IN (1, 2, 3)),
            width INTEGER NOT NULL CHECK (width BETWEEN 1 AND 100),
            height INTEGER NOT NULL CHECK (height BETWEEN 1 AND 100),
            grid_state BLOB NOT NULL,
            elapsed_ms INTEGER NOT NULL CHECK (elapsed_ms >= 0),
            move_count INTEGER NOT NULL CHECK (move_count >= 0),
            mistakes INTEGER NOT NULL CHECK (mistakes >= 0),
            hints_used INTEGER NOT NULL CHECK (hints_used >= 0),
            started TEXT NOT NULL,
            completed INTEGER NOT NULL CHECK (completed IN (0, 1)),
            last_played TEXT NOT NULL,
            saved_at TEXT NOT NULL,
            crossed_clues TEXT NOT NULL DEFAULT '[]'
        )
    """)
    connection.execute("INSERT INTO progress_v7 SELECT * FROM progress")
    connection.execute("DROP TABLE progress")
    connection.execute("ALTER TABLE progress_v7 RENAME TO progress")


def _upgrade_to_v8(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE mission_reward_claims (
        mission_id TEXT PRIMARY KEY REFERENCES milestone_claims(mission_id),
        claimed_at TEXT NOT NULL
    )""")


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _upgrade_to_v1,
    2: _upgrade_to_v2,
    3: _upgrade_to_v3,
    4: _upgrade_to_v4,
    5: _upgrade_to_v5,
    6: _upgrade_to_v6,
    7: _upgrade_to_v7,
    8: _upgrade_to_v8,
}


def migrate(connection: sqlite3.Connection) -> None:
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version > SCHEMA_VERSION:
        raise UnsupportedDatabaseVersion(f"Veritabanı sürümü çok yeni: {version}")
    if version == 0:
        existing = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        if existing:
            raise UnsupportedDatabaseVersion(
                "Sürümü olmayan mevcut veritabanı otomatik değiştirilemez"
            )
    while version < SCHEMA_VERSION:
        target = version + 1
        upgrade = MIGRATIONS[target]
        connection.execute("BEGIN IMMEDIATE")
        try:
            upgrade(connection)
            connection.execute(f"PRAGMA user_version = {target}")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        version = target
