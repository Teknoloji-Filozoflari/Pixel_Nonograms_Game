"""Validate and serialize committed GameSession snapshots."""

import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone

from pixel_nonograms.core import CellMark, CellState, GameSession, Puzzle, SessionSnapshot
from pixel_nonograms.core.commands import NOTE_SYMBOLS
from pixel_nonograms.core.compact import compact_puzzle
from pixel_nonograms.core.items import HelperItemId

from .database import Database, ProgressRecord

STATE_VERSION = 3
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
            grid.extend(
                (
                    _STATE_TO_CODE[mark.state], mark.color_id,
                    (NOTE_SYMBOLS.index(mark.note_symbol) + 1) if mark.note else 0,
                    mark.auto_sources,
                )
            )
    return bytes(grid)


def _decode_grid(
    data: bytes, puzzle: Puzzle, version: int = STATE_VERSION
) -> tuple[tuple[CellMark, ...], ...]:
    stride = 2 if version == 1 else 4
    if type(data) is not bytes or len(data) != puzzle.width * puzzle.height * stride:
        raise ValueError("Kayıt ızgarasının boyutu geçersiz")
    cells = []
    for y in range(puzzle.height):
        row = []
        for x in range(puzzle.width):
            index = stride * (y * puzzle.width + x)
            state = _CODE_TO_STATE.get(data[index])
            color_id = data[index + 1]
            if state is None or (state is CellState.FILLED and color_id > len(puzzle.palette)):
                raise ValueError("Kayıt ızgarasında geçersiz hücre var")
            try:
                note = data[index + 2] if version >= 2 else 0
                sources = data[index + 3] if version >= 2 else 0
                if not 0 <= note <= (len(NOTE_SYMBOLS) if version == 3 else 1):
                    raise ValueError("Geçersiz kalem notu")
                row.append(CellMark(
                    state, color_id, bool(note), sources, NOTE_SYMBOLS[note - 1] if note else ""
                ))
            except ValueError as exc:
                raise ValueError("Kayıt ızgarasında geçersiz hücre var") from exc
        cells.append(tuple(row))
    return tuple(cells)


class SaveManager:
    def __init__(self, database: Database) -> None:
        self.database = database
        self._originals: dict[str, Puzzle] = {}

    def register_original(self, puzzle: Puzzle) -> None:
        self._originals[puzzle.id] = puzzle

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
            record, reward_item_id=puzzle.reward_item_id, consume_item_id=consume_item_id,
            colored=len(puzzle.palette) > 1,
        )
        return True

    def load(self, puzzle: Puzzle) -> GameSession | None:
        if type(puzzle) is not Puzzle:
            raise TypeError("Puzzle gerekli")
        record = self.database.load_progress(puzzle.id)
        if record is None:
            return None
        if (
            record.state_version not in (1, 2, STATE_VERSION)
            or record.puzzle_revision != puzzle.metadata.revision
            or record.puzzle_fingerprint != _fingerprint(puzzle)
            or record.width != puzzle.width
            or record.height != puzzle.height
        ):
            if "packaged-grid" in puzzle.tags:
                # Earlier releases removed empty lines from bundled boards. Restore
                # those coordinates while keeping every saved mark and clue crossing.
                legacy_source = replace(puzzle, tags=tuple(t for t in puzzle.tags if t != "packaged-grid"))
                compact, rows, columns = compact_puzzle(legacy_source)
                if record.puzzle_fingerprint == _fingerprint(compact):
                    snapshot = SaveManager(self.database).load(compact).snapshot()
                    cells = [[CellMark(CellState.UNKNOWN) for _ in range(puzzle.width)]
                             for _ in range(puzzle.height)]
                    for y, old_y in enumerate(rows):
                        for x, old_x in enumerate(columns):
                            cells[old_y][old_x] = snapshot.cells[y][x]
                    return GameSession.from_snapshot(puzzle, replace(
                        snapshot, cells=tuple(tuple(row) for row in cells),
                        crossed_clues=tuple(
                            (axis, (rows if axis == "row" else columns)[line], clue)
                            for axis, line, clue in snapshot.crossed_clues
                            if (compact.row_clues[line] if axis == "row" else compact.column_clues[line])
                            == (puzzle.row_clues[rows[line]] if axis == "row"
                                else puzzle.column_clues[columns[line]])
                        ),
                    ))
            original = self._originals.get(puzzle.id)
            if original is None or record.puzzle_fingerprint != _fingerprint(original):
                raise ValueError("Kayıt bu bulmaca sürümüyle eşleşmiyor")
            compact, rows, columns = compact_puzzle(original)
            if _fingerprint(compact) != _fingerprint(puzzle):
                raise ValueError("Kayıt bu bulmaca sürümüyle eşleşmiyor")
            # Validate the complete legacy snapshot before remapping any coordinates.
            legacy_manager = SaveManager(self.database)
            legacy = legacy_manager.load(original)
            snapshot = legacy.snapshot()
            row_map = {old: new for new, old in enumerate(rows)}
            col_map = {old: new for new, old in enumerate(columns)}
            snapshot = replace(
                snapshot,
                cells=tuple(tuple(snapshot.cells[y][x] for x in columns) for y in rows),
                crossed_clues=tuple(
                    (axis, (row_map if axis == "row" else col_map)[line], clue)
                    for axis, line, clue in snapshot.crossed_clues
                    if line in (row_map if axis == "row" else col_map)
                    and (original.row_clues[line] if axis == "row" else original.column_clues[line])
                    == (puzzle.row_clues[row_map[line]] if axis == "row"
                        else puzzle.column_clues[col_map[line]])
                ),
            )
            # Removing an incorrect fill in a clue-free line can finish a board.
            completed = all(
                (mark.color_id if mark.state is CellState.FILLED else 0) == puzzle.solution[y][x]
                for y, row in enumerate(snapshot.cells) for x, mark in enumerate(row)
            )
            return GameSession.from_snapshot(puzzle, replace(snapshot, completed=completed))
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
            cells=_decode_grid(record.grid_state, puzzle, record.state_version),
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
