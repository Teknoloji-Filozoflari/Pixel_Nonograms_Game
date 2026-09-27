"""One QPainter canvas for the grid and both clue bands."""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QImage,
    QMouseEvent,
    QPainter,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from pixel_nonograms.core import CellState, GameSession, analyze_board
from pixel_nonograms.ui.theme import BOARD, CLUE, INK, PAPER

from .camera import Camera


def _stroke_cells(start: tuple[int, int], end: tuple[int, int]):
    """Interpolate a fast mouse move so it cannot skip grid cells."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    steps = max(abs(dx), abs(dy))
    if steps == 0:
        yield end
        return
    previous = None
    for index in range(steps + 1):
        cell = (round(start[0] + dx * index / steps), round(start[1] + dy * index / steps))
        if cell != previous:
            yield cell
            previous = cell


class BoardWidget(QWidget):
    session_changed = Signal()
    view_changed = Signal()
    active_clues_changed = Signal(str)

    def __init__(self, session: GameSession, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.display_width, self.display_height = self._display_dimensions()
        self.camera = Camera()
        self.tool = "fill"
        self.color_id = 1
        self.hover: tuple[int, int] | None = None
        self._hint_row: int | None = None
        self._hint_column: int | None = None
        self._hint_cell: tuple[int, int] | None = None
        self._stroke_active = False
        self._stroke_tool = "fill"
        self._stroke_erase_fill = False
        self._last_cell: tuple[int, int] | None = None
        self._pan_active = False
        self._pan_anchor = QPointF()
        self._space_down = False
        self._first_resize = True
        self.row_clue_offset = 0
        self.column_clue_offset = 0
        self._analysis = analyze_board(session.puzzle, session.cells)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(120, 120)

    def _display_dimensions(self) -> tuple[int, int]:
        """Trim only unused trailing cells past the last complete five-cell block."""
        puzzle = self.session.puzzle
        cells = self.session.cells

        def required_width() -> int:
            return max(
                (x + 1 for y in range(puzzle.height) for x in range(puzzle.width)
                 if puzzle.solution[y][x] or cells[y][x].state is not CellState.UNKNOWN),
                default=1,
            )

        def required_height() -> int:
            return max(
                (y + 1 for y in range(puzzle.height)
                 if any(puzzle.solution[y])
                 or any(mark.state is not CellState.UNKNOWN for mark in cells[y])),
                default=1,
            )

        width = puzzle.width if puzzle.width <= 5 or puzzle.width % 5 == 0 else max(
            (puzzle.width // 5) * 5, required_width()
        )
        height = puzzle.height if puzzle.height <= 5 or puzzle.height % 5 == 0 else max(
            (puzzle.height // 5) * 5, required_height()
        )
        return width, height

    def _clue_bands(self) -> tuple[float, float]:
        puzzle = self.session.puzzle
        row_depth = max((len(clues) for clues in puzzle.row_clues[:self.display_height]), default=0)
        column_depth = max((len(clues) for clues in puzzle.column_clues[:self.display_width]), default=0)
        left = min(max(56, 18 + row_depth * 24), 180)
        top = min(max(52, 18 + column_depth * 24), 140)
        return left, top

    def grid_viewport(self) -> QRectF:
        left, top = self._clue_bands()
        return QRectF(left, top, max(1, self.width() - left - 12), max(1, self.height() - top - 12))

    def fit_to_screen(self) -> None:
        self.camera.fit(self.grid_viewport(), self.display_width, self.display_height)
        self.update()
        self.view_changed.emit()

    def zoom(self, factor: float, point: QPointF | None = None) -> None:
        viewport = self.grid_viewport()
        center = point or viewport.center()
        self.camera.zoom_at(center, factor, viewport,
                            self.display_width, self.display_height)
        self.update()
        self.view_changed.emit()

    def set_tool(self, tool: str) -> None:
        if tool not in {"fill", "empty", "clear", "pan"}:
            raise ValueError("Bilinmeyen araç")
        self.tool = tool
        self.setCursor(Qt.CursorShape.OpenHandCursor if tool == "pan" else Qt.CursorShape.ArrowCursor)

    def set_color(self, color_id: int) -> None:
        if type(color_id) is not int or not 1 <= color_id <= len(self.session.puzzle.palette):
            raise ValueError("Renk palette yok")
        self.color_id = color_id

    def set_hint_highlight(
        self,
        *,
        row: int | None = None,
        column: int | None = None,
        cell: tuple[int, int] | None = None,
    ) -> None:
        puzzle = self.session.puzzle
        if row is not None and (type(row) is not int or not 0 <= row < puzzle.height):
            raise ValueError("İpucu satırı geçersiz")
        if column is not None and (type(column) is not int or not 0 <= column < puzzle.width):
            raise ValueError("İpucu sütunu geçersiz")
        if cell is not None and (
            type(cell) is not tuple
            or len(cell) != 2
            or type(cell[0]) is not int
            or type(cell[1]) is not int
            or not 0 <= cell[0] < puzzle.width
            or not 0 <= cell[1] < puzzle.height
        ):
            raise ValueError("İpucu hücresi geçersiz")
        self._hint_row, self._hint_column, self._hint_cell = row, column, cell
        self.update()

    def begin_assumption(self) -> None:
        if self._stroke_active:
            self._finish_stroke()
        self.session.begin_assumption()
        self.refresh_session()

    def accept_assumption(self) -> None:
        if self._stroke_active:
            self._finish_stroke()
        self.session.accept_assumption()
        self.refresh_session()

    def cancel_assumption(self) -> None:
        if self._stroke_active:
            self._finish_stroke()
        self.session.cancel_assumption()
        self.refresh_session()

    def undo(self) -> None:
        if self._stroke_active:
            self._finish_stroke()
        if self.session.undo():
            self._refresh_clue_analysis()
            self.update()
            self.session_changed.emit()

    def redo(self) -> None:
        if self._stroke_active:
            self._finish_stroke()
        if self.session.redo():
            self._refresh_clue_analysis()
            self.update()
            self.session_changed.emit()

    def clear_hovered_cell(self) -> None:
        if self.hover is None:
            return
        if self.session.clear_cell(*self.hover):
            self._refresh_clue_analysis()
            self.update()
            self.session_changed.emit()

    def _refresh_clue_analysis(self) -> None:
        self._analysis = analyze_board(self.session.puzzle, self.session.cells)

    def refresh_session(self) -> None:
        """Refresh board state after an external session action, such as an assist setting."""
        self._refresh_clue_analysis()
        self.update()
        self.session_changed.emit()

    def finish_active_stroke(self) -> None:
        """Commit an in-progress drag before a final save."""
        self._finish_stroke()

    def _clue_edges(self, viewport: QRectF) -> tuple[float, float]:
        return (
            viewport.left() + max(0.0, self.camera.pan_x),
            viewport.top() + max(0.0, self.camera.pan_y),
        )

    @staticmethod
    def _clue_capacity(edge: float) -> int:
        return max(2, int((edge - 8) // 20))

    @staticmethod
    def _visible_clue_indices(count: int, capacity: int, offset: int) -> tuple[int, ...]:
        visible_count = capacity - 1 if count > capacity else capacity
        start = min(max(0, offset), max(0, count - visible_count))
        return tuple(range(count - 1 - start, max(-1, count - 1 - start - visible_count), -1))

    def _active_clue_text(self) -> str:
        if self.hover is None:
            return "Aktif hücrenin satır ve sütun ipuçları burada görünür."
        x, y = self.hover
        puzzle = self.session.puzzle

        def format_clues(clues) -> str:
            if not clues:
                return "0"
            return "  ".join(
                f"{clue.length} ({clue.color_id})" if puzzle.is_colored else str(clue.length)
                for clue in clues
            )

        return (
            f"Satır {y + 1}: {format_clues(puzzle.row_clues[y])}   ·   "
            f"Sütun {x + 1}: {format_clues(puzzle.column_clues[x])}"
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._first_resize:
            self._first_resize = False
            self.fit_to_screen()
        else:
            self.camera.constrain(self.grid_viewport(), self.display_width, self.display_height)
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), PAPER)
        viewport = self.grid_viewport()
        row_edge, column_edge = self._clue_edges(viewport)
        row_band_left = row_edge - viewport.left()
        column_band_top = column_edge - viewport.top()
        board_right = min(
            viewport.right(),
            row_edge + self.display_width * self.camera.cell_size,
        )
        board_bottom = min(
            viewport.bottom(),
            column_edge + self.display_height * self.camera.cell_size,
        )
        painter.fillRect(
            QRectF(row_edge, column_band_top, board_right - row_edge, viewport.top()), CLUE
        )
        painter.fillRect(
            QRectF(row_band_left, column_edge, viewport.left(), board_bottom - column_edge), CLUE
        )
        painter.fillRect(QRectF(0, 0, viewport.left(), viewport.top()), QColor("#2B3039"))
        self._paint_marked_overview(painter, viewport)
        self._paint_grid(painter, viewport)
        self._paint_clues(painter, viewport)
        self._paint_overfilled_lines(painter, viewport)
        painter.end()

    def _marked_overview_rect(self, viewport: QRectF) -> QRectF:
        """Keep the progress miniature inside the fixed top-left clue corner."""
        available_width = max(1.0, viewport.left() - 14)
        available_height = max(1.0, viewport.top() - 14)
        scale = min(available_width / self.display_width,
                    available_height / self.display_height)
        width, height = self.display_width * scale, self.display_height * scale
        return QRectF((viewport.left() - width) / 2, (viewport.top() - height) / 2,
                      width, height)

    def _paint_marked_overview(self, painter: QPainter, viewport: QRectF) -> None:
        """Show only the player's filled cells, never the hidden solution."""
        puzzle = self.session.puzzle
        image = QImage(self.display_width, self.display_height, QImage.Format.Format_RGB32)
        image.fill(BOARD)
        for y, row in enumerate(self.session.cells[:self.display_height]):
            for x, mark in enumerate(row[:self.display_width]):
                if mark.state is CellState.FILLED:
                    color = QColor(puzzle.palette[mark.color_id - 1]) if puzzle.is_colored else INK
                    image.setPixelColor(x, y, color)
        target = self._marked_overview_rect(viewport)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(target, image)
        painter.setPen(QPen(QColor("#8F7955"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(target)
        painter.restore()

    def _overfilled_lines(self) -> tuple[tuple[int, ...], tuple[int, ...]]:
        puzzle = self.session.puzzle
        cells = self.session.cells
        rows = tuple(
            y for y, row in enumerate(cells[:self.display_height])
            if sum(mark.state is CellState.FILLED for mark in row)
            > sum(clue.length for clue in puzzle.row_clues[y])
        )
        columns = tuple(
            x for x in range(self.display_width)
            if sum(cells[y][x].state is CellState.FILLED for y in range(self.display_height))
            > sum(clue.length for clue in puzzle.column_clues[x])
        )
        return rows, columns

    def _paint_overfilled_lines(self, painter: QPainter, viewport: QRectF) -> None:
        rows, columns = self._overfilled_lines()
        if not rows and not columns:
            return
        painter.save()
        painter.setClipRect(QRectF(0, 0, viewport.right(), viewport.bottom()))
        painter.setBrush(QColor(226, 63, 75, 38))
        painter.setPen(QPen(QColor("#D63740"), 2.5))
        for y in rows:
            painter.drawRect(self._warning_row_rect(y, viewport))
        for x in columns:
            painter.drawRect(self._warning_column_rect(x, viewport))
        painter.restore()

    def _warning_row_rect(self, y: int, viewport: QRectF) -> QRectF:
        row_edge, _ = self._clue_edges(viewport)
        capacity = self._clue_capacity(viewport.left())
        slot = min(26.0, (viewport.left() - 8) / capacity)
        count = len(self.session.puzzle.row_clues[y])
        visible = self._visible_clue_indices(count, capacity, self.row_clue_offset)
        slots = max(1, len(visible) + int(count > len(visible)))
        left = max(row_edge - viewport.left(), row_edge - 8 - slots * slot)
        top = self.camera.cell_origin(0, y, viewport).y()
        board_right = viewport.left() + self.camera.pan_x + self.display_width * self.camera.cell_size
        right = min(viewport.right(), max(row_edge, board_right))
        return QRectF(left + 2, top + 2, max(1, right - left - 4),
                      max(1, self.camera.cell_size - 4))

    def _warning_column_rect(self, x: int, viewport: QRectF) -> QRectF:
        _, column_edge = self._clue_edges(viewport)
        capacity = self._clue_capacity(viewport.top())
        slot = min(26.0, (viewport.top() - 8) / capacity)
        count = len(self.session.puzzle.column_clues[x])
        visible = self._visible_clue_indices(count, capacity, self.column_clue_offset)
        slots = max(1, len(visible) + int(count > len(visible)))
        top = max(column_edge - viewport.top(), column_edge - 8 - slots * slot)
        left = self.camera.cell_origin(x, 0, viewport).x()
        board_bottom = viewport.top() + self.camera.pan_y + self.display_height * self.camera.cell_size
        bottom = min(viewport.bottom(), max(column_edge, board_bottom))
        return QRectF(left + 2, top + 2, max(1, self.camera.cell_size - 4),
                      max(1, bottom - top - 4))

    def _paint_grid(self, painter: QPainter, viewport: QRectF) -> None:
        puzzle = self.session.puzzle
        camera = self.camera
        size = camera.cell_size
        x0, y0, x1, y1 = camera.visible_cells(viewport, self.display_width, self.display_height)
        board_left = viewport.left() + camera.pan_x
        board_top = viewport.top() + camera.pan_y
        board_right = board_left + self.display_width * size
        board_bottom = board_top + self.display_height * size
        painter.save()
        painter.setClipRect(viewport)
        painter.fillRect(
            QRectF(board_left, board_top, self.display_width * size, self.display_height * size),
            BOARD,
        )
        for y in range(y0, y1):
            for x in range(x0, x1):
                origin = camera.cell_origin(x, y, viewport)
                rect = QRectF(origin.x(), origin.y(), size, size)
                mark = self.session.cell_at(x, y)
                if mark.state is CellState.FILLED:
                    painter.fillRect(
                        rect.adjusted(0.8, 0.8, -0.8, -0.8),
                        QColor(puzzle.palette[mark.color_id - 1]) if puzzle.is_colored else INK,
                    )
                elif (x // 5 + y // 5) % 2:
                    painter.fillRect(rect, QColor("#26313A"))
                if self.hover is not None and (x == self.hover[0] or y == self.hover[1]):
                    painter.fillRect(rect, QColor(207, 169, 82, 32))
                if y == self._hint_row or x == self._hint_column:
                    painter.fillRect(rect, QColor(255, 196, 76, 54))
                if self.session.is_assumption_cell(x, y):
                    if size < 7:
                        painter.fillRect(rect, QColor(245, 169, 48, 170))
                    else:
                        painter.fillRect(rect.adjusted(2, 2, -2, -2), QColor(245, 169, 48, 55))
                        painter.setPen(QPen(QColor("#E4A43D"), max(1.5, size * 0.055)))
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawRect(rect.adjusted(2, 2, -2, -2))
                if mark.state is CellState.EMPTY and size >= 10:
                    margin = max(3.0, size * 0.27)
                    painter.setPen(QPen(QColor("#C5CFCC"), max(1.5, size * 0.065)))
                    painter.drawLine(
                        rect.topLeft() + QPointF(margin, margin),
                        rect.bottomRight() - QPointF(margin, margin),
                    )
                    painter.drawLine(
                        rect.topRight() + QPointF(-margin, margin),
                        rect.bottomLeft() + QPointF(margin, -margin),
                    )

        for x in range(x0, x1 + 1):
            point = camera.cell_origin(x, 0, viewport)
            painter.setPen(
                QPen(
                    QColor("#B79A69") if x % 5 == 0 else QColor("#68757B"),
                    1.8 if x % 5 == 0 else 0.7,
                )
            )
            painter.drawLine(QPointF(point.x(), board_top), QPointF(point.x(), board_bottom))
        for y in range(y0, y1 + 1):
            point = camera.cell_origin(0, y, viewport)
            painter.setPen(
                QPen(
                    QColor("#B79A69") if y % 5 == 0 else QColor("#68757B"),
                    1.8 if y % 5 == 0 else 0.7,
                )
            )
            painter.drawLine(QPointF(board_left, point.y()), QPointF(board_right, point.y()))
        self._paint_five_step_labels(painter, viewport, (x0, y0, x1, y1))
        painter.restore()
        if self.hover is not None:
            x, y = self.hover
            if x0 <= x < x1 and y0 <= y < y1:
                origin = camera.cell_origin(x, y, viewport)
                painter.save()
                painter.setClipRect(viewport)
                painter.setPen(QPen(QColor("#B68D44"), 2.5))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(origin.x(), origin.y(), size, size).adjusted(1, 1, -1, -1))
                painter.restore()
        if self._hint_cell is not None:
            x, y = self._hint_cell
            if x0 <= x < x1 and y0 <= y < y1:
                origin = camera.cell_origin(x, y, viewport)
                painter.save()
                painter.setClipRect(viewport)
                painter.setPen(QPen(QColor("#F6C35B"), 3))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(origin.x(), origin.y(), size, size).adjusted(2, 2, -2, -2))
                painter.restore()

    def _paint_five_step_labels(
        self, painter: QPainter, viewport: QRectF, visible: tuple[int, int, int, int]
    ) -> None:
        """Number every fifth row at the right edge and column at the bottom edge."""
        size = self.camera.cell_size
        if size < 7:
            return
        x0, y0, x1, y1 = visible
        font = QFont(self.font())
        font.setPixelSize(max(5, min(13, int(size * 0.43))))
        font.setBold(True)
        painter.setFont(font)
        metrics = QFontMetricsF(font)

        def draw_label(x: int, y: int, number: int, *, top_left: bool = False) -> None:
            origin = self.camera.cell_origin(x, y, viewport)
            width = metrics.horizontalAdvance(str(number)) + (1 if size < 12 else 2)
            height = metrics.height()
            margin = 0.5 if size < 12 else 2
            left = origin.x() + margin if top_left else origin.x() + size - width - margin
            top = origin.y() + margin if top_left else origin.y() + size - height - margin
            badge = QRectF(left, top, width, height)
            painter.fillRect(badge, QColor(42, 50, 58, 235))
            painter.setPen(QColor("#E8D7B8"))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, str(number))

        if x0 <= self.display_width - 1 < x1:
            for count in range(5, self.display_height + 1, 5):
                if y0 <= count - 1 < y1:
                    draw_label(self.display_width - 1, count - 1, count)
        if y0 <= self.display_height - 1 < y1:
            for count in range(5, self.display_width + 1, 5):
                if x0 <= count - 1 < x1:
                    corner_overlap = count == self.display_width and self.display_height % 5 == 0
                    if corner_overlap and self.display_width == self.display_height:
                        continue
                    draw_label(count - 1, self.display_height - 1, count,
                               top_left=corner_overlap)

    def _paint_clues(self, painter: QPainter, viewport: QRectF) -> None:
        puzzle = self.session.puzzle
        camera = self.camera
        size = camera.cell_size
        row_edge, column_edge = self._clue_edges(viewport)
        row_band_left = row_edge - viewport.left()
        column_band_top = column_edge - viewport.top()
        row_capacity = self._clue_capacity(viewport.left())
        column_capacity = self._clue_capacity(viewport.top())
        row_slot = min(26.0, (viewport.left() - 8) / row_capacity)
        col_slot = min(26.0, (viewport.top() - 8) / column_capacity)
        font = QFont(self.font())
        font.setPixelSize(max(7, min(15, int(size * 0.58))))
        font.setBold(True)
        painter.setFont(font)
        x0, y0, x1, y1 = camera.visible_cells(viewport, self.display_width, self.display_height)

        painter.save()
        painter.setClipRect(QRectF(row_band_left, viewport.top(), viewport.left(), viewport.height()))
        for y in range(y0, y1):
            row_top = camera.cell_origin(0, y, viewport).y()
            cy = row_top + size / 2
            row_area = QRectF(row_band_left, row_top, viewport.left(), size)
            if self.hover is not None and self.hover[1] == y:
                painter.fillRect(row_area, QColor(202, 164, 73, 36))
            if self._hint_row == y:
                painter.fillRect(row_area, QColor(216, 157, 48, 75))
            painter.setPen(QPen(QColor("#7B797A"), 0.6))
            painter.drawLine(
                QPointF(row_band_left, row_top + size), QPointF(row_edge, row_top + size)
            )
            indices = self._visible_clue_indices(
                len(puzzle.row_clues[y]), row_capacity, self.row_clue_offset
            )
            for offset, clue_index in enumerate(indices):
                clue = puzzle.row_clues[y][clue_index]
                x = row_edge - 8 - (offset + 0.5) * row_slot
                self._draw_clue(
                    painter,
                    QRectF(x - row_slot / 2, cy - size / 2, row_slot, size),
                    clue,
                    self.session.is_clue_crossed("row", y, clue_index),
                )
            if len(puzzle.row_clues[y]) > len(indices):
                marker_x = row_edge - 8 - (row_capacity - 0.5) * row_slot
                painter.setPen(QColor("#C4B69B"))
                painter.drawText(
                    QRectF(marker_x - row_slot / 2, cy - size / 2, row_slot, size),
                    Qt.AlignmentFlag.AlignCenter,
                    "…",
                )
        painter.restore()

        painter.save()
        painter.setClipRect(
            QRectF(viewport.left(), column_band_top, viewport.width(), viewport.top())
        )
        for x in range(x0, x1):
            column_left = camera.cell_origin(x, 0, viewport).x()
            cx = column_left + size / 2
            column_area = QRectF(column_left, column_band_top, size, viewport.top())
            if self.hover is not None and self.hover[0] == x:
                painter.fillRect(column_area, QColor(202, 164, 73, 36))
            if self._hint_column == x:
                painter.fillRect(column_area, QColor(216, 157, 48, 75))
            painter.setPen(QPen(QColor("#7B797A"), 0.6))
            painter.drawLine(
                QPointF(column_left + size, column_band_top),
                QPointF(column_left + size, column_edge),
            )
            indices = self._visible_clue_indices(
                len(puzzle.column_clues[x]), column_capacity, self.column_clue_offset
            )
            for offset, clue_index in enumerate(indices):
                clue = puzzle.column_clues[x][clue_index]
                y = column_edge - 8 - (offset + 0.5) * col_slot
                self._draw_clue(
                    painter,
                    QRectF(cx - size / 2, y - col_slot / 2, size, col_slot),
                    clue,
                    self.session.is_clue_crossed("column", x, clue_index),
                )
            if len(puzzle.column_clues[x]) > len(indices):
                marker_y = column_edge - 8 - (column_capacity - 0.5) * col_slot
                painter.setPen(QColor("#C4B69B"))
                painter.drawText(
                    QRectF(cx - size / 2, marker_y - col_slot / 2, size, col_slot),
                    Qt.AlignmentFlag.AlignCenter,
                    "…",
                )
        painter.restore()

    def _draw_clue(self, painter: QPainter, rect: QRectF, clue, completed: bool) -> None:
        painter.save()
        if completed:
            painter.setOpacity(0.42)
            font = QFont(painter.font())
            font.setStrikeOut(True)
            painter.setFont(font)
        if self.session.puzzle.is_colored:
            color = QColor(self.session.puzzle.palette[clue.color_id - 1])
            badge = rect.adjusted(2, 2, -2, -2)
            painter.fillRect(badge, color)
            brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) / 1000
            painter.setPen(QColor("#282822") if brightness > 145 else QColor("#FFFFFF"))
        else:
            painter.setPen(INK)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(clue.length))
        painter.restore()

    def _cell_at(self, point: QPointF) -> tuple[int, int] | None:
        return self.camera.screen_to_cell(point, self.grid_viewport(),
                                          self.display_width, self.display_height)

    def _clue_at(self, point: QPointF) -> tuple[str, int, int] | None:
        puzzle = self.session.puzzle
        viewport = self.grid_viewport()
        row_edge, column_edge = self._clue_edges(viewport)
        size = self.camera.cell_size
        x0, y0, x1, y1 = self.camera.visible_cells(
            viewport, self.display_width, self.display_height
        )
        if 0 <= point.x() < row_edge and viewport.top() <= point.y() < viewport.bottom():
            capacity = self._clue_capacity(viewport.left())
            slot = min(26.0, (viewport.left() - 8) / capacity)
            for y in range(y0, y1):
                top = self.camera.cell_origin(0, y, viewport).y()
                for offset, index in enumerate(self._visible_clue_indices(
                    len(puzzle.row_clues[y]), capacity, self.row_clue_offset
                )):
                    center = row_edge - 8 - (offset + 0.5) * slot
                    if QRectF(center - slot / 2, top, slot, size).contains(point):
                        return "row", y, index
        if viewport.left() <= point.x() < viewport.right() and 0 <= point.y() < column_edge:
            capacity = self._clue_capacity(viewport.top())
            slot = min(26.0, (viewport.top() - 8) / capacity)
            for x in range(x0, x1):
                left = self.camera.cell_origin(x, 0, viewport).x()
                for offset, index in enumerate(self._visible_clue_indices(
                    len(puzzle.column_clues[x]), capacity, self.column_clue_offset
                )):
                    center = column_edge - 8 - (offset + 0.5) * slot
                    if QRectF(left, center - slot / 2, size, slot).contains(point):
                        return "column", x, index
        return None

    def _apply_at(self, point: QPointF) -> None:
        cell = self._cell_at(point)
        if cell is None:
            self._last_cell = None
            return
        previous = self._last_cell or cell
        for x, y in _stroke_cells(previous, cell):
            if self._stroke_tool == "fill":
                if self._stroke_erase_fill:
                    mark = self.session.cell_at(x, y)
                    if mark.state is CellState.FILLED and mark.color_id == self.color_id:
                        self.session.clear_cell(x, y)
                else:
                    self.session.fill_cell(x, y, self.color_id)
            elif self._stroke_tool == "empty":
                self.session.mark_empty(x, y)
            else:
                self.session.clear_cell(x, y)
        self._last_cell = cell
        self.update()

    def _finish_stroke(self) -> None:
        if not self._stroke_active:
            return
        self._stroke_active = False
        self._last_cell = None
        if self.session.end_stroke() is not None:
            self._refresh_clue_analysis()
            self.session_changed.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.setFocus()
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and (self._space_down or self.tool == "pan")
        ):
            self._pan_active = True
            self._pan_anchor = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            if event.button() == Qt.MouseButton.LeftButton and not self._space_down:
                clue = self._clue_at(event.position())
                if clue is not None:
                    if not self.session.assumption_active:
                        self.session.toggle_clue(*clue)
                        self.update()
                        self.session_changed.emit()
                    return
            self._stroke_tool = (
                "empty" if event.button() == Qt.MouseButton.RightButton else self.tool
            )
            cell = self._cell_at(event.position())
            self._stroke_erase_fill = (
                self._stroke_tool == "fill"
                and cell is not None
                and self.session.cell_at(*cell).state is CellState.FILLED
                and self.session.cell_at(*cell).color_id == self.color_id
            )
            self.session.begin_stroke()
            self._stroke_active = True
            self._last_cell = None
            self._apply_at(event.position())
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._pan_active:
            delta = event.position() - self._pan_anchor
            self._pan_anchor = event.position()
            self.camera.pan_x += delta.x()
            self.camera.pan_y += delta.y()
            self.camera.constrain(self.grid_viewport(), self.display_width, self.display_height)
            self.update()
            self.view_changed.emit()
        elif self._stroke_active:
            self._apply_at(event.position())
        cell = self._cell_at(event.position())
        if cell != self.hover:
            self.hover = cell
            self.active_clues_changed.emit(self._active_clue_text())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._pan_active:
            self._pan_active = False
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self.tool == "pan" else Qt.CursorShape.ArrowCursor
            )
        if self._stroke_active:
            self._finish_stroke()
        self.update()

    def wheelEvent(self, event: QWheelEvent) -> None:
        steps = event.angleDelta().y() / 120
        if not steps:
            event.accept()
            return
        viewport = self.grid_viewport()
        row_edge, column_edge = self._clue_edges(viewport)
        row_depth = max(map(len, self.session.puzzle.row_clues), default=0)
        column_depth = max(map(len, self.session.puzzle.column_clues), default=0)
        if (
            event.position().x() < row_edge
            and viewport.top() <= event.position().y() < viewport.bottom()
            and row_depth > self._clue_capacity(viewport.left())
        ):
            visible = self._clue_capacity(viewport.left()) - 1
            self.row_clue_offset = max(
                0, min(row_depth - visible, self.row_clue_offset + (1 if steps > 0 else -1))
            )
            self.update()
        elif (
            event.position().y() < column_edge
            and viewport.left() <= event.position().x() < viewport.right()
            and column_depth > self._clue_capacity(viewport.top())
        ):
            visible = self._clue_capacity(viewport.top()) - 1
            self.column_clue_offset = max(
                0, min(column_depth - visible, self.column_clue_offset + (1 if steps > 0 else -1))
            )
            self.update()
        else:
            self.zoom(1.15**steps, event.position())
        event.accept()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = True
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.clear_hovered_cell()
            event.accept()
        else:
            super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_down = False
            self.setCursor(
                Qt.CursorShape.OpenHandCursor
                if self.tool == "pan" else Qt.CursorShape.ArrowCursor
            )
            event.accept()
        else:
            super().keyReleaseEvent(event)

    def focusOutEvent(self, event) -> None:
        self._finish_stroke()
        self._pan_active = False
        self._space_down = False
        self.setCursor(
            Qt.CursorShape.OpenHandCursor if self.tool == "pan" else Qt.CursorShape.ArrowCursor
        )
        super().focusOutEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover = None
        self.active_clues_changed.emit(self._active_clue_text())
        self.update()
        super().leaveEvent(event)
