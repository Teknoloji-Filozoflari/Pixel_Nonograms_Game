"""Image-to-puzzle conversion with clue-only solver validation."""

from dataclasses import dataclass
from pathlib import Path

from pixel_nonograms.core import EditorDraft
from pixel_nonograms.importer.image_importer import ImageImportOptions, import_image
from pixel_nonograms.solver import SolveStatus, validate_unique_solution


@dataclass(frozen=True, slots=True)
class ImageImportResult:
    draft: EditorDraft
    status: SolveStatus


def convert_image_to_puzzle(
    path: str | Path,
    options: ImageImportOptions = ImageImportOptions(),
    *,
    timeout_seconds: float = 5.0,
    node_limit: int = 100_000,
) -> ImageImportResult:
    draft = import_image(path, options)
    candidate = draft.to_puzzle(title="Görsel Taslağı", author="Oyuncu")
    result = validate_unique_solution(
        candidate, timeout_seconds=timeout_seconds, node_limit=node_limit
    )
    return ImageImportResult(draft, result.status)
