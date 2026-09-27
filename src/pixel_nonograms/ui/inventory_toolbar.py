"""Small, explicit-target controls for optional puzzle aids."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixel_nonograms.core import HelperItemId, Puzzle
from pixel_nonograms.services.inventory import ITEM_NAMES

SHORT_NAMES = {
    HelperItemId.ANALYSIS_LENS: "Mercek",
    HelperItemId.LOGIC_HINT: "İpucu",
    HelperItemId.ERROR_CHECK: "Hata Kontrolü",
    HelperItemId.ROW_SCANNER: "Satır Tarayıcı",
    HelperItemId.COLUMN_SCANNER: "Sütun Tarayıcı",
    HelperItemId.SECOND_LOOK: "İkinci Bakış",
}
DESCRIPTIONS = {
    HelperItemId.ANALYSIS_LENS: "Seçilen çizginin durumunu ve olası yerleşimlerini inceler.",
    HelperItemId.LOGIC_HINT: "Çizgi, mantık ve kesin hücreyi sırayla gösterir; tahta değişirse kapanır.",
    HelperItemId.ERROR_CHECK: "Çözümle uyuşmayan ilk işareti gösterir.",
    HelperItemId.ROW_SCANNER: "Seçilen satırdaki en çok üç kesin hücreyi gösterir.",
    HelperItemId.COLUMN_SCANNER: "Seçilen sütundaki en çok üç kesin hücreyi gösterir.",
    HelperItemId.SECOND_LOOK: "Çelişki bulunan ilk satır veya sütunu gösterir.",
}
TARGETED = frozenset(
    (HelperItemId.ANALYSIS_LENS, HelperItemId.ROW_SCANNER, HelperItemId.COLUMN_SCANNER)
)


class InventoryToolbar(QWidget):
    use_requested = Signal(object, object, object)
    next_hint_requested = Signal()
    selection_changed = Signal(object)

    def __init__(self, puzzle: Puzzle, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("inventory_toolbar")
        self.setStyleSheet("""
            QWidget#inventory_toolbar { background: #27313A;
                border: 1px solid #627079; border-radius: 7px; }
            QPushButton, QComboBox { background: #333E47; color: #E8E7DF;
                border: 1px solid #77817E; border-radius: 6px; padding: 5px 8px; }
            QPushButton:hover { background: #45535C; }
            QPushButton:checked { background: #765F3F; border-color: #D3A65C; }
            QPushButton:disabled { color: #879193; background: #293239; }
            QLabel { color: #E5E6DF; background: transparent; }
        """)
        self.puzzle = puzzle
        self.selected_item: HelperItemId | None = None
        self._counts = {item: 0 for item in HelperItemId}
        self._available = True
        self._hint_level: int | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(5)
        row = QHBoxLayout()
        row.setSpacing(5)
        root.addLayout(row)
        heading = QLabel("Yardımcılar")
        heading.setStyleSheet("color: #E8BD78; font-weight: 700;")
        row.addWidget(heading)
        self.item_buttons: dict[HelperItemId, QPushButton] = {}
        for item_id in HelperItemId:
            button = QPushButton()
            button.setCheckable(True)
            button.setToolTip(f"{ITEM_NAMES[item_id]}: {DESCRIPTIONS[item_id]}")
            button.setAccessibleName(ITEM_NAMES[item_id])
            button.clicked.connect(
                lambda checked=False, selected=item_id: self.select_item(selected)
            )
            row.addWidget(button)
            self.item_buttons[item_id] = button
        row.addStretch(1)

        self.detail = QFrame()
        self.detail.setStyleSheet(
            "QFrame { background: #303B43; border: 1px solid #66737A; border-radius: 6px; }"
            "QLabel { color: #E5E6DF; border: none; background: transparent; }"
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
        self.axis_box.addItem("Satır", "row")
        self.axis_box.addItem("Sütun", "column")
        self.axis_box.currentIndexChanged.connect(self._axis_changed)
        controls.addWidget(self.axis_box)
        self.line_box = QComboBox()
        self.line_box.currentIndexChanged.connect(self._update_target)
        controls.addWidget(self.line_box)
        controls.addStretch(1)
        self.use_button = QPushButton("Kullan")
        self.use_button.clicked.connect(self._request_use)
        controls.addWidget(self.use_button)
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(lambda: self.select_item(None))
        controls.addWidget(close_button)
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setStyleSheet("color: #CCD6D0;")
        self.message_label.hide()
        detail_layout.addWidget(self.message_label)
        self.next_hint_button = QPushButton()
        self.next_hint_button.clicked.connect(self.next_hint_requested.emit)
        self.next_hint_button.hide()
        detail_layout.addWidget(self.next_hint_button)
        self.detail.hide()
        self.notice_label = QLabel()
        self.notice_label.setStyleSheet("color: #E8BD78;")
        self.notice_label.hide()
        root.addWidget(self.notice_label)
        self._refresh_buttons()

    def set_counts(self, counts: dict[HelperItemId, int]) -> None:
        self._counts = {item: counts.get(item, 0) for item in HelperItemId}
        self._refresh_buttons()
        self._update_detail()

    def set_available(self, available: bool) -> None:
        self._available = available
        self._update_target()

    def select_item(self, item_id: HelperItemId | None) -> None:
        if item_id is not None:
            item_id = HelperItemId(item_id)
        self.selected_item = None if item_id == self.selected_item else item_id
        for candidate, button in self.item_buttons.items():
            button.setChecked(candidate is self.selected_item)
        self.notice_label.hide()
        self.message_label.hide()
        self.next_hint_button.hide()
        self._hint_level = None
        self.detail.setVisible(self.selected_item is not None)
        if self.selected_item is None:
            self.selection_changed.emit(None)
            return
        self.axis_box.blockSignals(True)
        self.axis_box.setCurrentIndex(1 if self.selected_item is HelperItemId.COLUMN_SCANNER else 0)
        self.axis_box.blockSignals(False)
        self._fill_lines()
        self._update_detail()
        self.selection_changed.emit(self.selected_item)

    def _refresh_buttons(self) -> None:
        for item_id, button in self.item_buttons.items():
            button.setText(f"{SHORT_NAMES[item_id]} {self._counts[item_id]}")
            button.setAccessibleName(f"{ITEM_NAMES[item_id]}, {self._counts[item_id]} adet")

    def _fill_lines(self) -> None:
        self.line_box.blockSignals(True)
        self.line_box.clear()
        self.line_box.addItem("Hedef seçin", None)
        limit = self.puzzle.height if self.axis_box.currentData() == "row" else self.puzzle.width
        for index in range(limit):
            self.line_box.addItem(str(index + 1), index)
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
            f"{ITEM_NAMES[item_id]} · {DESCRIPTIONS[item_id]} · Kalan: {self._counts[item_id]}"
        )
        targeted = item_id in TARGETED
        self.axis_box.setVisible(targeted)
        self.line_box.setVisible(targeted)
        self.axis_box.setEnabled(item_id is HelperItemId.ANALYSIS_LENS)
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
        elif item_id is HelperItemId.SECOND_LOOK:
            target = "Hedef: tahta genelinde; satır/sütun otomatik belirlenir"
        else:
            target = "Hedef: tahta genelinde; hücre otomatik belirlenir"
        self.target_label.setText(target)
        self.use_button.setEnabled(
            self._available
            and self._counts[item_id] > 0
            and (not targeted or line_index is not None)
            and not (item_id is HelperItemId.LOGIC_HINT and self._hint_level in (1, 2))
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
        self.message_label.setText(message)
        self.message_label.show()
        if consumed and self.selected_item in TARGETED:
            self.line_box.setCurrentIndex(0)

    def show_hint_step(self, message: str, level: int) -> None:
        if level not in (1, 2, 3):
            raise ValueError("İpucu seviyesi geçersiz")
        self._hint_level = level
        self.message_label.setText(message)
        self.message_label.show()
        self.next_hint_button.setText("Mantığı açıkla" if level == 1 else "Kesin hücreyi göster")
        self.next_hint_button.setVisible(level < 3)
        self._update_target()

    def show_notice(self, message: str) -> None:
        self.notice_label.setText(message)
        self.notice_label.show()
