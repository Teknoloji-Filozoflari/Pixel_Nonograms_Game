"""Bounded clue-only logical replay and advisory artwork diagnostics."""

from collections import Counter
from dataclasses import dataclass
from math import isfinite
from time import monotonic

from pixel_nonograms.core import CellMark, Difficulty, Puzzle
from pixel_nonograms.solver.solver import get_next_logical_move


@dataclass(frozen=True, slots=True)
class QualityReport:
    status: str
    resolved: int
    total: int
    techniques: tuple[tuple[str, int], ...]
    difficulty: Difficulty | None
    warnings: tuple[str, ...]

    @property
    def teaching_key(self) -> tuple[int, int, int]:
        """Complete, simpler deductions first; unfinished analyses last."""
        rank = list(Difficulty).index(self.difficulty) if self.difficulty else 4
        return rank, len(self.techniques), self.total


def artwork_warnings(puzzle: Puzzle) -> tuple[str, ...]:
    grid = puzzle.solution
    filled = sum(value != 0 for row in grid for value in row)
    isolated = sum(
        value != 0 and not any(
            0 <= nx < puzzle.width and 0 <= ny < puzzle.height
            and grid[ny][nx] == value
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
        )
        for y, row in enumerate(grid) for x, value in enumerate(row)
    )
    warnings = []
    density = filled / (puzzle.width * puzzle.height)
    if density < 0.1 or density > 0.9:
        warnings.append("Doluluk çok düşük veya yüksek; görsel ayrıntıları kontrol edin.")
    if filled >= 5 and isolated / filled >= 0.25:
        warnings.append("Çok sayıda tekil renk pikseli var; görselde gürültü olabilir.")
    return tuple(warnings)


def assess_quality(puzzle: Puzzle, *, timeout_seconds: float = 2.0) -> QualityReport:
    if not isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("Analiz süresi pozitif ve sonlu olmalı")
    deadline = monotonic() + timeout_seconds
    cells = [[CellMark() for _ in range(puzzle.width)] for _ in range(puzzle.height)]
    counts: Counter[str] = Counter()
    total = puzzle.width * puzzle.height
    resolved = 0
    status = "solved"
    while resolved < total:
        remaining = deadline - monotonic()
        if remaining <= 0:
            status = "limit"
            break
        try:
            move = get_next_logical_move(puzzle, cells, timeout_seconds=remaining)
        except TimeoutError:
            status = "limit"
            break
        if move is None:
            status = "stalled"
            break
        cells[move.y][move.x] = move.mark
        counts[move.technique] += 1
        resolved += 1
    difficulty = None
    if status == "solved":
        difficulty = Difficulty.EASY
        if counts["impossible_position"]:
            difficulty = Difficulty.MEDIUM
        if counts["constraint_propagation"]:
            difficulty = Difficulty.HARD
    return QualityReport(
        status, resolved, total, tuple(sorted(counts.items())), difficulty,
        artwork_warnings(puzzle),
    )


def quality_text(report: QualityReport) -> str:
    from .puzzle_library import DIFFICULTY_LABELS

    states = {
        "solved": "Tahminsiz mantıksal çözüm tamamlandı",
        "stalled": "Mevcut teknikler ilerleyemedi; tahmin gerektiği kanıtlanmadı",
        "limit": "Mantıksal analiz süre sınırında durdu; sonuç belirsiz",
    }
    names = {
        "overlap": "Ortak hücre", "completed_block": "Tamamlanan blok",
        "impossible_position": "Olanaksız konum", "constraint_propagation": "Çapraz çıkarım",
    }
    parts = [f"{states[report.status]} ({report.resolved}/{report.total})."]
    if report.difficulty:
        parts.append(f"Tekniklere göre yaklaşık zorluk: {DIFFICULTY_LABELS[report.difficulty]}.")
    parts.extend(f"{names.get(name, name)}: {count}." for name, count in report.techniques)
    parts.extend(report.warnings)
    return " ".join(parts)
