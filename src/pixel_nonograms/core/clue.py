from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class Clue:
    length: int

    def __post_init__(self) -> None:
        if type(self.length) is not int or self.length < 1:
            raise ValueError("İpucu uzunluğu pozitif tam sayı olmalı")


@dataclass(frozen=True, slots=True)
class ColorClue:
    length: int
    color_id: int

    def __post_init__(self) -> None:
        if type(self.length) is not int or self.length < 1:
            raise ValueError("İpucu uzunluğu pozitif tam sayı olmalı")
        if type(self.color_id) is not int or self.color_id < 1:
            raise ValueError("Renk kimliği pozitif tam sayı olmalı")


def calculate_clues(
    line: Iterable[int], *, colored: bool = False
) -> tuple[Clue, ...] | tuple[ColorClue, ...]:
    """Return runs from 0=empty, 1..N=color IDs; empty line has no clues.

    Adjacent different colors form separate runs without an empty cell between them.
    """
    if type(colored) is not bool:
        raise TypeError("colored bir bool olmalı")
    result: list[Clue | ColorClue] = []
    run_color = 0
    run_length = 0

    def finish_run() -> None:
        nonlocal run_length
        if run_length:
            result.append(ColorClue(run_length, run_color) if colored else Clue(run_length))
            run_length = 0

    for value in line:
        if type(value) is not int or value < 0 or (not colored and value > 1):
            raise ValueError("Çizgi yalnızca geçerli tam sayı hücre değerleri içermeli")
        if value != run_color:
            finish_run()
            run_color = value
        if value:
            run_length += 1
    finish_run()
    return tuple(result)
