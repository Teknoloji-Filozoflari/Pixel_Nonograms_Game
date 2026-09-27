"""Lazy, clue-compatible placements for a single line."""

from collections.abc import Iterator, Sequence

from pixel_nonograms.core import CellMark, CellState, Clue, ColorClue, analyze_line


def generate_line_possibilities(
    clues: Sequence[Clue | ColorClue],
    marks: Sequence[CellMark],
    *,
    color_count: int = 1,
) -> Iterator[tuple[int, ...]]:
    """Yield line values (0=empty, 1..N=color), without materializing all placements.

    Consumers should stop iteration when they have enough candidates. The solver
    uses the bounded-memory dynamic-programming analysis for large lines.
    """
    marks = tuple(marks)
    analysis = analyze_line(clues, marks, color_count=color_count)
    if analysis.possibility_count == 0:
        return
    clues = tuple(clues)
    colored = color_count > 1
    size = len(marks)

    def place(position: int, clue_index: int, prefix: tuple[int, ...]) -> Iterator[tuple[int, ...]]:
        if clue_index == len(clues):
            if all(mark.state is not CellState.FILLED for mark in marks[position:]):
                yield prefix + (0,) * (size - position)
            return
        if position == size:
            return

        if marks[position].state is not CellState.FILLED:
            yield from place(position + 1, clue_index, prefix + (0,))

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
            segment = (color_id,) * clue.length + ((0,) if needs_gap else ())
            yield from place(next_position, clue_index + 1, prefix + segment)

    yield from place(0, 0, ())
