"""Immutable, Qt-free state transferred between a session and persistence."""

from dataclasses import dataclass
from datetime import datetime

from .commands import CellMark


@dataclass(frozen=True, slots=True)
class SessionSnapshot:
    cells: tuple[tuple[CellMark, ...], ...]
    elapsed_time: float
    move_count: int
    mistake_count: int
    hint_count: int
    started_at: datetime
    last_played_at: datetime
    completed: bool
    crossed_clues: tuple[tuple[str, int, int], ...] = ()
