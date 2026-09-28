"""Small, explicit-target controls for optional puzzle aids."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from pixel_nonograms.core import HelperItemId, Puzzle
from pixel_nonograms.i18n import tr
from pixel_nonograms.services.inventory import ITEM_NAMES

from .theme import set_theme_style

SHORT_NAMES = {
    HelperItemId.ROW_SCANNER: "↔",
    HelperItemId.ANALYSIS_LENS: "⌕",
    HelperItemId.LOGIC_HINT: "3×3",
    HelperItemId.ERROR_CHECK: "5×5",
    HelperItemId.SECOND_LOOK: "10×10",
}
DESCRIPTIONS = {
    HelperItemId.ROW_SCANNER: "Seçilen satır veya sütunu doğru renkler ve X işaretleriyle tamamlar.",
    HelperItemId.ANALYSIS_LENS: "Yanlış boyalı bir hücreyi düzeltir; hata yoksa eksik bir hücreyi boyar.",
    HelperItemId.LOGIC_HINT: "3×3 alanı doğru renklerle boyar, boş hücreleri X yapar.",
    HelperItemId.ERROR_CHECK: "5×5 alanı doğru renklerle boyar, boş hücreleri X yapar.",
    HelperItemId.COLUMN_SCANNER: "Eksik beş farklı dolu hücreyi doğru renkle boyar.",
    HelperItemId.SECOND_LOOK: "10×10 alanı doğru renklerle boyar, boş hücreleri X yapar.",
}
TARGETED = frozenset((HelperItemId.ROW_SCANNER,))


class InventoryToolbar(QWidget):
    use_requested = Signal(object, object, object)
    next_hint_requested = Signal()
    selection_changed = Signal(object)

    def __init__(self, puzzle: Puzzle, parent: QWidget | None = None, *, compact=False) -> None:
        super().__init__(parent)
        self.compact = compact
        self.setObjectName("inventory_toolbar")
        set_theme_style(
            self,
            """
            QWidget#inventory_toolbar { background: $panel;
                border: 1px solid $border; border-radius: 7px; }
            QPushButton, QComboBox { background: $button; color: $text;
                border: 1px solid $border; border-radius: 6px; padding: 5px 8px; }
            QPushButton:hover { background: $hover; }
            QPushButton:checked { background: $selected; color: $selected_text;
                border-color: $teal; }
            QPushButton:disabled { color: $disabled_text; background: $disabled; }
            QLabel { color: $text; background: transparent; }
        """,
        )
        self.puzzle = puzzle
        self.selected_item: HelperItemId | None = None
        self._counts = {item: 0 for item in HelperItemId}
        self._available = True
        self._hint_level: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(5)
        self.menu = QMenu(self)
        choices = QWidget()
        row = QVBoxLayout(choices) if compact else QHBoxLayout()
        row.setSpacing(5)
        if compact:
            choices.setMinimumWidth(260)
            action = QWidgetAction(self.menu)
            action.setDefaultWidget(choices)
            self.menu.addAction(action)
        else:
            root.addLayout(row)
        self.item_buttons: dict[HelperItemId, QPushButton] = {}
        for item_id in SHORT_NAMES:
            button = QPushButton()
            button.setCheckable(True)
            button.setToolTip(tr(f"{ITEM_NAMES[item_id]}: {DESCRIPTIONS[item_id]}"))
            button.setAccessibleName(tr(ITEM_NAMES[item_id]))
            button.clicked.connect(
                lambda checked=False, selected=item_id: self._activate_item(selected)
            )
            row.addWidget(button)
            self.item_buttons[item_id] = button
        row.addStretch(1)

        self.detail = QFrame()
        set_theme_style(
            self.detail,
            "QFrame { background: $button; border: 1px solid $border; border-radius: 6px; }QLabel { color: $text; border: none; background: transparent; }",
        )
        root.addWidget(self.detail)
        detail_layout = QVBoxLayout(self.detail)
        detail_layout.setContentsMargins(9, 6, 9, 6)
        detail_layout.setSpacing(4)
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        detail_layout.addWidget(self.description_label)
        controls = QHBoxLayout()
        controls.setSpacing(6)
        detail_layout.addLayout(controls)
        self.target_label = QLabel()
        controls.addWidget(self.target_label)
        self.axis_box = QComboBox()
        self.axis_box.addItem(tr("Satır"), "row")
        self.axis_box.addItem(tr("Sütun"), "column")
        self.axis_box.currentIndexChanged.connect(self._axis_changed)
        controls.addWidget(self.axis_box)
        self.line_box = QComboBox()
        self.line_box.currentIndexChanged.connect(self._line_changed)
        controls.addWidget(self.line_box)
        controls.addStretch(1)
        self.use_button = QPushButton(tr("▶"))
        self.use_button.setToolTip(tr("Kullan · 1 eşya"))
        self.use_button.setAccessibleName(tr("Yardımcıyı kullan"))
        self.use_button.clicked.connect(self._request_use)
        controls.addWidget(self.use_button)
        close_button = QPushButton(tr("×"))
        close_button.setToolTip(tr("Kapat"))
        close_button.setAccessibleName(tr("Kapat"))
        close_button.clicked.connect(lambda: self.select_item(None))
        controls.addWidget(close_button)
        self.cost_label = QLabel(tr("Yeni yardım: 1 eşya. Yararlı sonuç yoksa harcanmaz."))
        self.cost_label.setWordWrap(True)
        detail_layout.addWidget(self.cost_label)
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        set_theme_style(self.message_label, "color: $muted;")
        self.message_label.hide()
        detail_layout.addWidget(self.message_label)
        self.next_hint_button = QPushButton()
        self.next_hint_button.clicked.connect(self.next_hint_requested.emit)
        self.next_hint_button.hide()
        detail_layout.addWidget(self.next_hint_button)
        self.detail.hide()
        self.notice_label = QLabel()
        set_theme_style(self.notice_label, "color: $accent;")
        self.notice_label.hide()
        root.addWidget(self.notice_label)
        self._refresh_buttons()
        if compact:
            self.description_label.hide()
            self.cost_label.hide()
            self.use_button.hide()
            self.hide()

    def _activate_item(self, item_id) -> None:
        if not self.compact:
            self.select_item(item_id)
            return
        # Repeated clicks are new uses, rather than toggling an explanation panel.
        self.selected_item = None
        self.select_item(item_id)
        if item_id in TARGETED:
            if self._available and self._counts[item_id] > 0:
                self.use_requested.emit(item_id, None, None)
        else:
            self._request_use()
        self.detail.hide()
        self.hide()

    def _line_changed(self) -> None:
        self._update_target()
        if self.compact and self.line_box.currentData() is not None:
            self._request_use()
            self.detail.hide()
            self.hide()

    def set_counts(self, counts: dict[HelperItemId, int]) -> None:
        self._counts = {item: counts.get(item, 0) for item in HelperItemId}
        self._refresh_buttons()
        self._update_detail()

    def refresh_translation(self) -> None:
        self._refresh_buttons()
        self._update_detail()

    def set_available(self, available: bool) -> None:
        self._available = available
        self._refresh_buttons()
        self._update_target()

    def select_item(self, item_id: HelperItemId | None) -> None:
        if item_id is not None:
            item_id = HelperItemId(item_id)
        self.selected_item = None if item_id == self.selected_item else item_id
        for candidate, button in self.item_buttons.items():
            button.setChecked(candidate is self.selected_item)
        self.notice_label.hide()
        self.cost_label.setText(tr("Yeni yardım: 1 eşya. Yararlı sonuç yoksa harcanmaz."))
        self.message_label.hide()
        self.next_hint_button.hide()
        self._hint_level = None
        self.detail.setVisible(self.selected_item is not None)
        if self.compact:
            self.menu.close()
            self.setVisible(self.selected_item is not None)
        if self.selected_item is None:
            self.selection_changed.emit(None)
            return
        self.axis_box.blockSignals(True)
        self.axis_box.setCurrentIndex(0)
        self.axis_box.blockSignals(False)
        self._fill_lines()
        self._update_detail()
        self.selection_changed.emit(self.selected_item)

    def _refresh_buttons(self) -> None:
        for item_id, button in self.item_buttons.items():
            button.setText(
                f"{SHORT_NAMES[item_id]}  {tr(ITEM_NAMES[item_id])}  ·  {self._counts[item_id]}"
                if self.compact else tr(f"{SHORT_NAMES[item_id]} {self._counts[item_id]}")
            )
            button.setAccessibleName(tr(f"{ITEM_NAMES[item_id]}, {self._counts[item_id]} adet"))
            description = tr(DESCRIPTIONS[item_id])
            if item_id in TARGETED:
                description += " " + tr("Soldaki satır veya üstteki sütun sayılarına tıkla. Sağ tık veya Esc ile iptal et.")
            if item_id in (HelperItemId.LOGIC_HINT, HelperItemId.ERROR_CHECK, HelperItemId.SECOND_LOOK):
                description += " " + tr("Tahtada başlangıç hücresine tıkla. Sağ tık veya Esc ile iptal et.")
            button.setToolTip(f"{tr(ITEM_NAMES[item_id])}: {description}")
            button.setEnabled(self._available and self._counts[item_id] > 0)

    def _fill_lines(self) -> None:
        self.line_box.blockSignals(True)
        self.line_box.clear()
        self.line_box.addItem(tr("Hedef seçin"), None)
        limit = self.puzzle.height if self.axis_box.currentData() == "row" else self.puzzle.width
        for index in range(limit):
            self.line_box.addItem(tr(str(index + 1)), index)
        self.line_box.setCurrentIndex(0)
        self.line_box.blockSignals(False)
        self._update_target()

    def _axis_changed(self) -> None:
        if self.selected_item is not None:
            self._fill_lines()

    def _update_detail(self) -> None:
        item_id = self.selected_item
        if item_id is None:
            return
        self.description_label.setText(
            tr(f"{ITEM_NAMES[item_id]} · {DESCRIPTIONS[item_id]} · Kalan: {self._counts[item_id]}")
        )
        targeted = item_id in TARGETED
        self.axis_box.setVisible(targeted)
        self.line_box.setVisible(targeted)
        self.axis_box.setEnabled(item_id in TARGETED)
        self._update_target()

    def _update_target(self) -> None:
        item_id = self.selected_item
        if item_id is None:
            return
        targeted = item_id in TARGETED
        line_index = self.line_box.currentData()
        if targeted:
            axis = "satır" if self.axis_box.currentData() == "row" else "sütun"
            target = (
                f"Hedef: {line_index + 1}. {axis}" if line_index is not None else "Hedef: seçilmedi"
            )
        elif item_id in (HelperItemId.LOGIC_HINT, HelperItemId.ERROR_CHECK,
                         HelperItemId.SECOND_LOOK):
            target = "Hedef: en çok eksik hücre içeren alan; otomatik seçilir"
        else:
            target = "Hedef: tahta genelinde; hücre otomatik belirlenir"
        self.target_label.setText(tr(target))
        self.use_button.setEnabled(
            self._available
            and self._counts[item_id] > 0
            and (not targeted or line_index is not None)

        )
        self.next_hint_button.setEnabled(self._available and self._hint_level in (1, 2))

    def _request_use(self) -> None:
        if self.selected_item is None or not self.use_button.isEnabled():
            return
        targeted = self.selected_item in TARGETED
        self.use_requested.emit(
            self.selected_item,
            self.axis_box.currentData() if targeted else None,
            self.line_box.currentData() if targeted else None,
        )

    def show_result(self, message: str, *, consumed: bool) -> None:
        self._hint_level = None
        self.next_hint_button.hide()
        self.cost_label.setText(tr("1 eşya kullanıldı." if consumed else "Bu işlemde eşya harcanmadı."))
        self.message_label.setText(tr(message))
        self.message_label.show()
        if consumed and self.selected_item in TARGETED:
            self.line_box.setCurrentIndex(0)

    def show_hint_step(self, message: str, level: int) -> None:
        if level not in (1, 2, 3):
            raise ValueError("İpucu seviyesi geçersiz")
        self._hint_level = level
        self.cost_label.setText(
            tr("Bu ipucu zinciri: 1 eşya kullanıldı. Üç adımın devamı ücretsizdir.")
        )
        stage = {1: "Çizgiyi bul", 2: "Mantığı anla", 3: "Kesin hücreyi gör"}[level]
        self.message_label.setText(tr(f"{stage} — {message}"))
        self.message_label.show()
        self.next_hint_button.setText(tr("»" if level == 1 else "◎"))
        caption = "Mantığı açıkla" if level == 1 else "Kesin hücreyi göster"
        self.next_hint_button.setToolTip(tr(caption))
        self.next_hint_button.setAccessibleName(tr(caption))
        self.next_hint_button.setVisible(level < 3)
        self._update_target()

    def show_notice(self, message: str) -> None:
        if self.compact:
            self.show()
        self.notice_label.setText(tr(message))
        self.notice_label.show()
