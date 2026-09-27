"""Small vector icons for the game toolbar."""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap


def tool_icon(name: str) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    ink = QColor("#E4E8E6")
    accent = QColor("#D3A65C")
    painter.setPen(QPen(ink, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                        Qt.PenJoinStyle.RoundJoin))

    if name in {"fill", "empty", "clear"}:
        painter.drawRoundedRect(QRectF(10, 10, 44, 44), 5, 5)
        if name == "fill":
            painter.fillRect(QRectF(17, 17, 30, 30), accent)
        elif name == "empty":
            painter.drawLine(19, 19, 45, 45)
            painter.drawLine(45, 19, 19, 45)
        else:
            painter.setPen(QPen(accent, 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(19, 45, 45, 19)
    elif name == "pan":
        painter.drawLine(32, 8, 32, 56)
        painter.drawLine(8, 32, 56, 32)
        for start, end in ((QPointF(32, 8), QPointF(24, 18)),
                           (QPointF(32, 8), QPointF(40, 18)),
                           (QPointF(32, 56), QPointF(24, 46)),
                           (QPointF(32, 56), QPointF(40, 46)),
                           (QPointF(8, 32), QPointF(18, 24)),
                           (QPointF(8, 32), QPointF(18, 40)),
                           (QPointF(56, 32), QPointF(46, 24)),
                           (QPointF(56, 32), QPointF(46, 40))):
            painter.drawLine(start, end)
    elif name in {"undo", "redo"}:
        painter.drawArc(QRectF(15, 17, 38, 33), 30 * 16, 250 * 16)
        if name == "undo":
            painter.drawLine(15, 27, 15, 14)
            painter.drawLine(15, 27, 28, 25)
        else:
            painter.drawLine(49, 27, 49, 14)
            painter.drawLine(49, 27, 36, 25)
    elif name in {"zoom_in", "zoom_out"}:
        painter.drawEllipse(QRectF(11, 11, 32, 32))
        painter.drawLine(42, 42, 55, 55)
        painter.drawLine(20, 27, 34, 27)
        if name == "zoom_in":
            painter.drawLine(27, 20, 27, 34)
    elif name == "fit":
        painter.drawRoundedRect(QRectF(10, 12, 44, 40), 3, 3)
        painter.drawLine(19, 22, 27, 22)
        painter.drawLine(19, 22, 19, 30)
        painter.drawLine(45, 42, 37, 42)
        painter.drawLine(45, 42, 45, 34)
    elif name == "trial":
        painter.drawRoundedRect(QRectF(13, 13, 38, 38), 5, 5)
        painter.setPen(QPen(accent, 5, Qt.PenStyle.DashLine))
        painter.drawLine(20, 39, 43, 19)
    elif name == "accept":
        painter.setPen(QPen(accent, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(12, 33, 26, 47)
        painter.drawLine(26, 47, 52, 17)
    elif name == "cancel":
        painter.drawLine(17, 17, 47, 47)
        painter.drawLine(47, 17, 17, 47)
    elif name == "menu":
        painter.setBrush(ink)
        for y in (17, 32, 47):
            painter.drawEllipse(QPointF(32, y), 3.5, 3.5)
    else:
        raise ValueError(f"Unknown toolbar icon: {name}")
    painter.end()
    return QIcon(pixmap)
