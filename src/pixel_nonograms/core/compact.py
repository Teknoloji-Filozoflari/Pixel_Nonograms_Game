"""Remove clue-free lines before publishing puzzles, retaining coordinate maps."""
from dataclasses import replace

from .puzzle import Puzzle


def compact_puzzle(puzzle: Puzzle):
    if "packaged-grid" in puzzle.tags:
        return puzzle, tuple(range(puzzle.height)), tuple(range(puzzle.width))
    rows = tuple(y for y, clues in enumerate(puzzle.row_clues) if clues)
    columns = tuple(x for x, clues in enumerate(puzzle.column_clues) if clues)
    if not rows or not columns:
        return puzzle, tuple(range(puzzle.height)), tuple(range(puzzle.width))
    if len(rows) == puzzle.height and len(columns) == puzzle.width:
        return puzzle, rows, columns
    return replace(
        puzzle, width=len(columns), height=len(rows),
        solution=tuple(tuple(puzzle.solution[y][x] for x in columns) for y in rows),
        row_clues=None, column_clues=None,
    ), rows, columns
