"""Clue-only propagation, bounded search, and explainable logical moves."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from time import monotonic

from pixel_nonograms.core import (
    BoardAnalysis,
    CellMark,
    CellState,
    LineStatus,
    Puzzle,
    analyze_board,
    calculate_clues,
)


class SolveStatus(StrEnum):
    SOLVED = "SOLVED"
    NO_SOLUTION = "NO_SOLUTION"
    MULTIPLE_SOLUTIONS = "MULTIPLE_SOLUTIONS"
    UNKNOWN_LIMIT = "UNKNOWN_LIMIT"


@dataclass(frozen=True, slots=True)
class SolveResult:
    status: SolveStatus
    solution: tuple[tuple[int, ...], ...] | None
    alternate_solution: tuple[tuple[int, ...], ...] | None
    nodes_explored: int
    elapsed_time: float


@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: SolveStatus
    is_valid: bool | None
    is_unique: bool | None
    matches_stored_solution: bool | None


@dataclass(frozen=True, slots=True)
class LogicalMove:
    x: int
    y: int
    mark: CellMark
    technique: str
    axis: str
    line_index: int
    explanation: str


class _LimitReached(Exception):
    pass


class _Budget:
    def __init__(self, timeout_seconds: float, node_limit: int) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
            or not isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError("Zaman sınırı pozitif sayı olmalı")
        if type(node_limit) is not int or node_limit < 1:
            raise ValueError("Düğüm sınırı pozitif tam sayı olmalı")
        self.started = monotonic()
        self.deadline = self.started + timeout_seconds
        self.node_limit = node_limit
        self.nodes = 0

    def check_time(self) -> None:
        if monotonic() >= self.deadline:
            raise _LimitReached

    def visit(self) -> None:
        self.check_time()
        if self.nodes >= self.node_limit:
            raise _LimitReached
        self.nodes += 1


def _check_cells(
    puzzle: Puzzle, cells: Sequence[Sequence[CellMark]] | None
) -> tuple[tuple[CellMark, ...], ...]:
    if type(puzzle) is not Puzzle:
        raise TypeError("Bir Puzzle gerekli")
    if cells is None:
        return tuple(tuple(CellMark() for _ in range(puzzle.width)) for _ in range(puzzle.height))
    if (
        isinstance(cells, (str, bytes))
        or not isinstance(cells, Sequence)
        or len(cells) != puzzle.height
    ):
        raise ValueError("Tahta satır sayısı bulmacayla eşleşmiyor")
    rows = []
    for row in cells:
        if (
            isinstance(row, (str, bytes))
            or not isinstance(row, Sequence)
            or len(row) != puzzle.width
        ):
            raise ValueError("Tahta sütun sayısı bulmacayla eşleşmiyor")
        if any(type(mark) is not CellMark or mark.color_id > len(puzzle.palette) for mark in row):
            raise ValueError("Tahta geçersiz hücre işareti içeriyor")
        rows.append(tuple(row))
    return tuple(rows)


def _propagate(
    puzzle: Puzzle, cells: list[list[CellMark]], budget: _Budget
) -> BoardAnalysis | None:
    while True:
        budget.check_time()
        analysis = analyze_board(puzzle, cells, check_limit=budget.check_time)
        if any(
            line.status is LineStatus.CONTRADICTION for line in (*analysis.rows, *analysis.columns)
        ):
            return None
        changed = False
        for y in range(puzzle.height):
            for x in range(puzzle.width):
                if cells[y][x].state is not CellState.UNKNOWN:
                    continue
                options = (
                    analysis.rows[y].possible_values[x] & analysis.columns[x].possible_values[y]
                )
                if not options:
                    return None
                if len(options) == 1:
                    value = next(iter(options))
                    cells[y][x] = (
                        CellMark(CellState.EMPTY)
                        if value == 0
                        else CellMark(CellState.FILLED, value)
                    )
                    changed = True
        if not changed:
            return analysis


def _values(cells: list[list[CellMark]]) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(mark.color_id if mark.state is CellState.FILLED else 0 for mark in row)
        for row in cells
    )


def solve(
    puzzle: Puzzle,
    cells: Sequence[Sequence[CellMark]] | None = None,
    *,
    timeout_seconds: float = 5.0,
    node_limit: int = 100_000,
) -> SolveResult:
    """Find up to two clue-compatible solutions; never inspect puzzle.solution."""
    budget = _Budget(timeout_seconds, node_limit)
    board = [list(row) for row in _check_cells(puzzle, cells)]
    found: list[tuple[tuple[int, ...], ...]] = []

    def search(current: list[list[CellMark]]) -> None:
        budget.visit()
        analysis = _propagate(puzzle, current, budget)
        if analysis is None:
            return
        choices = []
        for y in range(puzzle.height):
            for x in range(puzzle.width):
                if current[y][x].state is CellState.UNKNOWN:
                    options = (
                        analysis.rows[y].possible_values[x] & analysis.columns[x].possible_values[y]
                    )
                    if not options:
                        return
                    choices.append((len(options), x, y, options))
        if not choices:
            found.append(_values(current))
            return
        _, x, y, options = min(choices)
        for value in sorted(options):
            budget.check_time()
            branch = [row.copy() for row in current]
            branch[y][x] = (
                CellMark(CellState.EMPTY) if value == 0 else CellMark(CellState.FILLED, value)
            )
            search(branch)
            if len(found) >= 2:
                return

    try:
        search(board)
    except _LimitReached:
        status = SolveStatus.UNKNOWN_LIMIT
    else:
        status = (
            SolveStatus.MULTIPLE_SOLUTIONS
            if len(found) >= 2
            else SolveStatus.SOLVED
            if found
            else SolveStatus.NO_SOLUTION
        )
    return SolveResult(
        status,
        found[0] if found else None,
        found[1] if len(found) > 1 else None,
        budget.nodes,
        max(0.0, monotonic() - budget.started),
    )


def validate_unique_solution(
    puzzle: Puzzle, *, timeout_seconds: float = 5.0, node_limit: int = 100_000
) -> SolveResult:
    """Classify clue solution count, including uncertainty from resource limits."""
    return solve(puzzle, timeout_seconds=timeout_seconds, node_limit=node_limit)


def validate(
    puzzle: Puzzle, *, timeout_seconds: float = 5.0, node_limit: int = 100_000
) -> ValidationResult:
    """Check the stored answer against clues and classify uniqueness."""
    if type(puzzle) is not Puzzle:
        raise TypeError("Bir Puzzle gerekli")
    stored_matches_clues = puzzle.row_clues == tuple(
        calculate_clues(row, colored=puzzle.is_colored) for row in puzzle.solution
    ) and puzzle.column_clues == tuple(
        calculate_clues(
            (puzzle.solution[y][x] for y in range(puzzle.height)),
            colored=puzzle.is_colored,
        )
        for x in range(puzzle.width)
    )
    if not stored_matches_clues:
        return ValidationResult(SolveStatus.NO_SOLUTION, False, False, False)
    result = validate_unique_solution(
        puzzle, timeout_seconds=timeout_seconds, node_limit=node_limit
    )
    if result.status is SolveStatus.UNKNOWN_LIMIT:
        return ValidationResult(result.status, True, None, True)
    unique = result.status is SolveStatus.SOLVED
    return ValidationResult(
        result.status,
        result.status is not SolveStatus.NO_SOLUTION,
        unique,
        True,
    )


def get_next_logical_move(
    puzzle: Puzzle,
    cells: Sequence[Sequence[CellMark]],
    *,
    timeout_seconds: float = 5.0,
) -> LogicalMove | None:
    """Return one forced move from current clues/marks, with no guessing."""
    board = _check_cells(puzzle, cells)
    budget = _Budget(timeout_seconds, 1)
    try:
        analysis = analyze_board(puzzle, board, check_limit=budget.check_time)
    except _LimitReached as exc:
        raise TimeoutError("Mantıksal ipucu zaman sınırına ulaştı") from exc
    if any(line.status is LineStatus.CONTRADICTION for line in (*analysis.rows, *analysis.columns)):
        raise ValueError("Oyuncu işaretleri ipuçlarıyla çelişiyor")
    for axis, lines in (("row", analysis.rows), ("column", analysis.columns)):
        for index, line in enumerate(lines):
            for offset, forced in enumerate(line.forced_cells):
                x, y = (offset, index) if axis == "row" else (index, offset)
                if forced is None or board[y][x].state is not CellState.UNKNOWN:
                    continue
                clues = puzzle.row_clues[index] if axis == "row" else puzzle.column_clues[index]
                already_filled = sum(
                    mark.state is CellState.FILLED
                    for mark in (board[index] if axis == "row" else (row[index] for row in board))
                )
                if forced.state is CellState.FILLED:
                    technique = "overlap"
                    reason = "Bütün geçerli yerleşimler bu hücreyi dolduruyor."
                elif already_filled == sum(clue.length for clue in clues):
                    technique = "completed_block"
                    reason = "Gerekli dolu bloklar işaretli; bu hücre boş kalmalı."
                else:
                    technique = "impossible_position"
                    reason = "Hiçbir geçerli blok yerleşimi bu hücreyi dolduramıyor."
                name = "satır" if axis == "row" else "sütun"
                action = (
                    "X koy"
                    if forced.state is CellState.EMPTY
                    else f"renk {forced.color_id} ile doldur"
                )
                explanation = (
                    f"{index + 1}. {name}: {reason} ({x + 1}, {y + 1}) hücresini {action}."
                )
                return LogicalMove(x, y, forced, technique, axis, index, explanation)
    for y in range(puzzle.height):
        for x in range(puzzle.width):
            if board[y][x].state is not CellState.UNKNOWN:
                continue
            options = analysis.rows[y].possible_values[x] & analysis.columns[x].possible_values[y]
            if not options:
                raise ValueError("Satır ve sütun kısıtları çelişiyor")
            if len(options) == 1:
                value = next(iter(options))
                mark = (
                    CellMark(CellState.EMPTY) if value == 0 else CellMark(CellState.FILLED, value)
                )
                action = "X koy" if value == 0 else f"renk {value} ile doldur"
                explanation = (
                    f"{y + 1}. satır ve {x + 1}. sütunun ortak olasılığı yalnızca bu durum. "
                    f"({x + 1}, {y + 1}) hücresini {action}."
                )
                return LogicalMove(x, y, mark, "constraint_propagation", "cross", y, explanation)
    return None


def explain_next_logical_move(puzzle: Puzzle, cells: Sequence[Sequence[CellMark]]) -> str | None:
    move = get_next_logical_move(puzzle, cells)
    return move.explanation if move is not None else None
