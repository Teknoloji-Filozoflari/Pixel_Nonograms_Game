"""Qt-independent puzzle domain."""

from .analysis import BoardAnalysis, LineAnalysis, LineStatus, analyze_board, analyze_line
from .cell import CellState
from .clue import Clue, ColorClue, calculate_clues
from .commands import CellChangeCommand, CellMark, MultiCellChangeCommand
from .editor import EditorDraft
from .game_session import GameSession
from .items import HelperItemId
from .puzzle import Difficulty, Puzzle, PuzzleMetadata
from .session_state import SessionSnapshot

__all__ = [
    "BoardAnalysis",
    "CellState",
    "CellMark",
    "CellChangeCommand",
    "Clue",
    "ColorClue",
    "Difficulty",
    "EditorDraft",
    "GameSession",
    "HelperItemId",
    "LineAnalysis",
    "LineStatus",
    "MultiCellChangeCommand",
    "Puzzle",
    "PuzzleMetadata",
    "SessionSnapshot",
    "analyze_board",
    "analyze_line",
    "calculate_clues",
]
