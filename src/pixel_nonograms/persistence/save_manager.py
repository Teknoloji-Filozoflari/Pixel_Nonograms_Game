"""Validate and serialize committed GameSession snapshots."""

import hashlib
import json
from datetime import datetime, timezone

from pixel_nonograms.core import CellMark, CellState, GameSession, Puzzle, SessionSnapshot
from pixel_nonograms.core.items import HelperItemId

from .database import Database, ProgressRecord

STATE_VERSION = 1
_STATE_TO_CODE = {CellState.UNKNOWN: 0, CellState.FILLED: 1, CellState.EMPTY: 2}
_CODE_TO_STATE = {code: state for state, code in _STATE_TO_CODE.items()}


def _fingerprint(puzzle: Puzzle) -> str:
    payload = json.dumps(
        {
            "id": puzzle.id,
            "revision": puzzle.metadata.revision,
            "width": puzzle.width,
            "height": puzzle.height,
            "palette": puzzle.palette,
            "solution": puzzle.solution,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _encode_grid(cells: tuple[tuple[CellMark, ...], ...]) -> bytes:
    grid = bytearray()
    for row in cells:
        for mark in row:
            grid.extend((_STATE_TO_CODE[mark.state], mark.color_id))
    return bytes(grid)


def _decode_grid(data: bytes, puzzle: Puzzle) -> tuple[tuple[CellMark, ...], ...]:
    if type(data) is not bytes or len(data) != puzzle.width * puzzle.height * 2:
        raise ValueError("Kayıt ızgarasının boyutu geçersiz")
    cells = []
    for y in range(puzzle.height):
        row = []
        for x in range(puzzle.width):
            index = 2 * (y * puzzle.width + x)
            state = _CODE_TO_STATE.get(data[index])
            color_id = data[index + 1]
            if state is None or (state is CellState.FILLED and color_id > len(puzzle.palette)):
                raise ValueError("Kayıt ızgarasında geçersiz hücre var")
            try:
                row.append(CellMark(state, color_id))
            except ValueError as exc:
                raise ValueError("Kayıt ızgarasında geçersiz hücre var") from exc
        cells.append(tuple(row))
    return tuple(cells)


class SaveManager:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(self, session: GameSession, *, consume_item_id: HelperItemId | None = None) -> bool:
        """Save committed state; defer a snapshot while a drag is in progress."""
        if type(session) is not GameSession:
            raise TypeError("GameSession gerekli")
        try:
            snapshot = session.snapshot()
        except RuntimeError:
            return False
        puzzle = session.puzzle
        record = ProgressRecord(
            puzzle_id=puzzle.id,
            puzzle_revision=puzzle.metadata.revision,
            puzzle_fingerprint=_fingerprint(puzzle),
            state_version=STATE_VERSION,
            width=puzzle.width,
            height=puzzle.height,
            grid_state=_encode_grid(snapshot.cells),
            elapsed_ms=round(snapshot.elapsed_time * 1000),
            move_count=snapshot.move_count,
            mistakes=snapshot.mistake_count,
            hints_used=snapshot.hint_count,
            started=snapshot.started_at.astimezone(timezone.utc).isoformat(),
            completed=snapshot.completed,
            last_played=snapshot.last_played_at.astimezone(timezone.utc).isoformat(),
            saved_at=datetime.now(timezone.utc).isoformat(),
            crossed_clues=json.dumps(snapshot.crossed_clues, separators=(",", ":")),
        )
        self.database.save_progress(
            record, reward_item_id=puzzle.reward_item_id, consume_item_id=consume_item_id
        )
        return True

    def load(self, puzzle: Puzzle) -> GameSession | None:
        if type(puzzle) is not Puzzle:
            raise TypeError("Puzzle gerekli")
        record = self.database.load_progress(puzzle.id)
        if record is None:
            return None
        if (
            record.state_version != STATE_VERSION
            or record.puzzle_revision != puzzle.metadata.revision
            or record.puzzle_fingerprint != _fingerprint(puzzle)
            or record.width != puzzle.width
            or record.height != puzzle.height
        ):
            raise ValueError("Kayıt bu bulmaca sürümüyle eşleşmiyor")
        try:
            started = datetime.fromisoformat(record.started)
            last_played = datetime.fromisoformat(record.last_played)
        except ValueError as exc:
            raise ValueError("Kayıttaki tarih geçersiz") from exc
        try:
            raw_clues = json.loads(record.crossed_clues)
            if type(raw_clues) is not list or any(
                type(entry) is not list or len(entry) != 3 for entry in raw_clues
            ):
                raise ValueError
            crossed_clues = tuple(tuple(entry) for entry in raw_clues)
        except (TypeError, ValueError) as exc:
            raise ValueError("Kayıttaki ipucu işaretleri geçersiz") from exc
        snapshot = SessionSnapshot(
            cells=_decode_grid(record.grid_state, puzzle),
            elapsed_time=record.elapsed_ms / 1000,
            move_count=record.move_count,
            mistake_count=record.mistakes,
            hint_count=record.hints_used,
            started_at=started,
            last_played_at=last_played,
            completed=record.completed,
            crossed_clues=crossed_clues,
        )
        return GameSession.from_snapshot(puzzle, snapshot)
