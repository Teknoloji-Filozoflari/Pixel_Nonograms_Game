"""Persistent home-screen preferences and creation/help shortcuts."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QDialog, QLabel, QPushButton, QVBoxLayout

from pixel_nonograms.i18n import tr

from .theme import CONTROL_STYLE, apply_theme, set_theme_style


class SettingsDialog(QDialog):
    editor_requested = Signal()
    tutorial_requested = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Ayarlar"))
        self.setMinimumWidth(440)
        set_theme_style(self, CONTROL_STYLE)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)
        heading = QLabel(tr("Yardım tercihleri"))
        set_theme_style(heading, "color: $accent; font-size: 20px; font-weight: 700;")
        layout.addWidget(heading)
        self.checkboxes = {}
        for key, caption, default in (
            ("assist/auto_x", "Tamamlanan çizgilerin boşlarını otomatik X yap", False),
            ("assist/clue_x", "Son sayıyı çizince kalan hücreleri X yap", True),
            ("assist/auto_clues", "Kesin tamamlanan sayıları otomatik çiz", False),
            ("assist/errors", "Çizgide fazla dolu hücre uyarısı göster", True),
            ("controls/axis_lock", "Sürüklemede yön kilidi", True),
            ("appearance/reduce_motion", "Hareketi azalt", False),
        ):
            checkbox = QCheckBox(tr(caption))
            checkbox.setChecked(settings.value(key, default, type=bool))
            checkbox.toggled.connect(lambda value, option=key: settings.setValue(option, value))
            self.checkboxes[key] = checkbox
            layout.addWidget(checkbox)
        note = QLabel(tr("Tercihler otomatik kaydedilir."))
        set_theme_style(note, "color: $muted;")
        layout.addWidget(note)
        self.editor_button = QPushButton(tr("Bulmaca oluştur"))
        self.editor_button.clicked.connect(lambda: self._open(self.editor_requested))
        layout.addWidget(self.editor_button)
        self.tutorial_button = QPushButton(tr("Oynamayı öğren"))
        self.tutorial_button.clicked.connect(lambda: self._open(self.tutorial_requested))
        layout.addWidget(self.tutorial_button)
        close = QPushButton(tr("Kapat"))
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.finished.connect(lambda: settings.sync())
        apply_theme(self, "night")

    def _open(self, signal):
        self.accept()
        signal.emit()
