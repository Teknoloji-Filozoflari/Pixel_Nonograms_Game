"""Validate editor drafts with the solver and manage local .nono files."""

from dataclasses import dataclass
from pathlib import Path

from pixel_nonograms.core import Difficulty, EditorDraft, Puzzle
from pixel_nonograms.core.compact import compact_puzzle
from pixel_nonograms.importer import read_puzzle, write_puzzle
from pixel_nonograms.solver import SolveStatus, validate_unique_solution


@dataclass(frozen=True, slots=True)
class EditorSaveResult:
    status: SolveStatus
    puzzle: Puzzle
    path: Path | None


def save_editor_puzzle(
    draft: EditorDraft,
    directory: str | Path,
    *,
    title: str,
    author: str,
    description: str = "",
    difficulty: Difficulty = Difficulty.EASY,
    tags: tuple[str, ...] = (),
    timeout_seconds: float = 5.0,
    node_limit: int = 100_000,
) -> EditorSaveResult:
    """Write a new puzzle only if its clues have exactly one solution."""
    if type(draft) is not EditorDraft:
        raise TypeError("EditorDraft gerekli")
    puzzle = draft.to_puzzle(
        title=title,
        author=author,
        description=description,
        difficulty=difficulty,
        tags=tags,
    )
    puzzle = compact_puzzle(puzzle)[0]
    result = validate_unique_solution(
        puzzle, timeout_seconds=timeout_seconds, node_limit=node_limit
    )
    if result.status is not SolveStatus.SOLVED:
        return EditorSaveResult(result.status, puzzle, None)
    if result.solution != puzzle.solution:
        raise ValueError("Solver çözümü çizilen bulmacayla eşleşmiyor")
    path = Path(directory) / f"{puzzle.id}.nono"
    write_puzzle(puzzle, path)
    return EditorSaveResult(SolveStatus.SOLVED, puzzle, path)


def load_user_puzzles(
    directory: str | Path, *, existing_ids: frozenset[str] = frozenset()
) -> tuple[tuple[Puzzle, ...], tuple[str, ...]]:
    """Load local user files while reporting corrupt or duplicate entries."""
    directory = Path(directory)
    if not directory.exists():
        return (), ()
    if not directory.is_dir():
        return (), (f"Bulmaca dizini değil: {directory}",)
    puzzles = []
    errors = []
    seen = set(existing_ids)
    for path in sorted(directory.iterdir()):
        if path.suffix.lower() != ".nono":
            continue
        if path.is_symlink():
            errors.append(f"{path.name}: simgesel bağlantı desteklenmiyor")
            continue
        try:
            puzzle = read_puzzle(path)
        except (OSError, ValueError) as exc:
            errors.append(f"{path.name}: {exc}")
            continue
        if puzzle.id in seen:
            errors.append(f"{path.name}: yinelenen bulmaca kimliği")
            continue
        seen.add(puzzle.id)
        puzzles.append(puzzle)
    return tuple(puzzles), tuple(errors)
