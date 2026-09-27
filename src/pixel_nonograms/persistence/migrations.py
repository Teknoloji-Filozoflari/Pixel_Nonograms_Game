"""Versioned, transactional SQLite schema changes."""

import sqlite3
from collections.abc import Callable

SCHEMA_VERSION = 4


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


MIGRATIONS: dict[int, Callable[[sqlite3.Connection], None]] = {
    1: _upgrade_to_v1,
    2: _upgrade_to_v2,
    3: _upgrade_to_v3,
    4: _upgrade_to_v4,
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
