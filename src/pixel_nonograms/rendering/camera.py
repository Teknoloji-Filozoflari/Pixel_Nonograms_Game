"""Viewport geometry shared by board cells and clue labels."""

from dataclasses import dataclass
from math import ceil, floor

from PySide6.QtCore import QPointF, QRectF


@dataclass(slots=True)
class Camera:
    cell_size: float = 32.0
    pan_x: float = 0.0
    pan_y: float = 0.0
    min_cell_size: float = 2.0
    max_cell_size: float = 80.0

    def cell_origin(self, x: int, y: int, viewport: QRectF) -> QPointF:
        return QPointF(
            viewport.left() + self.pan_x + x * self.cell_size,
            viewport.top() + self.pan_y + y * self.cell_size,
        )

    def screen_to_cell(
        self, point: QPointF, viewport: QRectF, width: int, height: int
    ) -> tuple[int, int] | None:
        if not viewport.contains(point):
            return None
        x = floor((point.x() - viewport.left() - self.pan_x) / self.cell_size)
        y = floor((point.y() - viewport.top() - self.pan_y) / self.cell_size)
        return (x, y) if 0 <= x < width and 0 <= y < height else None

    def visible_cells(self, viewport: QRectF, width: int, height: int) -> tuple[int, int, int, int]:
        x0 = max(0, floor(-self.pan_x / self.cell_size))
        y0 = max(0, floor(-self.pan_y / self.cell_size))
        x1 = min(width, ceil((viewport.width() - self.pan_x) / self.cell_size))
        y1 = min(height, ceil((viewport.height() - self.pan_y) / self.cell_size))
        return x0, y0, max(x0, x1), max(y0, y1)

    def constrain(self, viewport: QRectF, width: int, height: int) -> None:
        def clamp(pan: float, extent: float, available: float) -> float:
            if extent <= available:
                return (available - extent) / 2
            return min(0.0, max(available - extent, pan))

        self.pan_x = clamp(self.pan_x, width * self.cell_size, viewport.width())
        self.pan_y = clamp(self.pan_y, height * self.cell_size, viewport.height())

    def fit(self, viewport: QRectF, width: int, height: int) -> None:
        if viewport.width() <= 0 or viewport.height() <= 0:
            return
        self.cell_size = max(
            self.min_cell_size,
            min(
                self.max_cell_size,
                (viewport.width() - 12) / width,
                (viewport.height() - 12) / height,
            ),
        )
        self.constrain(viewport, width, height)

    def zoom_at(
        self, point: QPointF, factor: float, viewport: QRectF, width: int, height: int
    ) -> None:
        old = self.cell_size
        new = max(self.min_cell_size, min(self.max_cell_size, old * factor))
        if new == old:
            return
        logical_x = (point.x() - viewport.left() - self.pan_x) / old
        logical_y = (point.y() - viewport.top() - self.pan_y) / old
        self.cell_size = new
        self.pan_x = point.x() - viewport.left() - logical_x * new
        self.pan_y = point.y() - viewport.top() - logical_y * new
        self.constrain(viewport, width, height)
