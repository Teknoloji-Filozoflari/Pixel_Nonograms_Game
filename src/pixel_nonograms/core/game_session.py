"""Player state and command history, without persistence or UI dependencies."""

from datetime import datetime, timezone
from math import isfinite
from time import monotonic

from .analysis import LineStatus, analyze_board
from .cell import CellState
from .commands import (
    CellChangeCommand,
    CellMark,
    ClueChangeCommand,
    Command,
    MultiCellChangeCommand,
)
from .puzzle import Puzzle
from .session_state import SessionSnapshot


class GameSession:
    def __init__(self, puzzle: Puzzle, *, auto_x_completed_lines: bool = False) -> None:
        if type(puzzle) is not Puzzle:
            raise TypeError("GameSession bir Puzzle gerektirir")
        if type(auto_x_completed_lines) is not bool:
            raise TypeError("Otomatik X ayarı bool olmalı")
        self.puzzle = puzzle
        self.auto_x_completed_lines = auto_x_completed_lines
        self._cells = [[CellMark() for _ in range(puzzle.width)] for _ in range(puzzle.height)]
        self._crossed_clues: set[tuple[str, int, int]] = set()
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._assumption_cells: tuple[tuple[CellMark, ...], ...] | None = None
        self._assumption_undo_stack: list[Command] = []
        self._assumption_redo_stack: list[Command] = []
        self._stroke: dict[tuple[int, int], CellChangeCommand] | None = None
        self.move_count = 0
        self.undo_count = 0
        self.redo_count = 0
        self.mistake_count = 0
        self.hint_count = 0
        self.started_at = datetime.now(timezone.utc)
        self.last_played_at = self.started_at
        self._elapsed_seconds = 0.0
        self._completed = self._is_solved()
        self._paused = False
        self._active_since = None if self._completed else monotonic()

    @property
    def cells(self) -> tuple[tuple[CellMark, ...], ...]:
        return tuple(tuple(row) for row in self._cells)

    def snapshot(self) -> SessionSnapshot:
        """Capture committed progress; a live assumption remains temporary."""
        self._require_no_stroke()
        return SessionSnapshot(
            cells=self._assumption_cells if self.assumption_active else self.cells,
            elapsed_time=self.elapsed_time,
            move_count=self.move_count,
            mistake_count=self.mistake_count,
            hint_count=self.hint_count,
            started_at=self.started_at,
            last_played_at=self.last_played_at,
            completed=self.completed,
            crossed_clues=tuple(sorted(self._crossed_clues)),
        )

    @classmethod
    def from_snapshot(cls, puzzle: Puzzle, snapshot: SessionSnapshot) -> "GameSession":
        """Restore progress without replaying moves or retaining undo history."""
        if type(snapshot) is not SessionSnapshot:
            raise TypeError("Geçerli oturum kaydı gerekli")
        if len(snapshot.cells) != puzzle.height or any(
            len(row) != puzzle.width for row in snapshot.cells
        ):
            raise ValueError("Kayıt tahtası bulmaca boyutuyla eşleşmiyor")
        if any(
            type(mark) is not CellMark
            or (mark.state is CellState.FILLED and mark.color_id > len(puzzle.palette))
            for row in snapshot.cells
            for mark in row
        ):
            raise ValueError("Kayıtta geçersiz hücre var")
        if (
            type(snapshot.elapsed_time) not in (int, float)
            or not isfinite(snapshot.elapsed_time)
            or snapshot.elapsed_time < 0
        ):
            raise ValueError("Kayıtta geçersiz süre var")
        if any(
            type(value) is not int or value < 0
            for value in (snapshot.move_count, snapshot.mistake_count, snapshot.hint_count)
        ):
            raise ValueError("Kayıtta geçersiz sayaç var")
        if (
            any(
                not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None
                for value in (snapshot.started_at, snapshot.last_played_at)
            )
            or snapshot.last_played_at < snapshot.started_at
        ):
            raise ValueError("Kayıtta geçersiz tarih var")
        if type(snapshot.completed) is not bool:
            raise ValueError("Kayıtta geçersiz tamamlanma durumu var")
        if type(snapshot.crossed_clues) is not tuple or any(
            type(key) is not tuple
            or len(key) != 3
            or type(key[0]) is not str
            or type(key[1]) is not int
            or type(key[2]) is not int
            or key[0] not in {"row", "column"}
            or not 0 <= key[1] < (puzzle.height if key[0] == "row" else puzzle.width)
            or not 0 <= key[2] < len(
                puzzle.row_clues[key[1]] if key[0] == "row" else puzzle.column_clues[key[1]]
            )
            for key in snapshot.crossed_clues
        ) or len(set(snapshot.crossed_clues)) != len(snapshot.crossed_clues):
            raise ValueError("Kayıttaki ipucu işaretleri geçersiz")
        session = cls(puzzle)
        session._cells = [list(row) for row in snapshot.cells]
        session._crossed_clues = set(snapshot.crossed_clues)
        if session._is_solved() != snapshot.completed:
            raise ValueError("Kayıttaki tamamlanma durumu tahtayla eşleşmiyor")
        session._elapsed_seconds = float(snapshot.elapsed_time)
        session.move_count = snapshot.move_count
        session.mistake_count = snapshot.mistake_count
        session.hint_count = snapshot.hint_count
        session.started_at = snapshot.started_at
        session.last_played_at = snapshot.last_played_at
        session._completed = snapshot.completed
        session._active_since = None if snapshot.completed else monotonic()
        return session

    def cell_at(self, x: int, y: int) -> CellMark:
        self._check_position(x, y)
        return self._cells[y][x]

    def is_clue_crossed(self, axis: str, line_index: int, clue_index: int) -> bool:
        self._check_clue(axis, line_index, clue_index)
        return (axis, line_index, clue_index) in self._crossed_clues

    def toggle_clue(self, axis: str, line_index: int, clue_index: int) -> bool:
        """Manually cross a clue; crossing the last clue marks remaining cells X."""
        self._require_no_stroke()
        if self.assumption_active:
            raise RuntimeError("Deneme modunda ipucu işaretlenemez")
        clues = self._check_clue(axis, line_index, clue_index)
        key = (axis, line_index, clue_index)
        before = key in self._crossed_clues
        changes = []
        closing_line = not before and all(
            index == clue_index or (axis, line_index, index) in self._crossed_clues
            for index in range(len(clues))
        )
        if before or closing_line:
            positions = (
                ((x, line_index) for x in range(self.puzzle.width))
                if axis == "row"
                else ((line_index, y) for y in range(self.puzzle.height))
            )
            for x, y in positions:
                before_cell = self._cells[y][x]
                target = CellMark() if before else CellMark(CellState.EMPTY)
                if before_cell.state is (CellState.EMPTY if before else CellState.UNKNOWN):
                    changes.append(CellChangeCommand(x, y, before_cell, target))
                    self._cells[y][x] = target
        if before:
            self._crossed_clues.remove(key)
        else:
            self._crossed_clues.add(key)
        self._record_new_command(
            ClueChangeCommand(axis, line_index, clue_index, before, not before, tuple(changes))
        )
        return not before

    def _check_clue(self, axis: str, line_index: int, clue_index: int):
        if axis not in {"row", "column"} or type(line_index) is not int:
            raise ValueError("İpucu koordinatı geçersiz")
        if not 0 <= line_index < (self.puzzle.height if axis == "row" else self.puzzle.width):
            raise ValueError("İpucu koordinatı geçersiz")
        clues = self.puzzle.row_clues[line_index] if axis == "row" else self.puzzle.column_clues[line_index]
        if type(clue_index) is not int or not 0 <= clue_index < len(clues):
            raise ValueError("İpucu koordinatı geçersiz")
        return clues

    @property
    def assumption_active(self) -> bool:
        return self._assumption_cells is not None

    @property
    def assumption_move_count(self) -> int:
        return len(self._assumption_undo_stack) if self.assumption_active else 0

    def is_assumption_cell(self, x: int, y: int) -> bool:
        """Whether the displayed mark differs from the assumption's starting board."""
        self._check_position(x, y)
        return (
            self._assumption_cells is not None and self._cells[y][x] != self._assumption_cells[y][x]
        )

    def begin_assumption(self) -> None:
        self._require_no_stroke()
        if self.assumption_active:
            raise RuntimeError("Deneme Modu zaten açık")
        if self.completed:
            raise RuntimeError("Tamamlanmış bulmacada Deneme Modu başlatılamaz")
        self._assumption_cells = self.cells
        self._assumption_undo_stack.clear()
        self._assumption_redo_stack.clear()
        self._touch()

    def accept_assumption(self) -> bool:
        """Commit the net trial changes as one normal undoable command."""
        self._require_active_assumption()
        baseline = self._assumption_cells
        changes = tuple(
            CellChangeCommand(x, y, before, self._cells[y][x])
            for y, row in enumerate(baseline)
            for x, before in enumerate(row)
            if before != self._cells[y][x]
        )
        self._end_assumption()
        if changes:
            self._record_new_command(MultiCellChangeCommand(changes))
            return True
        self._touch()
        self._refresh_completion()
        return False

    def cancel_assumption(self) -> None:
        """Discard every trial mark and preserve the normal undo/redo history."""
        self._require_active_assumption()
        self._cells = [list(row) for row in self._assumption_cells]
        self._end_assumption()
        self._touch()
        self._refresh_completion()

    def _end_assumption(self) -> None:
        self._assumption_cells = None
        self._assumption_undo_stack.clear()
        self._assumption_redo_stack.clear()

    def _require_active_assumption(self) -> None:
        self._require_no_stroke()
        if not self.assumption_active:
            raise RuntimeError("Etkin Deneme Modu yok")

    @property
    def elapsed_time(self) -> float:
        if self._active_since is None:
            return self._elapsed_seconds
        return self._elapsed_seconds + max(0.0, monotonic() - self._active_since)

    @property
    def completed(self) -> bool:
        return self._completed

    @property
    def completion_percentage(self) -> float:
        required = sum(color > 0 for row in self.puzzle.solution for color in row)
        if required == 0:
            return 100.0 if self._completed else 0.0
        correct = sum(
            self._cells[y][x].state is CellState.FILLED and self._cells[y][x].color_id == color
            for y, row in enumerate(self.puzzle.solution)
            for x, color in enumerate(row)
            if color > 0
        )
        return 100.0 * correct / required

    @property
    def can_undo(self) -> bool:
        return bool(self._assumption_undo_stack if self.assumption_active else self._undo_stack)

    @property
    def can_redo(self) -> bool:
        return bool(self._assumption_redo_stack if self.assumption_active else self._redo_stack)

    def fill_cell(self, x: int, y: int, color_id: int = 1) -> bool:
        self._check_color(color_id)
        return self._change_cell(x, y, CellMark(CellState.FILLED, color_id))

    def mark_empty(self, x: int, y: int) -> bool:
        return self._change_cell(x, y, CellMark(CellState.EMPTY))

    def clear_cell(self, x: int, y: int) -> bool:
        return self._change_cell(x, y, CellMark())

    def _change_cell(self, x: int, y: int, after: CellMark) -> bool:
        before = self.cell_at(x, y)
        if before == after:
            return False
        if self._stroke is None:
            history = self._assumption_undo_stack if self.assumption_active else self._undo_stack
            previous_moves = len(history)
            self.execute(CellChangeCommand(x, y, before, after))
            return len(history) != previous_moves
        else:
            key = (x, y)
            original = self._stroke[key].before if key in self._stroke else before
            self._cells[y][x] = after
            if original == after:
                self._stroke.pop(key, None)
            else:
                self._stroke[key] = CellChangeCommand(x, y, original, after)
            self._refresh_completion()
            return True

    def begin_stroke(self) -> None:
        if self._stroke is not None:
            raise RuntimeError("Sürükleme zaten başladı")
        self._stroke = {}

    def end_stroke(self) -> MultiCellChangeCommand | None:
        if self._stroke is None:
            raise RuntimeError("Etkin sürükleme yok")
        changes = tuple(self._stroke.values())
        self._stroke = None
        if not changes:
            return None
        if self.auto_x_completed_lines:
            changes = self._merge_changes(changes, self._auto_x_changes())
            if not changes:
                self._refresh_completion()
                return None
        command = MultiCellChangeCommand(changes)
        self._record_new_command(command)
        return command

    def cancel_stroke(self) -> None:
        if self._stroke is None:
            raise RuntimeError("Etkin sürükleme yok")
        for change in self._stroke.values():
            self._cells[change.y][change.x] = change.before
        self._stroke = None
        self._refresh_completion()

    def execute(self, command: Command) -> None:
        self._require_no_stroke()
        changes = self._check_command(command, reverse=False)
        for change in changes:
            self._cells[change.y][change.x] = change.after
        if self.auto_x_completed_lines:
            automatic = self._auto_x_changes()
            if automatic:
                combined = self._merge_changes(changes, automatic)
                if not combined:
                    self._refresh_completion()
                    return
                command = MultiCellChangeCommand(combined)
        self._record_new_command(command)

    @staticmethod
    def _merge_changes(
        manual: tuple[CellChangeCommand, ...], automatic: tuple[CellChangeCommand, ...]
    ) -> tuple[CellChangeCommand, ...]:
        original = {(change.x, change.y): change.before for change in manual}
        final = {(change.x, change.y): change.after for change in manual}
        for change in automatic:
            position = (change.x, change.y)
            original.setdefault(position, change.before)
            final[position] = change.after
        return tuple(
            CellChangeCommand(x, y, before, final[x, y])
            for (x, y), before in original.items()
            if before != final[x, y]
        )

    def set_auto_x_completed_lines(self, enabled: bool) -> bool:
        """Apply newly enabled auto-X as one undoable command, if needed."""
        self._require_no_stroke()
        if type(enabled) is not bool:
            raise TypeError("Otomatik X ayarı bool olmalı")
        self.auto_x_completed_lines = enabled
        if not enabled:
            return False
        changes = self._auto_x_changes()
        if not changes:
            return False
        self._record_new_command(MultiCellChangeCommand(changes))
        return True

    def _auto_x_changes(self) -> tuple[CellChangeCommand, ...]:
        """Cross only unknown cells forced empty by completed clue constraints."""
        changes: list[CellChangeCommand] = []
        empty = CellMark(CellState.EMPTY)
        while True:
            analysis = analyze_board(self.puzzle, self.cells)
            completed_rows = {
                y for y, row in enumerate(analysis.rows) if row.status is LineStatus.COMPLETED
            }
            completed_columns = {
                x
                for x, column in enumerate(analysis.columns)
                if column.status is LineStatus.COMPLETED
            }
            pending = [
                (x, y)
                for y in range(self.puzzle.height)
                for x in range(self.puzzle.width)
                if (y in completed_rows or x in completed_columns)
                and self._cells[y][x].state is CellState.UNKNOWN
            ]
            if not pending:
                return tuple(changes)
            for x, y in pending:
                changes.append(CellChangeCommand(x, y, self._cells[y][x], empty))
                self._cells[y][x] = empty

    def undo(self) -> bool:
        self._require_no_stroke()
        undo_stack = self._assumption_undo_stack if self.assumption_active else self._undo_stack
        redo_stack = self._assumption_redo_stack if self.assumption_active else self._redo_stack
        if not undo_stack:
            return False
        command = undo_stack[-1]
        changes = self._check_command(command, reverse=True)
        for change in reversed(changes):
            self._cells[change.y][change.x] = change.before
        if isinstance(command, ClueChangeCommand):
            key = (command.axis, command.line_index, command.clue_index)
            if command.before:
                self._crossed_clues.add(key)
            else:
                self._crossed_clues.remove(key)
        undo_stack.pop()
        redo_stack.append(command)
        if not self.assumption_active:
            self.undo_count += 1
        self._touch()
        self._refresh_completion()
        return True

    def redo(self) -> bool:
        self._require_no_stroke()
        undo_stack = self._assumption_undo_stack if self.assumption_active else self._undo_stack
        redo_stack = self._assumption_redo_stack if self.assumption_active else self._redo_stack
        if not redo_stack:
            return False
        command = redo_stack[-1]
        changes = self._check_command(command, reverse=False)
        for change in changes:
            self._cells[change.y][change.x] = change.after
        if isinstance(command, ClueChangeCommand):
            key = (command.axis, command.line_index, command.clue_index)
            if command.after:
                self._crossed_clues.add(key)
            else:
                self._crossed_clues.remove(key)
        redo_stack.pop()
        undo_stack.append(command)
        if not self.assumption_active:
            self.redo_count += 1
        self._touch()
        self._refresh_completion()
        return True

    def record_hint(self) -> None:
        """Record a consumed hint; hint selection belongs to a later phase."""
        self._require_no_stroke()
        self.hint_count += 1
        self._touch()

    def pause(self) -> None:
        self._require_no_stroke()
        if not self._paused:
            self._paused = True
            self._stop_clock()

    def resume(self) -> None:
        self._require_no_stroke()
        if self._paused:
            self._paused = False
            if not self._completed:
                self._active_since = monotonic()

    def _record_new_command(self, command: Command) -> None:
        if self.assumption_active:
            self._assumption_undo_stack.append(command)
            self._assumption_redo_stack.clear()
            self._touch()
            self._refresh_completion()
            return
        self._undo_stack.append(command)
        self._redo_stack.clear()
        self.move_count += 1
        self.mistake_count += sum(
            self._is_mistake(change.x, change.y, change.after) for change in command.changes
        )
        self._touch()
        self._refresh_completion()

    def _check_command(self, command: Command, *, reverse: bool) -> tuple[CellChangeCommand, ...]:
        if type(command) not in (CellChangeCommand, MultiCellChangeCommand, ClueChangeCommand):
            raise TypeError("Geçersiz komut")
        if isinstance(command, ClueChangeCommand):
            self._check_clue(command.axis, command.line_index, command.clue_index)
            crossed = (command.axis, command.line_index, command.clue_index) in self._crossed_clues
            if crossed != (command.after if reverse else command.before):
                raise ValueError("Komut ipucu durumuyla eşleşmiyor")
        changes = command.changes
        for change in changes:
            self._check_position(change.x, change.y)
            self._check_mark(change.before)
            self._check_mark(change.after)
            expected = change.after if reverse else change.before
            if self._cells[change.y][change.x] != expected:
                raise ValueError("Komut mevcut hücre durumuyla eşleşmiyor")
        return changes

    def _check_mark(self, mark: CellMark) -> None:
        if mark.state is CellState.FILLED:
            self._check_color(mark.color_id)

    def _check_color(self, color_id: int) -> None:
        if type(color_id) is not int or not 1 <= color_id <= len(self.puzzle.palette):
            raise ValueError("Renk kimliği palette yok")

    def _check_position(self, x: int, y: int) -> None:
        if (
            type(x) is not int
            or type(y) is not int
            or not (0 <= x < self.puzzle.width and 0 <= y < self.puzzle.height)
        ):
            raise IndexError("Hücre koordinatı tahta dışında")

    def _is_mistake(self, x: int, y: int, mark: CellMark) -> bool:
        target = self.puzzle.solution[y][x]
        return (mark.state is CellState.FILLED and mark.color_id != target) or (
            mark.state is CellState.EMPTY and target != 0
        )

    def _is_solved(self) -> bool:
        return all(
            (mark.state is CellState.FILLED and mark.color_id == target)
            if target
            else mark.state is not CellState.FILLED
            for row, answer in zip(self._cells, self.puzzle.solution)
            for mark, target in zip(row, answer)
        )

    def _refresh_completion(self) -> None:
        solved = self._is_solved() and not self.assumption_active
        if solved and not self._completed:
            self._stop_clock()
        elif not solved and self._completed and not self._paused:
            self._active_since = monotonic()
        self._completed = solved

    def _stop_clock(self) -> None:
        if self._active_since is not None:
            self._elapsed_seconds += max(0.0, monotonic() - self._active_since)
            self._active_since = None

    def _touch(self) -> None:
        self.last_played_at = datetime.now(timezone.utc)

    def _require_no_stroke(self) -> None:
        if self._stroke is not None:
            raise RuntimeError("Önce sürükleme bitirilmeli")
