"""Dark slate palette and original botanical decoration."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from pixel_nonograms.core import Puzzle

PAPER = QColor("#171D24")
INK = QColor("#E8BD78")
CLUE = QColor("#343640")
GOLD = QColor("#D3A65C")
BOARD = QColor("#202830")
TEXT = QColor("#E9E7DE")


def paint_wallpaper(painter: QPainter, widget: QWidget) -> None:
    painter.fillRect(widget.rect(), PAPER)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(111, 137, 149, 84), 1.7))
    for base_y in range(-120, widget.height() + 180, 250):
        for base_x in range(-90, widget.width() + 230, 250):
            painter.drawLine(base_x - 18, base_y + 118, base_x + 141, base_y - 33)
            painter.drawLine(base_x + 44, base_y + 59, base_x + 8, base_y - 8)
            painter.drawLine(base_x + 96, base_y + 8, base_x + 172, base_y + 53)
            for center_x, center_y in (
                (base_x + 14, base_y + 14),
                (base_x + 88, base_y + 15),
                (base_x + 147, base_y + 56),
            ):
                painter.save()
                painter.translate(QPointF(center_x, center_y))
                for angle in range(0, 360, 72):
                    painter.save()
                    painter.rotate(angle)
                    painter.setBrush(QColor(54, 70, 78, 188))
                    painter.drawEllipse(QRectF(-4.5, -13, 9, 12))
                    painter.restore()
                painter.setBrush(QColor("#967B55"))
                painter.drawEllipse(QRectF(-3, -3, 6, 6))
                painter.restore()
    painter.restore()


class PuzzlePreview(QWidget):
    """Cached pixel artwork used on puzzle cards and the game header."""

    def __init__(self, puzzle: Puzzle, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.puzzle = puzzle
        self.setMinimumSize(88, 88)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.image = QImage(puzzle.width, puzzle.height, QImage.Format.Format_RGB32)
        self.image.fill(BOARD)
        for y, row in enumerate(puzzle.solution):
            for x, color_id in enumerate(row):
                if color_id:
                    color = (
                        QColor(puzzle.palette[color_id - 1])
                        if puzzle.is_colored else INK
                    )
                    self.image.setPixelColor(x, y, color)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(BOARD)
        painter.setPen(QPen(QColor("#7B8791"), 1.5))
        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(outer, 7, 7)
        side = min(outer.width(), outer.height()) - 12
        target = QRectF(
            outer.center().x() - side / 2,
            outer.center().y() - side / 2,
            side, side,
        )
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawImage(target, self.image)
        painter.end()
