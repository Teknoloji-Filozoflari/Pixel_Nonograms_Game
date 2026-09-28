"""Small SQLite access layer for puzzle progress."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pixel_nonograms.core.items import HelperItemId
from pixel_nonograms.core.progression import MISSION_REWARDS, MISSIONS, mission_count

from .migrations import SCHEMA_VERSION, migrate


class OutOfStockError(ValueError):
    """The selected aid is unavailable or has already been consumed."""


@dataclass(frozen=True, slots=True)
class ProgressRecord:
    puzzle_id: str
    puzzle_revision: int
    puzzle_fingerprint: str
    state_version: int
    width: int
    height: int
    grid_state: bytes
    elapsed_ms: int
    move_count: int
    mistakes: int
    hints_used: int
    started: str
    completed: bool
    last_played: str
    saved_at: str
    crossed_clues: str = "[]"


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path, timeout=5)
        try:
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA busy_timeout = 5000")
            self.connection.execute("PRAGMA foreign_keys = ON")
            self.connection.execute("PRAGMA journal_mode = WAL")
            version = self.connection.execute("PRAGMA user_version").fetchone()[0]
            if 0 < version < SCHEMA_VERSION:
                stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
                backup_path = self.path.with_name(f"{self.path.name}.v{version}.{stamp}.bak")
                with sqlite3.connect(backup_path) as backup:
                    self.connection.backup(backup)
            migrate(self.connection)
            with self.connection:
                self._award_milestones()
        except Exception:
            self.connection.close()
            raise

    def close(self) -> None:
        self.connection.close()

    def favorite_ids(self) -> frozenset[str]:
        rows = self.connection.execute("SELECT puzzle_id FROM favorites").fetchall()
        return frozenset(row[0] for row in rows)

    def set_favorite(self, puzzle_id: str, favorite: bool) -> None:
        if type(puzzle_id) is not str or not puzzle_id.strip():
            raise ValueError("Bulmaca kimliği gerekli")
        if type(favorite) is not bool:
            raise TypeError("Favori durumu bool olmalı")
        with self.connection:
            if favorite:
                self.connection.execute(
                    "INSERT OR IGNORE INTO favorites(puzzle_id, created_at) VALUES (?, ?)",
                    (puzzle_id, datetime.now(timezone.utc).isoformat()),
                )
            else:
                self.connection.execute("DELETE FROM favorites WHERE puzzle_id = ?", (puzzle_id,))

    def load_progress(self, puzzle_id: str) -> ProgressRecord | None:
        row = self.connection.execute(
            "SELECT * FROM progress WHERE puzzle_id = ?", (puzzle_id,)
        ).fetchone()
        if row is None:
            return None
        return ProgressRecord(
            puzzle_id=row["puzzle_id"],
            puzzle_revision=row["puzzle_revision"],
            puzzle_fingerprint=row["puzzle_fingerprint"],
            state_version=row["state_version"],
            width=row["width"],
            height=row["height"],
            grid_state=row["grid_state"],
            elapsed_ms=row["elapsed_ms"],
            move_count=row["move_count"],
            mistakes=row["mistakes"],
            hints_used=row["hints_used"],
            started=row["started"],
            completed=bool(row["completed"]),
            last_played=row["last_played"],
            saved_at=row["saved_at"],
            crossed_clues=row["crossed_clues"],
        )

    def item_count(self, item_id: HelperItemId) -> int:
        item_id = HelperItemId(item_id)
        row = self.connection.execute(
            "SELECT quantity FROM inventory WHERE item_id = ?", (item_id.value,)
        ).fetchone()
        return 0 if row is None else row[0]

    def inventory_counts(self) -> dict[HelperItemId, int]:
        return {item_id: self.item_count(item_id) for item_id in HelperItemId}

    def reward_claimed(self, puzzle_id: str) -> bool:
        return (
            self.connection.execute(
                "SELECT 1 FROM reward_claims WHERE puzzle_id = ?", (puzzle_id,)
            ).fetchone()
            is not None
        )

    def save_progress(
        self,
        record: ProgressRecord,
        *,
        reward_item_id: HelperItemId | None = None,
        consume_item_id: HelperItemId | None = None,
        colored: bool = False,
    ) -> None:
        if reward_item_id is not None:
            reward_item_id = HelperItemId(reward_item_id)
        if consume_item_id is not None:
            consume_item_id = HelperItemId(consume_item_id)
        with self.connection:
            if consume_item_id is not None:
                changed = self.connection.execute(
                    "UPDATE inventory SET quantity = quantity - 1 "
                    "WHERE item_id = ? AND quantity > 0",
                    (consume_item_id.value,),
                ).rowcount
                if changed != 1:
                    raise OutOfStockError("Yardımcı öğe envanterde yok")
            self.connection.execute(
                """
                INSERT INTO progress (
                    puzzle_id, puzzle_revision, puzzle_fingerprint, state_version,
                    width, height, grid_state, elapsed_ms, move_count, mistakes,
                    hints_used, started, completed, last_played, saved_at, crossed_clues
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(puzzle_id) DO UPDATE SET
                    puzzle_revision=excluded.puzzle_revision,
                    puzzle_fingerprint=excluded.puzzle_fingerprint,
                    state_version=excluded.state_version,
                    width=excluded.width,
                    height=excluded.height,
                    grid_state=excluded.grid_state,
                    elapsed_ms=excluded.elapsed_ms,
                    move_count=excluded.move_count,
                    mistakes=excluded.mistakes,
                    hints_used=excluded.hints_used,
                    started=excluded.started,
                    completed=excluded.completed,
                    last_played=excluded.last_played,
                    saved_at=excluded.saved_at,
                    crossed_clues=excluded.crossed_clues
                """,
                (
                    record.puzzle_id,
                    record.puzzle_revision,
                    record.puzzle_fingerprint,
                    record.state_version,
                    record.width,
                    record.height,
                    record.grid_state,
                    record.elapsed_ms,
                    record.move_count,
                    record.mistakes,
                    record.hints_used,
                    record.started,
                    int(record.completed),
                    record.last_played,
                    record.saved_at,
                    record.crossed_clues,
                ),
            )
            if record.completed:
                self.connection.execute(
                    "INSERT INTO completions VALUES (?, ?, ?) "
                    "ON CONFLICT(puzzle_id) DO UPDATE SET colored = MAX(colored, excluded.colored)",
                    (record.puzzle_id, int(colored), record.saved_at),
                )
                self._award_milestones()
            if record.completed and reward_item_id is not None:
                claimed = self.connection.execute(
                    "INSERT OR IGNORE INTO reward_claims(puzzle_id, item_id, claimed_at) "
                    "VALUES (?, ?, ?)",
                    (record.puzzle_id, reward_item_id.value, record.saved_at),
                ).rowcount
                if claimed:
                    self.connection.execute(
                        "INSERT INTO inventory(item_id, quantity) VALUES (?, 1) "
                        "ON CONFLICT(item_id) DO UPDATE SET quantity = quantity + 1",
                        (reward_item_id.value,),
                    )

    def completion_history(self) -> dict[str, bool]:
        return {row[0]: bool(row[1]) for row in self.connection.execute(
            "SELECT puzzle_id, colored FROM completions"
        )}

    def milestone_ids(self) -> frozenset[str]:
        return frozenset(row[0] for row in self.connection.execute(
            "SELECT mission_id FROM milestone_claims"
        ))

    def _award_milestones(self) -> None:
        history = self.completion_history()
        for mission in MISSIONS:
            if mission_count(mission, history) >= mission.target:
                self.connection.execute(
                    "INSERT OR IGNORE INTO milestone_claims VALUES (?, ?)",
                    (mission.id, datetime.now(timezone.utc).isoformat()),
                )

        for mission_id in self.milestone_ids():
            pack = MISSION_REWARDS.get(mission_id, ())
            if not pack:
                continue
            claimed = self.connection.execute(
                "INSERT OR IGNORE INTO mission_reward_claims VALUES (?, ?)",
                (mission_id, datetime.now(timezone.utc).isoformat()),
            ).rowcount
            if claimed:
                for item, quantity in pack:
                    self.connection.execute(
                        "INSERT INTO inventory VALUES (?, ?) "
                        "ON CONFLICT(item_id) DO UPDATE SET quantity = quantity + excluded.quantity",
                        (item, quantity),
                    )

    def grant_missing_puzzle_rewards(self, puzzles) -> None:
        """Backfill only recorded completions; existing claims remain authoritative."""
        history = self.completion_history()
        with self.connection:
            for puzzle in puzzles:
                if puzzle.id not in history:
                    continue
                item = puzzle.reward_item_id or HelperItemId.LOGIC_HINT
                changed = self.connection.execute(
                    "INSERT OR IGNORE INTO reward_claims VALUES (?, ?, ?)",
                    (puzzle.id, item.value, datetime.now(timezone.utc).isoformat()),
                ).rowcount
                if changed:
                    self.connection.execute(
                        "INSERT INTO inventory VALUES (?, 1) "
                        "ON CONFLICT(item_id) DO UPDATE SET quantity = quantity + 1", (item.value,)
                    )

    def selected_badge(self) -> str | None:
        return self.connection.execute(
            "SELECT badge_id FROM player_profile WHERE id = 1"
        ).fetchone()[0]

    def select_badge(self, badge_id: str | None) -> None:
        if badge_id is not None and badge_id not in self.milestone_ids():
            raise ValueError("Bu rozet henüz açılmadı")
        with self.connection:
            self.connection.execute(
                "UPDATE player_profile SET badge_id = ? WHERE id = 1", (badge_id,)
            )

    def mark_completed_color(self, puzzle_id: str) -> None:
        # Used only for validated old saves whose palette was not stored in v5.
        with self.connection:
            self.connection.execute(
                "UPDATE completions SET colored = 1 WHERE puzzle_id = ?", (puzzle_id,)
            )
            self._award_milestones()
