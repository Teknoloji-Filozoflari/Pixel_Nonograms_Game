"""The shared, native-name language selector in the upper-right header."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox

from pixel_nonograms.i18n import LANGUAGES, language, tr


class LanguagePicker(QComboBox):
    def __init__(self, parent, on_change):
        super().__init__(parent)
        self.setProperty("language_picker", True)
        self.setFixedSize(154, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(tr("Dil"))
        self.setToolTip(tr("Dil"))
        self.setStyleSheet("""
            QComboBox { background: #263C3B; color: #D4E8E2;
                border: 1px solid #52786D; border-radius: 10px;
                padding: 0 14px; font-weight: 600; }
            QComboBox:hover { background: #315048; border-color: #85C7AD; }
            QComboBox:focus { border: 2px solid #F3946F; }
            QComboBox::drop-down { border: none; width: 26px; }
            QComboBox::down-arrow { image: none; }
            QComboBox QAbstractItemView { background: #263238; color: #E5F1ED;
                selection-background-color: #315B51; padding: 6px;
                border: 1px solid #52786D; }
        """)
        for code, name in LANGUAGES.items():
            self.addItem(name, code)
        self.setCurrentIndex(self.findData(language()))
        self.currentIndexChanged.connect(lambda: on_change(self.currentData()))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#D4E8E2"), 2))
        x, y = self.width() - 18, self.height() // 2
        painter.drawLine(x - 4, y - 2, x, y + 2)
        painter.drawLine(x, y + 2, x + 4, y - 2)
        painter.end()
