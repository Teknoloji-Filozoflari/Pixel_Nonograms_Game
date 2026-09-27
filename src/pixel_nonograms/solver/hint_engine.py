"""Three teaching stages for one clue-forced Nonogram move."""

from collections.abc import Sequence
from dataclasses import dataclass
from time import monotonic

from pixel_nonograms.core import CellMark, CellState, Puzzle, analyze_line

from .solver import LogicalMove, get_next_logical_move


@dataclass(frozen=True, slots=True)
class HintStep:
    level: int
    message: str
    axis: str
    line_index: int
    cell: tuple[int, int, CellMark] | None = None


@dataclass(frozen=True, slots=True)
class HintPlan:
    """A frozen explanation chain for one board state and one forced move."""

    board: tuple[tuple[CellMark, ...], ...]
    move: LogicalMove
    steps: tuple[HintStep, HintStep, HintStep]

    def step(self, level: int) -> HintStep:
        if type(level) is not int or not 1 <= level <= 3:
            raise ValueError("İpucu seviyesi 1–3 arasında olmalı")
        return self.steps[level - 1]

    def matches(self, cells: Sequence[Sequence[CellMark]]) -> bool:
        return self.board == tuple(tuple(row) for row in cells)


def _line_name(axis: str, index: int) -> str:
    return f"{index + 1}. {'satır' if axis == 'row' else 'sütun'}"


def _reason(
    puzzle: Puzzle, board: tuple[tuple[CellMark, ...], ...], move: LogicalMove, deadline: float
) -> str:
    if move.axis == "cross":
        return (
            "Satırdaki ve sütundaki geçerli yerleşimleri ayrı ayrı düşün. "
            "Bu iki kısıtın ortak olasılıkları tek bir hücre durumuna indirgeniyor."
        )

    axis = move.axis
    index = move.line_index
    marks = board[index] if axis == "row" else tuple(row[index] for row in board)
    clues = puzzle.row_clues[index] if axis == "row" else puzzle.column_clues[index]

    def check_limit() -> None:
        if monotonic() >= deadline:
            raise TimeoutError("İpucu analizi zaman sınırına ulaştı")

    line = analyze_line(clues, marks, color_count=len(puzzle.palette), check_limit=check_limit)
    label = _line_name(axis, index)
    if move.mark.state is CellState.FILLED:
        offset = move.x if axis == "row" else move.y
        for clue, starts in zip(clues, line.possible_starts):
            if not starts:
                continue
            color_id = clue.color_id if puzzle.is_colored else 1
            first = max(starts)
            last = min(starts) + clue.length - 1
            if color_id == move.mark.color_id and first <= offset <= last:
                unknown = sum(
                    marks[position].state is CellState.UNKNOWN
                    for position in range(first, last + 1)
                )
                color_note = f" ({color_id}. renk)" if puzzle.is_colored else ""
                return (
                    f"{label}: {clue.length} uzunluğundaki blok{color_note} "
                    f"{len(starts)} başlangıç konumuna sığabiliyor. Bu konumların ortak "
                    f"bölgesinde {unknown} henüz işaretlenmemiş kesin dolu hücre var."
                )
        return (
            f"{label}: {line.possibility_count} geçerli blok yerleşimini karşılaştır. "
            "Bazı hücreler her yerleşimde aynı renkle dolu kalıyor."
        )

    if move.technique == "completed_block":
        total = sum(clue.length for clue in clues)
        return (
            f"{label}: ipuçlarındaki blokların toplamı {total} dolu hücre. "
            "Bu bloklar zaten işaretli; kalan bilinmeyen hücrelere X koyabilirsin."
        )
    return (
        f"{label}: {line.possibility_count} geçerli blok yerleşimini karşılaştır. "
        "Bazı konumlara hiçbir blok yerleşemediği için o hücreler boş kalır."
    )


def create_hint_plan(
    puzzle: Puzzle,
    cells: Sequence[Sequence[CellMark]],
    *,
    timeout_seconds: float = 2.0,
) -> HintPlan | None:
    """Use clue constraints only; never reveal a stored solution cell by guessing."""
    started = monotonic()
    move = get_next_logical_move(puzzle, cells, timeout_seconds=timeout_seconds)
    if move is None:
        return None
    board = tuple(tuple(row) for row in cells)
    deadline = started + timeout_seconds
    if monotonic() >= deadline:
        raise TimeoutError("İpucu analizi zaman sınırına ulaştı")
    if move.axis == "cross":
        focus = f"{move.y + 1}. satır ve {move.x + 1}. sütuna bak."
    else:
        focus = f"{_line_name(move.axis, move.line_index)} ipuçlarına bak."
    reason = _reason(puzzle, board, move, deadline)
    action = (
        "X koy" if move.mark.state is CellState.EMPTY else f"{move.mark.color_id}. renkle doldur"
    )
    reveal = f"Kesin hücre: ({move.x + 1}, {move.y + 1}). Bu hücreye {action}."
    steps = (
        HintStep(1, f"1/3 · {focus}", move.axis, move.line_index),
        HintStep(2, f"2/3 · {reason}", move.axis, move.line_index),
        HintStep(3, f"3/3 · {reveal}", move.axis, move.line_index, (move.x, move.y, move.mark)),
    )
    return HintPlan(board, move, steps)


def get_hint(
    puzzle: Puzzle,
    cells: Sequence[Sequence[CellMark]],
    level: int,
    *,
    timeout_seconds: float = 2.0,
) -> HintStep | None:
    if type(level) is not int or not 1 <= level <= 3:
        raise ValueError("İpucu seviyesi 1–3 arasında olmalı")
    plan = create_hint_plan(puzzle, cells, timeout_seconds=timeout_seconds)
    return plan.step(level) if plan is not None else None
