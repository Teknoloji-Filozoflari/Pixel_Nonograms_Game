"""Scalable pixel emblem and startup splash shared by the application."""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen

from pixel_nonograms.i18n import tr


def logo_pixmap(size=256):
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(size / 256, size / 256)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor('#2D333B'))
    painter.drawRoundedRect(QRectF(0, 0, 256, 256), 48, 48)
    pattern = ('..X..', '.XXX.', 'XXXXX', '.XXX.', '..X..')
    for y, row in enumerate(pattern):
        for x, cell in enumerate(row):
            painter.setBrush(QColor('#F06C3B' if x == 2 and y == 2 else '#8BC9B5'
                                    if cell == 'X' else '#3C434D'))
            painter.drawRoundedRect(QRectF(34 + x * 39, 34 + y * 39, 32, 32), 5, 5)
    painter.end()
    return pixmap


def application_icon():
    icon = QIcon()
    for size in (16, 32, 48, 64, 128, 256):
        icon.addPixmap(logo_pixmap(size))
    return icon


class StartupSplash(QSplashScreen):
    def __init__(self):
        canvas = QPixmap(520, 350)
        canvas.fill(QColor('#23272E'))
        painter = QPainter(canvas)
        painter.fillRect(0, 0, 520, 4, QColor('#F06C3B'))
        painter.drawPixmap(196, 35, logo_pixmap(128))
        painter.setPen(QColor('#F3946F'))
        font = QFont('Segoe UI', 23)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(20, 180, 480, 42), Qt.AlignmentFlag.AlignCenter, tr('PİKSEL NONOGRAM'))
        font.setPointSize(11)
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor('#AEB9C4'))
        painter.drawText(QRectF(20, 229, 480, 25), Qt.AlignmentFlag.AlignCenter,
                         tr('Sayıları takip et. Pikselleri tamamla.'))
        painter.end()
        super().__init__(canvas)

    def stage(self, text):
        self.showMessage(text, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                         QColor('#8BC9B5'))
        # QSplashScreen.showMessage processes paint events during synchronous startup.
