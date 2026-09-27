"""Application services independent of Qt widgets."""

from .editor import EditorSaveResult, load_user_puzzles, save_editor_puzzle
from .image_import import ImageImportResult, convert_image_to_puzzle
from .inventory import ITEM_NAMES, AidResult, InventoryService
from .puzzle_library import (
    PuzzleEntry,
    PuzzleLibrary,
    PuzzleQuery,
    PuzzleSort,
    PuzzleStatus,
    built_in_puzzles,
)

__all__ = [
    "PuzzleEntry",
    "AidResult",
    "EditorSaveResult",
    "ImageImportResult",
    "InventoryService",
    "load_user_puzzles",
    "save_editor_puzzle",
    "ITEM_NAMES",
    "PuzzleLibrary",
    "PuzzleQuery",
    "PuzzleSort",
    "PuzzleStatus",
    "built_in_puzzles",
    "convert_image_to_puzzle",
]
