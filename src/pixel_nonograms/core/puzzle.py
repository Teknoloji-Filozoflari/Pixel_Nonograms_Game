from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum

from .clue import Clue, ColorClue, calculate_clues
from .items import HelperItemId
from .validation import validate_clue_line, validate_palette, validate_solution


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


@dataclass(frozen=True, slots=True)
class PuzzleMetadata:
    revision: int = 1
    source: str = "local"
    license: str | None = None

    def __post_init__(self) -> None:
        if type(self.revision) is not int or self.revision < 1:
            raise ValueError("Revizyon pozitif tam sayı olmalı")
        if type(self.source) is not str or not self.source.strip():
            raise ValueError("Kaynak boş olamaz")
        if self.license is not None and (type(self.license) is not str or not self.license.strip()):
            raise ValueError("Lisans boş olamaz")


@dataclass(frozen=True, slots=True)
class Puzzle:
    """Immutable puzzle definition. Solution: 0=empty, 1..N=palette IDs."""

    id: str
    title: str
    author: str
    description: str
    width: int
    height: int
    difficulty: Difficulty
    tags: tuple[str, ...]
    palette: tuple[str, ...]
    solution: tuple[tuple[int, ...], ...]
    row_clues: tuple[tuple[Clue | ColorClue, ...], ...] | None = None
    column_clues: tuple[tuple[Clue | ColorClue, ...], ...] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: PuzzleMetadata = field(default_factory=PuzzleMetadata)
    reward_item_id: HelperItemId | None = None

    def __post_init__(self) -> None:
        if type(self.id) is not str or not self.id.strip() or len(self.id) > 128:
            raise ValueError("Bulmaca kimliği 1–128 karakter olmalı")
        if type(self.title) is not str or not self.title.strip() or len(self.title) > 200:
            raise ValueError("Başlık 1–200 karakter olmalı")
        if type(self.author) is not str or type(self.description) is not str:
            raise ValueError("Yazar ve açıklama metin olmalı")
        if type(self.difficulty) is not Difficulty:
            raise ValueError("Geçersiz zorluk")
        if not isinstance(self.metadata, PuzzleMetadata):
            raise ValueError("Geçersiz metadata")
        if self.reward_item_id is not None:
            try:
                item_id = HelperItemId(self.reward_item_id)
            except ValueError as exc:
                raise ValueError("Bilinmeyen bulmaca ödülü") from exc
            object.__setattr__(self, "reward_item_id", item_id)
        if (
            not isinstance(self.created_at, datetime)
            or self.created_at.tzinfo is None
            or self.created_at.utcoffset() is None
        ):
            raise ValueError("Oluşturulma zamanı saat dilimi içermeli")
        if isinstance(self.tags, (str, bytes)) or not isinstance(self.tags, (list, tuple)):
            raise ValueError("Etiketler dizi olmalı")
        if any(type(tag) is not str or not tag.strip() for tag in self.tags):
            raise ValueError("Etiketler boş olmayan metinler olmalı")
        tags = tuple(self.tags)
        if len(set(tags)) != len(tags):
            raise ValueError("Etiketler yinelenemez")
        object.__setattr__(self, "tags", tags)

        palette = validate_palette(self.palette)
        object.__setattr__(self, "palette", palette)
        solution = validate_solution(self.solution, self.width, self.height, len(palette))
        object.__setattr__(self, "solution", solution)
        colored = len(palette) > 1
        expected_rows = tuple(calculate_clues(row, colored=colored) for row in solution)
        expected_columns = tuple(
            calculate_clues((solution[y][x] for y in range(self.height)), colored=colored)
            for x in range(self.width)
        )
        for name, supplied, expected, line_length in (
            ("row_clues", self.row_clues, expected_rows, self.width),
            ("column_clues", self.column_clues, expected_columns, self.height),
        ):
            if supplied is None:
                object.__setattr__(self, name, expected)
                continue
            if (
                isinstance(supplied, (str, bytes))
                or not isinstance(supplied, (list, tuple))
                or len(supplied) != len(expected)
            ):
                raise ValueError(f"{name} sayısı boyutla eşleşmiyor")
            checked = tuple(
                validate_clue_line(line, line_length, len(palette), colored) for line in supplied
            )
            if checked != expected:
                raise ValueError(f"{name} çözümle eşleşmiyor")
            object.__setattr__(self, name, checked)

    @property
    def is_colored(self) -> bool:
        return len(self.palette) > 1
