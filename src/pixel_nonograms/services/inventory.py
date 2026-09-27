"""Optional puzzle aids; deterministic outcomes and SQLite-backed balances."""

from dataclasses import dataclass
from time import monotonic

from pixel_nonograms.core import CellMark, CellState, GameSession, HelperItemId, LineStatus
from pixel_nonograms.core.analysis import analyze_board
from pixel_nonograms.persistence.database import Database, OutOfStockError
from pixel_nonograms.persistence.save_manager import SaveManager
from pixel_nonograms.solver import HintPlan, create_hint_plan

ITEM_NAMES = {
    HelperItemId.ANALYSIS_LENS: "Analiz Merceği",
    HelperItemId.LOGIC_HINT: "Mantık İpucu",
    HelperItemId.ERROR_CHECK: "Hata Kontrolü",
    HelperItemId.ROW_SCANNER: "Satır Tarayıcı",
    HelperItemId.COLUMN_SCANNER: "Sütun Tarayıcı",
    HelperItemId.SECOND_LOOK: "İkinci Bakış",
}
_STATUS_NAMES = {
    LineStatus.UNRESOLVED: "Henüz işaret yok",
    LineStatus.VALID_SO_FAR: "Şimdilik geçerli",
    LineStatus.COMPLETED: "Tamamlandı",
    LineStatus.CONTRADICTION: "Çelişki var",
}


@dataclass(frozen=True, slots=True)
class AidResult:
    item_id: HelperItemId
    message: str
    cells: tuple[tuple[int, int, CellMark], ...] = ()
    axis: str | None = None
    line_index: int | None = None
    hint_plan: HintPlan | None = None


class InventoryService:
    def __init__(self, database: Database, save_manager: SaveManager) -> None:
        if save_manager.database is not database:
            raise ValueError("Envanter ve kayıt aynı veritabanını kullanmalı")
        self.database = database
        self.save_manager = save_manager

    def counts(self) -> dict[HelperItemId, int]:
        return self.database.inventory_counts()

    def use(
        self,
        item_id: HelperItemId,
        session: GameSession,
        *,
        axis: str | None = None,
        line_index: int | None = None,
    ) -> AidResult | None:
        """Return an explanation, consuming one item only when it can help.

        None means no useful result and never costs an item. Aids do not alter the grid.
        """
        item_id = HelperItemId(item_id)
        if type(session) is not GameSession:
            raise TypeError("GameSession gerekli")
        if session.assumption_active:
            raise RuntimeError("Deneme Modunda yardımcı öğe kullanılamaz")
        session.snapshot()  # Reject an active drag before computing or consuming.
        if session.completed:
            return None
        if self.database.item_count(item_id) < 1:
            raise OutOfStockError("Yardımcı öğe envanterde yok")
        result = self._calculate(item_id, session, axis, line_index)
        if result is None:
            return None
        session.record_hint()
        try:
            if not self.save_manager.save(session, consume_item_id=item_id):
                raise RuntimeError("Sürükleme sürerken yardımcı öğe kullanılamaz")
        except Exception:
            session.hint_count -= 1
            raise
        return result

    def _calculate(
        self, item_id: HelperItemId, session: GameSession, axis: str | None, line_index: int | None
    ) -> AidResult | None:
        puzzle, cells = session.puzzle, session.cells
        if item_id is HelperItemId.LOGIC_HINT:
            plan = create_hint_plan(puzzle, cells, timeout_seconds=2.0)
            if plan is None:
                return None
            step = plan.step(1)
            return AidResult(
                item_id,
                step.message,
                axis=step.axis,
                line_index=step.line_index,
                hint_plan=plan,
            )
        if item_id is HelperItemId.ERROR_CHECK:
            for y, row in enumerate(cells):
                for x, mark in enumerate(row):
                    answer = puzzle.solution[y][x]
                    wrong = (mark.state is CellState.FILLED and mark.color_id != answer) or (
                        mark.state is CellState.EMPTY and answer != 0
                    )
                    if wrong:
                        return AidResult(
                            item_id,
                            f"({x + 1}, {y + 1}) işareti çözümle uyuşmuyor. Bu hücreyi yeniden inceleyin.",
                            ((x, y, mark),),
                        )
            return None

        deadline = monotonic() + 2.0

        def check_limit() -> None:
            if monotonic() >= deadline:
                raise TimeoutError("Yardımcı analiz zaman sınırına ulaştı")

        analysis = analyze_board(puzzle, cells, check_limit=check_limit)
        if item_id is HelperItemId.SECOND_LOOK:
            for selected_axis, lines in (("row", analysis.rows), ("column", analysis.columns)):
                for index, line in enumerate(lines):
                    if line.status is LineStatus.CONTRADICTION:
                        name = "satır" if selected_axis == "row" else "sütun"
                        return AidResult(
                            item_id,
                            f"{index + 1}. {name} ipuçlarıyla çelişiyor. İşaretleri yeniden inceleyin.",
                            axis=selected_axis,
                            line_index=index,
                        )
            return None

        selected_axis = (
            "row"
            if item_id is HelperItemId.ROW_SCANNER
            else ("column" if item_id is HelperItemId.COLUMN_SCANNER else axis)
        )
        if selected_axis not in ("row", "column"):
            raise ValueError("Satır veya sütun seçilmeli")
        lines = analysis.rows if selected_axis == "row" else analysis.columns
        if type(line_index) is not int or not 0 <= line_index < len(lines):
            raise ValueError("Çizgi numarası geçersiz")
        line = lines[line_index]
        name = "satır" if selected_axis == "row" else "sütun"
        if item_id is HelperItemId.ANALYSIS_LENS:
            return AidResult(
                item_id,
                f"{line_index + 1}. {name}: {_STATUS_NAMES[line.status]}; "
                f"{line.possibility_count} olası yerleşim.",
                axis=selected_axis,
                line_index=line_index,
            )
        if line.status is LineStatus.CONTRADICTION:
            return None
        forced = []
        for offset, mark in enumerate(line.forced_cells):
            x, y = (offset, line_index) if selected_axis == "row" else (line_index, offset)
            if mark is not None and cells[y][x].state is CellState.UNKNOWN:
                forced.append((x, y, mark))
            if len(forced) == 3:
                break
        if not forced:
            return None
        descriptions = [
            f"({x + 1}, {y + 1}) {'X' if mark.state is CellState.EMPTY else f'renk {mark.color_id}'}"
            for x, y, mark in forced
        ]
        return AidResult(
            item_id,
            f"{line_index + 1}. {name} kesin hücreler: " + ", ".join(descriptions),
            tuple(forced),
            selected_axis,
            line_index,
        )
