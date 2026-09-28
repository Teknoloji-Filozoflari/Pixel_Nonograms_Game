"""Solution-backed helpers with atomic saves and reversible board edits.

Persisted IDs are retained so existing inventory and rewards remain valid.
"""
from copy import deepcopy
from dataclasses import dataclass

from pixel_nonograms.core import CellMark, CellState, GameSession, HelperItemId
from pixel_nonograms.core.commands import CellChangeCommand, MultiCellChangeCommand
from pixel_nonograms.persistence.database import Database, OutOfStockError
from pixel_nonograms.persistence.save_manager import SaveManager

ITEM_NAMES = {
    HelperItemId.ROW_SCANNER: "Satır / Sütun Çözücü",
    HelperItemId.ANALYSIS_LENS: "Akıllı Düzeltme",
    HelperItemId.LOGIC_HINT: "3×3 Alan Çözücü",
    HelperItemId.ERROR_CHECK: "5×5 Alan Çözücü",
    HelperItemId.COLUMN_SCANNER: "Beş Hücre",
    HelperItemId.SECOND_LOOK: "10×10 Alan Çözücü",
}
AREA_SIZES = {HelperItemId.LOGIC_HINT: 3, HelperItemId.ERROR_CHECK: 5,
              HelperItemId.SECOND_LOOK: 10}


@dataclass(frozen=True, slots=True)
class AidResult:
    item_id: HelperItemId
    message: str
    cells: tuple[tuple[int, int, CellMark], ...] = ()
    axis: str | None = None
    line_index: int | None = None
    hint_plan: object = None
    corrected_cell: tuple[int, int] | None = None


class InventoryService:
    def __init__(self, database: Database, save_manager: SaveManager):
        if save_manager.database is not database:
            raise ValueError("Envanter ve kayıt aynı veritabanını kullanmalı")
        self.database, self.save_manager = database, save_manager

    def counts(self):
        return self.database.inventory_counts()

    def use(self, item_id, session, *, axis=None, line_index=None, origin=None):
        item_id = HelperItemId(item_id)
        if item_id is HelperItemId.COLUMN_SCANNER:
            raise ValueError("Bu ipucu kaldırıldı")
        if type(session) is not GameSession:
            raise TypeError("GameSession gerekli")
        if session.assumption_active:
            raise RuntimeError("Deneme Modunda yardımcı öğe kullanılamaz")
        session.snapshot()
        if session.completed:
            return None
        if self.database.item_count(item_id) < 1:
            raise OutOfStockError("Yardımcı öğe envanterde yok")
        result = self._calculate(item_id, session, axis, line_index, origin)
        if result is None:
            return None
        # Build on an isolated session, committing in-memory history only after SQLite succeeds.
        candidate = deepcopy(session)
        changes = tuple(CellChangeCommand(x, y, session.cell_at(x, y), mark)
                        for x, y, mark in result.cells)
        automatic = candidate.auto_x_completed_lines
        candidate.auto_x_completed_lines = False  # Do not change cells outside the requested area.
        candidate.execute(MultiCellChangeCommand(changes))
        candidate.auto_x_completed_lines = automatic
        candidate.record_hint()
        if not self.save_manager.save(candidate, consume_item_id=item_id):
            raise RuntimeError("Yardım kaydedilemedi")
        session.__dict__.update(candidate.__dict__)
        return result

    def _calculate(self, item_id, session, axis, line_index, origin):
        puzzle = session.puzzle
        width, height = puzzle.width, puzzle.height

        def answer(x, y):
            color = puzzle.solution[y][x]
            return CellMark(CellState.FILLED, color) if color else CellMark(CellState.EMPTY)

        def differs(x, y):
            mark, target = session.cell_at(x, y), answer(x, y)
            return (mark.state, mark.color_id) != (target.state, target.color_id)

        positions = []
        corrected = None
        if item_id is HelperItemId.ROW_SCANNER:
            if axis not in ('row', 'column'):
                raise ValueError("Satır veya sütun seçilmeli")
            limit = height if axis == 'row' else width
            if type(line_index) is not int or not 0 <= line_index < limit:
                raise ValueError("Çizgi numarası geçersiz")
            positions = ([(x, line_index) for x in range(width)] if axis == 'row'
                         else [(line_index, y) for y in range(height)])
        elif item_id in AREA_SIZES:
            side = AREA_SIZES[item_id]
            w, h = min(side, width), min(side, height)
            if (not isinstance(origin, tuple) or len(origin) != 2
                    or any(type(value) is not int for value in origin)
                    or not 0 <= origin[0] < width or not 0 <= origin[1] < height):
                raise ValueError("Alan için başlangıç hücresi seçilmeli")
            x0, y0 = min(origin[0], width-w), min(origin[1], height-h)
            positions = [(x,y) for y in range(y0,y0+h) for x in range(x0,x0+w)]
        else:
            if item_id is HelperItemId.ANALYSIS_LENS:
                corrected = next(((x,y) for y in range(height) for x in range(width)
                                  if session.cell_at(x,y).state is CellState.FILLED
                                  and differs(x,y)), None)
            if corrected is not None:
                positions = [corrected]
            else:
                candidates = [(x,y) for y in range(height) for x in range(width)
                              if puzzle.solution[y][x] and differs(x,y)]
                # Prefer cells in lines closest to completion to unlock further deductions.
                row_left = [sum(differs(x,y) for x in range(width)) for y in range(height)]
                col_left = [sum(differs(x,y) for y in range(height)) for x in range(width)]
                candidates.sort(key=lambda p: (min(row_left[p[1]], col_left[p[0]]),
                                               row_left[p[1]]+col_left[p[0]],p[1],p[0]))
                positions = candidates[:1]
        changes = tuple((x,y,answer(x,y)) for x,y in positions if differs(x,y))
        if not changes:
            return None
        return AidResult(item_id, f"{len(changes)} hücre çözümlendi.", changes,
                         axis, line_index, corrected_cell=corrected)
