"""Pure domain validation helpers."""

import re
from collections.abc import Sequence

from .clue import Clue, ColorClue

HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}\Z")
MAX_DIMENSION = 100


def validate_solution(
    solution: Sequence[Sequence[int]], width: int, height: int, color_count: int
) -> tuple[tuple[int, ...], ...]:
    if type(width) is not int or type(height) is not int:
        raise ValueError("Bulmaca boyutları tam sayı olmalı")
    if not (1 <= width <= MAX_DIMENSION and 1 <= height <= MAX_DIMENSION):
        raise ValueError(f"Bulmaca boyutları 1–{MAX_DIMENSION} arasında olmalı")
    if (
        isinstance(solution, (str, bytes))
        or not isinstance(solution, Sequence)
        or len(solution) != height
    ):
        raise ValueError("Çözüm satır sayısı yükseklikle eşleşmeli")
    rows = []
    for row in solution:
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence) or len(row) != width:
            raise ValueError("Çözüm sütun sayısı genişlikle eşleşmeli")
        if any(type(cell) is not int or not 0 <= cell <= color_count for cell in row):
            raise ValueError("Çözüm geçersiz renk kimliği içeriyor")
        rows.append(tuple(row))
    return tuple(rows)


def validate_palette(palette: Sequence[str]) -> tuple[str, ...]:
    if (
        isinstance(palette, (str, bytes))
        or not isinstance(palette, Sequence)
        or not 1 <= len(palette) <= 255
    ):
        raise ValueError("Palette 1–255 renk içermeli")
    if any(type(color) is not str or HEX_COLOR.fullmatch(color) is None for color in palette):
        raise ValueError("Renkler #RRGGBB biçiminde olmalı")
    normalized = tuple(color.upper() for color in palette)
    if len(set(normalized)) != len(normalized):
        raise ValueError("Palette yinelenen renk içeriyor")
    return normalized


def validate_clue_line(
    clues: Sequence[Clue | ColorClue], line_length: int, color_count: int, colored: bool
) -> tuple[Clue | ColorClue, ...]:
    if isinstance(clues, (str, bytes)) or not isinstance(clues, Sequence):
        raise ValueError("İpucu çizgisi bir dizi olmalı")
    expected_type = ColorClue if colored else Clue
    if any(type(clue) is not expected_type for clue in clues):
        raise ValueError("İpucu türü bulmaca renk türüyle eşleşmiyor")
    if colored and any(clue.color_id > color_count for clue in clues):
        raise ValueError("İpucu geçersiz renk kimliği içeriyor")
    minimum = sum(clue.length for clue in clues)
    if colored:
        minimum += sum(a.color_id == b.color_id for a, b in zip(clues, clues[1:]))
    else:
        minimum += max(0, len(clues) - 1)
    if minimum > line_length:
        raise ValueError("İpuçları çizgiye sığmıyor")
    return tuple(clues)
