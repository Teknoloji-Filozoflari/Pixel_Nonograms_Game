"""Reversible, immutable changes to a player's marks."""

from dataclasses import dataclass

from .cell import CellState


@dataclass(frozen=True, slots=True)
class CellMark:
    state: CellState = CellState.UNKNOWN
    color_id: int = 0

    def __post_init__(self) -> None:
        if type(self.state) is not CellState:
            raise ValueError("Geçersiz hücre durumu")
        if type(self.color_id) is not int or self.color_id < 0:
            raise ValueError("Geçersiz renk kimliği")
        if self.state is CellState.FILLED and self.color_id < 1:
            raise ValueError("Dolu hücrenin renk kimliği olmalı")
        if self.state is not CellState.FILLED and self.color_id != 0:
            raise ValueError("Boş veya bilinmeyen hücrenin rengi olamaz")


@dataclass(frozen=True, slots=True)
class CellChangeCommand:
    x: int
    y: int
    before: CellMark
    after: CellMark

    def __post_init__(self) -> None:
        if type(self.x) is not int or type(self.y) is not int or self.x < 0 or self.y < 0:
            raise ValueError("Hücre koordinatı negatif olmayan tam sayı olmalı")
        if type(self.before) is not CellMark or type(self.after) is not CellMark:
            raise ValueError("Komut geçerli hücre işaretleri içermeli")
        if self.before == self.after:
            raise ValueError("Komut hücreyi değiştirmeli")

    @property
    def changes(self) -> tuple["CellChangeCommand", ...]:
        return (self,)


@dataclass(frozen=True, slots=True)
class MultiCellChangeCommand:
    changes: tuple[CellChangeCommand, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.changes, tuple) or not self.changes:
            raise ValueError("Çoklu komut en az bir değişiklik içermeli")
        if any(type(change) is not CellChangeCommand for change in self.changes):
            raise ValueError("Çoklu komut yalnızca hücre değişiklikleri içermeli")
        positions = {(change.x, change.y) for change in self.changes}
        if len(positions) != len(self.changes):
            raise ValueError("Aynı hücre bir komutta iki kez değiştirilemez")


@dataclass(frozen=True, slots=True)
class ClueChangeCommand:
    axis: str
    line_index: int
    clue_index: int
    before: bool
    after: bool
    changes: tuple[CellChangeCommand, ...] = ()

    def __post_init__(self) -> None:
        if self.axis not in {"row", "column"}:
            raise ValueError("İpucu ekseni geçersiz")
        if any(type(value) is not int or value < 0 for value in (self.line_index, self.clue_index)):
            raise ValueError("İpucu koordinatı geçersiz")
        if type(self.before) is not bool or type(self.after) is not bool or self.before == self.after:
            raise ValueError("İpucu durumu değişmeli")
        if any(type(change) is not CellChangeCommand for change in self.changes):
            raise ValueError("İpucu komutu geçersiz hücre değişikliği içeriyor")


Command = CellChangeCommand | MultiCellChangeCommand | ClueChangeCommand
