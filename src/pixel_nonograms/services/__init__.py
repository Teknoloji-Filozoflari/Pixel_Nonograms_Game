"""Load application services on demand to keep startup lightweight."""
from importlib import import_module

_EXPORTS = {
    "editor": ("EditorSaveResult", "load_user_puzzles", "save_editor_puzzle"),
    "image_import": ("ImageImportResult", "convert_image_to_puzzle"),
    "inventory": ("ITEM_NAMES", "AidResult", "InventoryService"),
    "puzzle_library": ("PuzzleEntry", "PuzzleLibrary", "PuzzleQuery", "PuzzleSort",
                       "PuzzleStatus", "built_in_puzzles"),
}
__all__ = [name for names in _EXPORTS.values() for name in names]


def __getattr__(name):
    for module, names in _EXPORTS.items():
        if name in names:
            value = getattr(import_module(f"{__name__}.{module}"), name)
            globals()[name] = value
            return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
