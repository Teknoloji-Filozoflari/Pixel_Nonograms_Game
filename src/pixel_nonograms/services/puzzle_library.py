"""Offline puzzle catalog, progress summaries, and query rules."""

import json
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pixel_nonograms.core import CellMark, CellState, Difficulty, Puzzle
from pixel_nonograms.core.compact import compact_puzzle
from pixel_nonograms.persistence import Database, SaveManager

DIFFICULTY_LABELS = {
    Difficulty.EASY: "Kolay",
    Difficulty.MEDIUM: "Orta",
    Difficulty.HARD: "Zor",
    Difficulty.EXPERT: "Uzman",
}
CATEGORIES = ("Tümü", "Başlangıç", "Kolay", "Orta", "Zor", "Uzman", "Renkli")
_DIFFICULTY_ORDER = {
    Difficulty.EASY: 0,
    Difficulty.MEDIUM: 1,
    Difficulty.HARD: 2,
    Difficulty.EXPERT: 3,
}


class PuzzleStatus(StrEnum):
    UNSTARTED = "unstarted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"


class PuzzleSort(StrEnum):
    NAME = "name"
    SIZE = "size"
    DIFFICULTY = "difficulty"
    LAST_PLAYED = "last_played"
    PROGRESS = "progress"


@dataclass(frozen=True, slots=True)
class PuzzleQuery:
    category: str = "Tümü"
    size: tuple[int, int] | None = None
    difficulty: Difficulty | None = None
    color_mode: str = "all"
    status: PuzzleStatus | None = None
    favorites_only: bool = False
    sort: PuzzleSort = PuzzleSort.SIZE


@dataclass(frozen=True, slots=True)
class PuzzleEntry:
    puzzle: Puzzle
    progress: float
    status: PuzzleStatus
    last_played: datetime | None
    favorite: bool
    error: str | None = None
    reward_claimed: bool = False
    preview_cells: tuple[tuple[CellMark, ...], ...] | None = None


class PuzzleLibrary:
    def __init__(
        self, puzzles: tuple[Puzzle, ...], save_manager: SaveManager, database: Database
    ) -> None:
        if not puzzles or any(type(puzzle) is not Puzzle for puzzle in puzzles):
            raise ValueError("Kütüphane en az bir geçerli bulmaca içermeli")
        if len({puzzle.id for puzzle in puzzles}) != len(puzzles):
            raise ValueError("Bulmaca kimlikleri benzersiz olmalı")
        for original in puzzles:
            save_manager.register_original(original)
        puzzles = tuple(compact_puzzle(puzzle)[0] for puzzle in puzzles)
        self._puzzles = {puzzle.id: puzzle for puzzle in puzzles}
        self.save_manager = save_manager
        self.database = database
        database.grant_missing_puzzle_rewards(puzzles)
        history = database.completion_history()
        for puzzle in puzzles:
            if len(puzzle.palette) > 1 and puzzle.id in history and not history[puzzle.id]:
                try:
                    saved = save_manager.load(puzzle)
                except ValueError:
                    continue
                if saved is not None and saved.completed:
                    database.mark_completed_color(puzzle.id)

    @property
    def puzzles(self) -> tuple[Puzzle, ...]:
        return tuple(self._puzzles.values())

    def get(self, puzzle_id: str) -> Puzzle:
        return self._puzzles[puzzle_id]

    def add_puzzle(self, puzzle: Puzzle) -> None:
        if type(puzzle) is not Puzzle:
            raise TypeError("Puzzle gerekli")
        if puzzle.id in self._puzzles:
            raise ValueError("Bulmaca kimliği zaten kütüphanede")
        self.save_manager.register_original(puzzle)
        self._puzzles[puzzle.id] = compact_puzzle(puzzle)[0]

    def set_favorite(self, puzzle_id: str, favorite: bool) -> None:
        self.get(puzzle_id)
        self.database.set_favorite(puzzle_id, favorite)

    def entries(self) -> tuple[PuzzleEntry, ...]:
        favorites = self.database.favorite_ids()
        result = []
        for puzzle in self._puzzles.values():
            reward_claimed = self.database.reward_claimed(puzzle.id)
            try:
                session = self.save_manager.load(puzzle)
            except ValueError as exc:
                result.append(
                    PuzzleEntry(
                        puzzle,
                        0.0,
                        PuzzleStatus.ERROR,
                        None,
                        puzzle.id in favorites,
                        str(exc),
                        reward_claimed,
                    )
                )
                continue
            if session is None:
                result.append(
                    PuzzleEntry(
                        puzzle,
                        0.0,
                        PuzzleStatus.UNSTARTED,
                        None,
                        puzzle.id in favorites,
                        reward_claimed=reward_claimed,
                    )
                )
                continue
            started = (
                session.move_count > 0
                or session.hint_count > 0
                or any(mark.state is not CellState.UNKNOWN for row in session.cells for mark in row)
            )
            status = (
                PuzzleStatus.COMPLETED
                if session.completed
                else PuzzleStatus.IN_PROGRESS
                if started
                else PuzzleStatus.UNSTARTED
            )
            result.append(
                PuzzleEntry(
                    puzzle,
                    session.completion_percentage,
                    status,
                    session.last_played_at if started or session.completed else None,
                    puzzle.id in favorites,
                    reward_claimed=reward_claimed,
                    preview_cells=session.cells,
                )
            )
        return tuple(result)

    def query(self, query: PuzzleQuery = PuzzleQuery()) -> tuple[PuzzleEntry, ...]:
        return self.filter_entries(self.entries(), query)

    @staticmethod
    def filter_entries(entries: tuple[PuzzleEntry, ...], query: PuzzleQuery) -> tuple[PuzzleEntry, ...]:
        if type(query) is not PuzzleQuery or query.category not in CATEGORIES:
            raise ValueError("Geçersiz kütüphane sorgusu")
        if query.color_mode not in {"all", "color", "mono"}:
            raise ValueError("Geçersiz renk filtresi")
        entries = [entry for entry in entries if _matches(entry, query)]
        return tuple(sorted(entries, key=lambda entry: _sort_key(entry, query.sort)))


def _sort_key(entry: PuzzleEntry, sort: PuzzleSort):
    name = entry.puzzle.title.casefold()
    if sort is PuzzleSort.SIZE:
        return (
            entry.puzzle.width * entry.puzzle.height,
            entry.puzzle.width,
            entry.puzzle.height,
            name,
        )
    if sort is PuzzleSort.DIFFICULTY:
        return (_DIFFICULTY_ORDER[entry.puzzle.difficulty], name)
    if sort is PuzzleSort.LAST_PLAYED:
        return (-(entry.last_played.timestamp() if entry.last_played is not None else -1), name)
    if sort is PuzzleSort.PROGRESS:
        return (-entry.progress, name)
    return (name,)


def _matches(entry: PuzzleEntry, query: PuzzleQuery) -> bool:
    puzzle = entry.puzzle
    if query.category == "Başlangıç" and "başlangıç" not in puzzle.tags:
        return False
    if query.category == "Renkli" and not puzzle.is_colored:
        return False
    if (
        query.category in {"Kolay", "Orta", "Zor", "Uzman"}
        and DIFFICULTY_LABELS[puzzle.difficulty] != query.category
    ):
        return False
    return not (
        (query.size is not None and (puzzle.width, puzzle.height) != query.size)
        or (query.difficulty is not None and puzzle.difficulty is not query.difficulty)
        or (query.color_mode == "color" and not puzzle.is_colored)
        or (query.color_mode == "mono" and puzzle.is_colored)
        or (query.status is not None and entry.status is not query.status)
        or (query.favorites_only and not entry.favorite)
    )


def _from_rows(
    puzzle_id: str,
    title: str,
    difficulty: Difficulty,
    rows: tuple[str, ...],
    *,
    tags: tuple[str, ...] = (),
    palette: tuple[str, ...] = ("#3087B9",),
    reward_item_id: str | None = None,
) -> Puzzle:
    return Puzzle(
        id=puzzle_id,
        title=title,
        author="Pixel Nonograms",
        description="Özgün geometrik nonogram bulmacası",
        width=len(rows[0]),
        height=len(rows),
        difficulty=difficulty,
        tags=tags,
        palette=palette,
        solution=tuple(tuple(0 if cell == "." else int(cell) for cell in row) for row in rows),
        reward_item_id=reward_item_id,
    )


def demonstration_puzzle() -> Puzzle:
    return _from_rows(
        "demo-elmas-01",
        "Elmas",
        Difficulty.EASY,
        (
            "....11....",
            "...1111...",
            "..111111..",
            ".11111111.",
            "1111111111",
            "1111111111",
            ".11111111.",
            "..111111..",
            "...1111...",
            "....11....",
        ),
        reward_item_id="analysis_lens",
    )


def built_in_puzzles() -> tuple[Puzzle, ...]:
    first = _from_rows(
        "ilk-adim-01",
        "İlk Adım",
        Difficulty.EASY,
        ("..1..", ".111.", "11111", ".111.", "..1.."),
        tags=("başlangıç",),
        reward_item_id="logic_hint",
    )
    diamond = demonstration_puzzle()

    heart = _from_rows(
        "kalp-10-01",
        "Kalp",
        Difficulty.EASY,
        (
            ".11..11...",
            "11111111..",
            "111111111.",
            "111111111.",
            ".1111111..",
            "..11111...",
            "...111....",
            "....1.....",
            "..........",
            "..........",
        ),
    )

    kite = [["." for _ in range(15)] for _ in range(15)]
    for y in range(1, 11):
        for x in range(1, 14):
            if abs(x - 7) + abs(y - 5) <= 6:
                kite[y][x] = "1" if x <= 7 else "2"
    for y in range(10, 15):
        kite[y][7] = "2"
    color = _from_rows(
        "renkli-ucurtma-15-01",
        "Renkli Uçurtma",
        Difficulty.MEDIUM,
        tuple("".join(row) for row in kite),
        palette=("#C97550", "#478DA1"),
        reward_item_id="column_scanner",
    )

    tulip = [["." for _ in range(17)] for _ in range(17)]
    for y in range(2, 9):
        half_width = (2, 4, 5, 5, 4, 3, 2)[y - 2]
        for x in range(8 - half_width, 9 + half_width):
            tulip[y][x] = "1"
    for y in range(8, 17):
        tulip[y][8] = "1"
    for y in range(11, 15):
        for x in range(9, 14):
            if abs(x - 10) + abs(y - 13) <= 3:
                tulip[y][x] = "1"
    medium = _from_rows(
        "lale-17-01", "Lale", Difficulty.MEDIUM,
        tuple("".join(row) for row in tulip)
    )

    cap = [["." for _ in range(20)] for _ in range(20)]
    for center, apex, half_width in ((4, 5, 3), (10, 2, 4), (16, 6, 2)):
        for y in range(apex, 18):
            spread = min(half_width, (y - apex) // 3)
            for x in range(max(0, center - spread), min(20, center + spread + 1)):
                cap[y][x] = "1"
    for x in range(20):
        cap[18][x] = "1"
    cappadocia = _from_rows(
        "kapadokya-01",
        "Kapadokya",
        Difficulty.MEDIUM,
        tuple("".join(row) for row in cap),
        reward_item_id="row_scanner",
    )

    lighthouse = [["." for _ in range(25)] for _ in range(25)]
    for y in range(4, 22):
        span = 3 if y > 13 else 2
        for x in range(12 - span, 13 + span):
            lighthouse[y][x] = "1"
    for y in (3, 8, 14, 21):
        for x in range(7, 18):
            lighthouse[y][x] = "1"
    for y in (22, 24):
        for x in range(25):
            if (x + y) % 5 != 0:
                lighthouse[y][x] = "1"
    hard = _from_rows(
        "deniz-feneri-01",
        "Deniz Feneri",
        Difficulty.HARD,
        tuple("".join(row) for row in lighthouse),
        reward_item_id="error_check",
    )

    sailboat = [["." for _ in range(27)] for _ in range(27)]
    for y in range(3, 20):
        sailboat[y][13] = "1"
        for x in range(max(3, 13 - (y - 2) // 2), 13):
            sailboat[y][x] = "1"
        for x in range(14, min(24, 14 + (y - 3) // 3)):
            sailboat[y][x] = "1"
    for y in range(20, 24):
        for x in range(4 + y - 20, 23 - (y - 20)):
            sailboat[y][x] = "1"
    for x in range(27):
        sailboat[24][x] = "1"
    hard_sail = _from_rows(
        "yelkenli-27-01", "Yelkenli", Difficulty.HARD,
        tuple("".join(row) for row in sailboat)
    )

    castle = [["." for _ in range(30)] for _ in range(30)]
    for y in range(7, 26):
        for x in range(4, 26):
            if 11 <= y <= 25 and 7 <= x <= 22:
                castle[y][x] = "1"
            if (4 <= x <= 8 or 21 <= x <= 25) and y >= 7:
                castle[y][x] = "1"
    for x in range(4, 26, 3):
        for y in range(5, 8):
            castle[y][x] = "1"
    for y in range(19, 26):
        for x in range(13, 17):
            castle[y][x] = "."
    for x in range(30):
        castle[27][x] = "1"
    hard_castle = _from_rows(
        "kale-30-01", "Kale", Difficulty.HARD,
        tuple("".join(row) for row in castle)
    )

    mosaic = tuple(
        "".join(
            "1"
            if x in (0, 5, 11, 17, 23, 29)
            or y in (0, 7, 15, 22, 29)
            or abs((x % 10) - 5) + abs((y % 10) - 5) <= 4
            else "."
            for x in range(30)
        )
        for y in range(30)
    )
    expert = _from_rows(
        "mozaik-01", "Mozaik", Difficulty.EXPERT, mosaic, reward_item_id="second_look"
    )

    starfield = tuple(
        "".join(
            "1" if x in (0, 8, 16, 24, 32, 39)
            or y in (0, 9, 19, 29, 39)
            or abs(x - 20) + abs(y - 20) < 8
            or (x % 9 == 4 and y % 8 == 4)
            else "."
            for x in range(40)
        )
        for y in range(40)
    )
    expert_star = _from_rows(
        "yildiz-haritasi-40-01", "Yıldız Haritası", Difficulty.EXPERT,
        starfield
    )

    flower = tuple(
        "".join(
            "1" if x in (0, 10, 20, 30, 40, 49)
            or y in (0, 10, 20, 30, 40, 49)
            or abs(x - 25) + abs(y - 24) < 9
            or min(
                abs(x - 13) + abs(y - 13),
                abs(x - 37) + abs(y - 13),
                abs(x - 13) + abs(y - 37),
                abs(x - 37) + abs(y - 37),
            ) < 6
            else "."
            for x in range(50)
        )
        for y in range(50)
    )
    expert_flower = _from_rows(
        "buyuk-cicek-50-01", "Büyük Çiçek", Difficulty.EXPERT,
        flower
    )
    flower_easy = _from_rows(
        "renkli-cicek-05-01", "Minik Çiçek", Difficulty.EASY,
        (".111.", "11211", ".111.", "..3..", ".333."),
        palette=("#C64E68", "#E2AD36", "#38876A"),
        tags=("başlangıç", "renkli"), reward_item_id="logic_hint",
    )
    house_easy = _from_rows(
        "renkli-ev-07-01", "Renkli Ev", Difficulty.EASY,
        ("...1...", "..111..", ".11111.", "1111111", ".22222.", ".23332.", ".23332."),
        palette=("#C56243", "#E0B65C", "#427FA0"),
        tags=("başlangıç", "renkli"), reward_item_id="row_scanner",
    )
    original = (
        first, diamond, heart, flower_easy, house_easy,
        color, medium, cappadocia,
        hard, hard_sail, hard_castle,
        expert, expert_star, expert_flower,
    )
    records = json.loads(
        (Path(__file__).resolve().parents[1] / "catalog_expansion.json").read_text(encoding="utf-8")
    )
    records += json.loads(
        (Path(__file__).resolve().parents[1] / "catalog_extended.json").read_text(encoding="utf-8")
    )
    additions = tuple(
        _from_rows(record["id"], record["title"], Difficulty(record["difficulty"]),
                   tuple(record["rows"]), palette=tuple(record["palette"]))
        for record in records
    )
    packaged = []
    for puzzle in original + additions:
        size = 10 if puzzle.difficulty is Difficulty.EASY and puzzle.width == 7 else puzzle.width
        solution = tuple(
            tuple(puzzle.solution[y][x] if y < puzzle.height and x < puzzle.width else 0
                  for x in range(size)) for y in range(size)
        )
        packaged.append(replace(
            puzzle, width=size, height=size, solution=solution,
            row_clues=None, column_clues=None, tags=(*puzzle.tags, "packaged-grid"),
        ))
    return tuple(packaged)
