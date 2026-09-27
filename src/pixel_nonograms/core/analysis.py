"""Clue-based line and board analysis; the solution grid is never consulted."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from typing import Callable

from .cell import CellState
from .clue import Clue, ColorClue
from .commands import CellMark
from .puzzle import Puzzle
from .validation import validate_clue_line


class LineStatus(StrEnum):
    UNRESOLVED = "unresolved"
    VALID_SO_FAR = "valid_so_far"
    COMPLETED = "completed"
    CONTRADICTION = "contradiction"


@dataclass(frozen=True, slots=True)
class LineAnalysis:
    status: LineStatus
    possibility_count: int
    forced_cells: tuple[CellMark | None, ...]
    possible_values: tuple[frozenset[int], ...]
    completed_clues: tuple[bool, ...]
    possible_starts: tuple[frozenset[int], ...]


@dataclass(frozen=True, slots=True)
class BoardAnalysis:
    rows: tuple[LineAnalysis, ...]
    columns: tuple[LineAnalysis, ...]


def analyze_line(
    clues: Sequence[Clue | ColorClue],
    marks: Sequence[CellMark],
    *,
    color_count: int = 1,
    check_limit: Callable[[], None] | None = None,
) -> LineAnalysis:
    """Find all clue-compatible placements using memoized constraints.

    ``forced_cells`` contains a mark only when every valid placement agrees.
    ``None`` means that at least two values remain possible at that position.
    A line is complete when no still-unmarked cell can be filled in any valid
    placement. Unknown cells forced empty need not be explicitly crossed out.
    """
    if type(color_count) is not int or not 1 <= color_count <= 255:
        raise ValueError("Renk sayısı 1–255 arasında olmalı")
    if isinstance(marks, (str, bytes)) or not isinstance(marks, Sequence):
        raise ValueError("Hücre işaretleri dizi olmalı")
    marks = tuple(marks)
    if not marks or len(marks) > 100:
        raise ValueError("Çizgi uzunluğu 1–100 arasında olmalı")
    if any(type(mark) is not CellMark for mark in marks):
        raise ValueError("Geçersiz hücre işareti")
    if any(mark.color_id > color_count for mark in marks):
        raise ValueError("Hücre rengi palette yok")
    colored = color_count > 1
    clues = validate_clue_line(clues, len(marks), color_count, colored)
    size = len(marks)

    @cache
    def search(position: int, clue_index: int) -> tuple[int, tuple[int, ...], tuple[int, ...]]:
        if check_limit is not None:
            check_limit()
        if clue_index == len(clues):
            if any(mark.state is CellState.FILLED for mark in marks[position:]):
                return 0, (0,) * (size - position), (0,) * len(clues)
            return 1, (1,) * (size - position), (0,) * len(clues)
        if position == size:
            return 0, (), (0,) * len(clues)

        count = 0
        possible = [0] * (size - position)
        possible_starts = [0] * len(clues)

        if marks[position].state is not CellState.FILLED:
            child_count, child_masks, child_starts = search(position + 1, clue_index)
            if child_count:
                count += child_count
                possible[0] |= 1  # bit 0: empty
                for offset, mask in enumerate(child_masks, 1):
                    possible[offset] |= mask
                for index, starts in enumerate(child_starts):
                    possible_starts[index] |= starts

        clue = clues[clue_index]
        color_id = clue.color_id if colored else 1
        end = position + clue.length
        needs_gap = clue_index + 1 < len(clues) and (
            not colored or color_id == clues[clue_index + 1].color_id
        )
        next_position = end + int(needs_gap)
        if (
            next_position <= size
            and all(
                mark.state is CellState.UNKNOWN
                or (mark.state is CellState.FILLED and mark.color_id == color_id)
                for mark in marks[position:end]
            )
            and (not needs_gap or marks[end].state is not CellState.FILLED)
        ):
            child_count, child_masks, child_starts = search(next_position, clue_index + 1)
            if child_count:
                count += child_count
                for offset in range(clue.length):
                    possible[offset] |= 1 << color_id
                if needs_gap:
                    possible[clue.length] |= 1
                for offset, mask in enumerate(child_masks, next_position - position):
                    possible[offset] |= mask
                possible_starts[clue_index] |= 1 << position
                for index, starts in enumerate(child_starts):
                    possible_starts[index] |= starts
        return count, tuple(possible), tuple(possible_starts)

    count, masks, starts = search(0, 0)
    if count == 0:
        return LineAnalysis(
            LineStatus.CONTRADICTION,
            0,
            (None,) * size,
            (frozenset(),) * size,
            (False,) * len(clues),
            (frozenset(),) * len(clues),
        )

    forced = tuple(
        (
            CellMark(CellState.EMPTY)
            if mask == 1
            else CellMark(CellState.FILLED, mask.bit_length() - 1)
        )
        if mask.bit_count() == 1
        else None
        for mask in masks
    )
    if all(mask == 1 or mark.state is CellState.FILLED for mask, mark in zip(masks, marks)):
        status = LineStatus.COMPLETED
    elif all(mark.state is CellState.UNKNOWN for mark in marks):
        status = LineStatus.UNRESOLVED
    else:
        status = LineStatus.VALID_SO_FAR
    possible_values = tuple(
        frozenset(value for value in range(color_count + 1) if mask & (1 << value))
        for mask in masks
    )
    completed_clues = tuple(
        start_mask.bit_count() == 1
        and all(
            mark.state is CellState.FILLED and mark.color_id == (clue.color_id if colored else 1)
            for mark in marks[
                start_mask.bit_length() - 1 : start_mask.bit_length() - 1 + clue.length
            ]
        )
        for clue, start_mask in zip(clues, starts)
    )
    possible_starts = tuple(
        frozenset(position for position in range(size) if mask & (1 << position)) for mask in starts
    )
    return LineAnalysis(status, count, forced, possible_values, completed_clues, possible_starts)


def analyze_board(
    puzzle: Puzzle,
    cells: Sequence[Sequence[CellMark]],
    *,
    check_limit: Callable[[], None] | None = None,
) -> BoardAnalysis:
    """Analyze rows and columns against clues, without reading puzzle.solution."""
    if type(puzzle) is not Puzzle:
        raise TypeError("Bir Puzzle gerekli")
    if (
        isinstance(cells, (str, bytes))
        or not isinstance(cells, Sequence)
        or len(cells) != puzzle.height
    ):
        raise ValueError("Tahta satır sayısı bulmacayla eşleşmiyor")
    if any(
        isinstance(row, (str, bytes)) or not isinstance(row, Sequence) or len(row) != puzzle.width
        for row in cells
    ):
        raise ValueError("Tahta sütun sayısı bulmacayla eşleşmiyor")
    rows = tuple(
        analyze_line(clues, row, color_count=len(puzzle.palette), check_limit=check_limit)
        for clues, row in zip(puzzle.row_clues, cells)
    )
    columns = tuple(
        analyze_line(
            clues,
            tuple(cells[y][x] for y in range(puzzle.height)),
            color_count=len(puzzle.palette),
            check_limit=check_limit,
        )
        for x, clues in enumerate(puzzle.column_clues)
    )
    return BoardAnalysis(rows, columns)
