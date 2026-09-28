"""One QPainter canvas for editing and previewing puzzle solutions."""

from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from pixel_nonograms.core import EditorDraft

from .theme import contrasting_ink, theme_color


class EditorCanvas(QWidget):
    changed = Signal()
    hover_changed = Signal(str)

    def __init__(self, draft: EditorDraft, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.draft = draft
        self.cell_size = 25
        self.tool = "pencil"
        self.color_id = 1
        self.hover: tuple[int, int] | None = None
        self._drag_tool: str | None = None
        self._last_cell: tuple[int, int] | None = None
        self.setMouseTracking(True)
        self.refresh_geometry()

    def refresh_geometry(self) -> None:
        row_depth = max(map(len, self.draft.row_clues), default=0)
        column_depth = max(map(len, self.draft.column_clues), default=0)
        self.left_margin = max(58, 20 + row_depth * 20)
        self.top_margin = max(58, 20 + column_depth * 20)
        self.setFixedSize(
            self.left_margin + self.draft.width * self.cell_size + 2,
            self.top_margin + self.draft.height * self.cell_size + 2,
        )
        self.update()

    def set_tool(self, tool: str) -> None:
        if tool not in {"pencil", "eraser", "fill"}:
            raise ValueError("Bilinmeyen editör aracı")
        self.tool = tool

    def set_color_id(self, color_id: int) -> None:
        if type(color_id) is not int or not 1 <= color_id <= len(self.draft.palette):
            raise ValueError("Renk palette yok")
        self.color_id = color_id

    def _cell_at(self, position: QPointF) -> tuple[int, int] | None:
        x = int((position.x() - self.left_margin) // self.cell_size)
        y = int((position.y() - self.top_margin) // self.cell_size)
        if 0 <= x < self.draft.width and 0 <= y < self.draft.height:
            return x, y
        return None

    def _apply(self, cell: tuple[int, int], tool: str) -> None:
        x, y = cell
        if tool == "fill":
            changed = self.draft.flood_fill(x, y, self.color_id) > 0
        else:
            changed = self.draft.set_cell(x, y, self.color_id if tool == "pencil" else 0)
        if changed:
            self.refresh_geometry()
            self.changed.emit()

    def _paint_clue(self, painter: QPainter, clue, x: float, y: float) -> None:
        color_id = getattr(clue, "color_id", 1)
        color = QColor(self.draft.palette[color_id - 1])
        if len(self.draft.palette) > 1:
            painter.fillRect(int(x - 9), int(y - 10), 18, 20, color)
            painter.setPen(contrasting_ink(color))
        else:
            painter.setPen(theme_color(self, "ink"))
        painter.drawText(
            int(x - 9), int(y - 10), 18, 20, Qt.AlignmentFlag.AlignCenter, str(clue.length)
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), theme_color(self, "paper"))
        painter.setFont(QFont("Sans", 11, QFont.Weight.Bold))
        size = self.cell_size
        left, top = self.left_margin, self.top_margin
        clip = event.rect()
        x0 = max(0, (clip.left() - left) // size)
        y0 = max(0, (clip.top() - top) // size)
        x1 = min(self.draft.width, (clip.right() - left) // size + 2)
        y1 = min(self.draft.height, (clip.bottom() - top) // size + 2)
        for y in range(y0, y1):
            for x in range(x0, x1):
                color_id = self.draft.cell_at(x, y)
                painter.fillRect(
                    left + x * size,
                    top + y * size,
                    size,
                    size,
                    QColor(self.draft.palette[color_id - 1])
                    if color_id
                    else theme_color(self, "board"),
                )
                if self.hover == (x, y):
                    painter.fillRect(
                        left + x * size, top + y * size, size, size, QColor(211, 166, 92, 76)
                    )
        for x in range(max(0, x0), min(self.draft.width, x1) + 1):
            painter.setPen(
                QPen(
                    theme_color(self, "grid_major") if x % 5 == 0 else theme_color(self, "grid"),
                    2 if x % 5 == 0 else 1,
                )
            )
            edge = left + x * size
            painter.drawLine(edge, top, edge, top + self.draft.height * size)
        for y in range(max(0, y0), min(self.draft.height, y1) + 1):
            painter.setPen(
                QPen(
                    theme_color(self, "grid_major") if y % 5 == 0 else theme_color(self, "grid"),
                    2 if y % 5 == 0 else 1,
                )
            )
            edge = top + y * size
            painter.drawLine(left, edge, left + self.draft.width * size, edge)
        for y in range(y0, y1):
            clues = self.draft.row_clues[y]
            for offset, clue in enumerate(reversed(clues)):
                self._paint_clue(painter, clue, left - 15 - offset * 20, top + y * size + size / 2)
        for x in range(x0, x1):
            clues = self.draft.column_clues[x]
            for offset, clue in enumerate(reversed(clues)):
                self._paint_clue(painter, clue, left + x * size + size / 2, top - 15 - offset * 20)
        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        cell = self._cell_at(event.position())
        if cell is None or event.button() not in (
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.RightButton,
        ):
            return
        self._drag_tool = "eraser" if event.button() == Qt.MouseButton.RightButton else self.tool
        self._last_cell = cell
        self._apply(cell, self._drag_tool)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        cell = self._cell_at(event.position())
        if cell != self.hover:
            self.hover = cell
            if cell is None:
                self.hover_changed.emit("")
            else:
                x, y = cell
                self.hover_changed.emit(
                    f"{y + 1}. satır: {self._clue_text(self.draft.row_clues[y])}   ·   "
                    f"{x + 1}. sütun: {self._clue_text(self.draft.column_clues[x])}"
                )
            self.update()
        if cell is None or self._drag_tool not in ("pencil", "eraser"):
            return
        if self._last_cell is not None:
            start_x, start_y = self._last_cell
            steps = max(abs(cell[0] - start_x), abs(cell[1] - start_y))
            for step in range(1, steps + 1):
                point = (
                    round(start_x + (cell[0] - start_x) * step / steps),
                    round(start_y + (cell[1] - start_y) * step / steps),
                )
                self._apply(point, self._drag_tool)
        self._last_cell = cell

    @staticmethod
    def _clue_text(clues) -> str:
        return " ".join(str(clue.length) for clue in clues) or "boş"

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_tool = None
        self._last_cell = None
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover = None
        self.hover_changed.emit("")
        self.update()
        super().leaveEvent(event)


class EditorPreview(QWidget):
    def __init__(self, draft: EditorDraft, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.draft = draft
        self.setMinimumSize(300, 300)

    def sizeHint(self) -> QSize:
        return QSize(440, 440)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(event.rect(), theme_color(self, "paper"))
        size = min((self.width() - 24) / self.draft.width, (self.height() - 24) / self.draft.height)
        left = (self.width() - size * self.draft.width) / 2
        top = (self.height() - size * self.draft.height) / 2
        painter.fillRect(
            int(left),
            int(top),
            int(size * self.draft.width),
            int(size * self.draft.height),
            theme_color(self, "board"),
        )
        for y, row in enumerate(self.draft.solution):
            for x, color_id in enumerate(row):
                if color_id:
                    painter.fillRect(
                        int(left + x * size),
                        int(top + y * size),
                        max(1, int(size + 1)),
                        max(1, int(size + 1)),
                        QColor(self.draft.palette[color_id - 1]),
                    )
        painter.end()
