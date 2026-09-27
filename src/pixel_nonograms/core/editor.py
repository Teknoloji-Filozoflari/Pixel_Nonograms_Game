"""Qt-independent mutable draft for drawing a Nonogram solution."""

from collections import deque
from uuid import uuid4

from .clue import calculate_clues
from .puzzle import Difficulty, Puzzle, PuzzleMetadata
from .validation import MAX_DIMENSION, validate_palette, validate_solution


class EditorDraft:
    def __init__(
        self,
        width: int = 10,
        height: int = 10,
        palette: tuple[str, ...] = ("#3087B9",),
    ) -> None:
        self._check_size(width, height)
        self.width = width
        self.height = height
        self.palette = validate_palette(palette)
        self._grid = [[0] * width for _ in range(height)]
        self._rebuild_clues()

    @classmethod
    def from_solution(
        cls, solution: tuple[tuple[int, ...], ...], palette: tuple[str, ...]
    ) -> "EditorDraft":
        if not solution or not solution[0]:
            raise ValueError("Çözüm boş olamaz")
        height, width = len(solution), len(solution[0])
        checked_palette = validate_palette(palette)
        checked_solution = validate_solution(solution, width, height, len(checked_palette))
        draft = cls(width, height, checked_palette)
        draft._grid = [list(row) for row in checked_solution]
        draft._rebuild_clues()
        return draft

    @staticmethod
    def _check_size(width: int, height: int) -> None:
        if (
            type(width) is not int
            or type(height) is not int
            or not 1 <= width <= MAX_DIMENSION
            or not 1 <= height <= MAX_DIMENSION
        ):
            raise ValueError(f"Izgara boyutları 1–{MAX_DIMENSION} arasında olmalı")

    @property
    def solution(self) -> tuple[tuple[int, ...], ...]:
        return tuple(tuple(row) for row in self._grid)

    @property
    def has_filled_cells(self) -> bool:
        return any(cell for row in self._grid for cell in row)

    def cell_at(self, x: int, y: int) -> int:
        self._check_cell(x, y)
        return self._grid[y][x]

    def _check_cell(self, x: int, y: int) -> None:
        if (
            type(x) is not int
            or type(y) is not int
            or not 0 <= x < self.width
            or not 0 <= y < self.height
        ):
            raise ValueError("Hücre konumu geçersiz")

    def _check_color_id(self, color_id: int) -> None:
        if type(color_id) is not int or not 0 <= color_id <= len(self.palette):
            raise ValueError("Renk kimliği palette yok")

    def _rebuild_clues(self) -> None:
        colored = len(self.palette) > 1
        self.row_clues = tuple(calculate_clues(row, colored=colored) for row in self._grid)
        self.column_clues = tuple(
            calculate_clues((self._grid[y][x] for y in range(self.height)), colored=colored)
            for x in range(self.width)
        )

    def _update_clues(self, rows: set[int], columns: set[int]) -> None:
        colored = len(self.palette) > 1
        row_clues = list(self.row_clues)
        column_clues = list(self.column_clues)
        for y in rows:
            row_clues[y] = calculate_clues(self._grid[y], colored=colored)
        for x in columns:
            column_clues[x] = calculate_clues(
                (self._grid[y][x] for y in range(self.height)), colored=colored
            )
        self.row_clues = tuple(row_clues)
        self.column_clues = tuple(column_clues)

    def set_cell(self, x: int, y: int, color_id: int) -> bool:
        self._check_cell(x, y)
        self._check_color_id(color_id)
        if self._grid[y][x] == color_id:
            return False
        self._grid[y][x] = color_id
        self._update_clues({y}, {x})
        return True

    def flood_fill(self, x: int, y: int, color_id: int) -> int:
        self._check_cell(x, y)
        self._check_color_id(color_id)
        original = self._grid[y][x]
        if original == color_id:
            return 0
        queue = deque(((x, y),))
        self._grid[y][x] = color_id
        changed_rows, changed_columns = {y}, {x}
        count = 0
        while queue:
            cx, cy = queue.popleft()
            count += 1
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if (
                    0 <= nx < self.width
                    and 0 <= ny < self.height
                    and self._grid[ny][nx] == original
                ):
                    self._grid[ny][nx] = color_id
                    changed_rows.add(ny)
                    changed_columns.add(nx)
                    queue.append((nx, ny))
        self._update_clues(changed_rows, changed_columns)
        return count

    def resize(self, width: int, height: int) -> bool:
        self._check_size(width, height)
        if (width, height) == (self.width, self.height):
            return False
        self._grid = [
            (self._grid[y][:width] + [0] * max(0, width - self.width))
            if y < self.height
            else [0] * width
            for y in range(height)
        ]
        self.width, self.height = width, height
        self._rebuild_clues()
        return True

    def clear(self) -> bool:
        if not self.has_filled_cells:
            return False
        self._grid = [[0] * self.width for _ in range(self.height)]
        self._rebuild_clues()
        return True

    def add_color(self, color: str) -> int:
        self.palette = validate_palette((*self.palette, color))
        self._rebuild_clues()
        return len(self.palette)

    def set_palette_color(self, color_id: int, color: str) -> None:
        if type(color_id) is not int or not 1 <= color_id <= len(self.palette):
            raise ValueError("Renk kimliği palette yok")
        updated = list(self.palette)
        updated[color_id - 1] = color
        self.palette = validate_palette(updated)

    def remove_color(self, color_id: int) -> None:
        if len(self.palette) == 1:
            raise ValueError("Son renk kaldırılamaz")
        if type(color_id) is not int or not 1 <= color_id <= len(self.palette):
            raise ValueError("Renk kimliği palette yok")
        self.palette = tuple(
            color for index, color in enumerate(self.palette, 1) if index != color_id
        )
        for row in self._grid:
            for x, cell in enumerate(row):
                row[x] = 0 if cell == color_id else cell - 1 if cell > color_id else cell
        self._rebuild_clues()

    def to_puzzle(
        self,
        *,
        title: str,
        author: str,
        description: str = "",
        difficulty: Difficulty = Difficulty.EASY,
        tags: tuple[str, ...] = (),
        puzzle_id: str | None = None,
    ) -> Puzzle:
        if type(title) is not str or not title.strip():
            raise ValueError("Bulmaca başlığı gerekli")
        if type(author) is not str or not author.strip():
            raise ValueError("Yazar adı gerekli")
        if type(description) is not str:
            raise ValueError("Açıklama metin olmalı")
        if not self.has_filled_cells:
            raise ValueError("En az bir hücre doldurulmalı")
        if (
            type(tags) is not tuple
            or len(tags) > 32
            or any(type(tag) is not str or not 1 <= len(tag) <= 64 for tag in tags)
        ):
            raise ValueError("Etiketler geçersiz")
        return Puzzle(
            id=puzzle_id or f"user-{uuid4().hex}",
            title=title.strip(),
            author=author.strip(),
            description=description.strip(),
            width=self.width,
            height=self.height,
            difficulty=Difficulty(difficulty),
            tags=tags,
            palette=self.palette,
            solution=self.solution,
            row_clues=self.row_clues,
            column_clues=self.column_clues,
            metadata=PuzzleMetadata(source="editor"),
        )
