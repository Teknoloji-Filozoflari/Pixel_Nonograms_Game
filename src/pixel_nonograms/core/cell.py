from enum import IntEnum


class CellState(IntEnum):
    """A player's mark, independent of the puzzle's answer/color IDs."""

    UNKNOWN = 0
    FILLED = 1
    EMPTY = 2
