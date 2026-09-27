"""Offline puzzle editor with live clues and solver validation on save."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pixel_nonograms.core import Difficulty, EditorDraft
from pixel_nonograms.importer import GRID_SIZES, ImageImportOptions
from pixel_nonograms.services import convert_image_to_puzzle, save_editor_puzzle
from pixel_nonograms.services.puzzle_library import DIFFICULTY_LABELS
from pixel_nonograms.solver import SolveStatus

from .editor_canvas import EditorCanvas, EditorPreview


class ImageImportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Görselden Nonogram")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.size_box = QComboBox()
        for size in GRID_SIZES:
            self.size_box.addItem(f"{size} × {size}", size)
        self.size_box.setCurrentIndex(2)
        form.addRow("Izgara", self.size_box)
        self.mode_box = QComboBox()
        self.mode_box.addItem("Siyah beyaz", "mono")
        self.mode_box.addItem("Renkli", "color")
        form.addRow("Dönüşüm", self.mode_box)
        self.threshold_box = QSpinBox()
        self.threshold_box.setRange(1, 254)
        self.threshold_box.setValue(180)
        self.threshold_box.setToolTip("Daha yüksek değer daha çok hücreyi doldurur")
        form.addRow("Doluluk eşiği", self.threshold_box)
        self.colors_box = QSpinBox()
        self.colors_box.setRange(2, 8)
        self.colors_box.setValue(4)
        self.colors_box.setEnabled(False)
        self.mode_box.currentIndexChanged.connect(
            lambda: self.colors_box.setEnabled(self.mode_box.currentData() == "color")
        )
        form.addRow("Renk sayısı", self.colors_box)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def options(self) -> ImageImportOptions:
        return ImageImportOptions(
            size=self.size_box.currentData(),
            mode=self.mode_box.currentData(),
            threshold=self.threshold_box.value(),
            colors=self.colors_box.value(),
        )


class EditorScreen(QWidget):
    back_requested = Signal()
    saved = Signal(object)

    def __init__(self, directory: str | Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.directory = Path(directory)
        self.draft = EditorDraft()
        self.last_result = None
        self.setStyleSheet("""
            QWidget, QScrollArea { background: #171D24; color: #E8E7DF; font-size: 13px; }
            QLineEdit, QSpinBox, QComboBox, QPushButton { background: #2D3740; color: #E8E7DF;
                border: 1px solid #66717A; border-radius: 6px; padding: 6px 9px; }
            QPushButton:hover { background: #3D4A54; }
            QPushButton:checked { background: #765F3F; border-color: #D3A65C; }
            QPushButton:disabled { color: #899498; background: #293139; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        root.addLayout(header)
        self.back_button = QPushButton("← Kütüphane")
        self.back_button.clicked.connect(self.back_requested.emit)
        header.addWidget(self.back_button)
        title = QLabel("Bulmaca Editörü")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch(1)
        self.import_button = QPushButton("Görselden Oluştur")
        self.import_button.clicked.connect(self.open_image_import)
        header.addWidget(self.import_button)
        self.save_button = QPushButton("Doğrula ve Kaydet")
        self.save_button.clicked.connect(self.save)
        header.addWidget(self.save_button)

        metadata = QGridLayout()
        root.addLayout(metadata)
        self.title_edit = QLineEdit("Yeni Bulmaca")
        self.title_edit.setMaxLength(200)
        self.author_edit = QLineEdit("Oyuncu")
        self.author_edit.setMaxLength(200)
        self.description_edit = QLineEdit()
        self.description_edit.setMaxLength(4096)
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("Etiketler, virgülle ayrılmış")
        self.difficulty_box = QComboBox()
        for difficulty in Difficulty:
            self.difficulty_box.addItem(DIFFICULTY_LABELS[difficulty], difficulty)
        for col, label, widget in (
            (0, "Başlık", self.title_edit),
            (2, "Yazar", self.author_edit),
            (4, "Zorluk", self.difficulty_box),
        ):
            metadata.addWidget(QLabel(label), 0, col)
            metadata.addWidget(widget, 0, col + 1)
        metadata.addWidget(QLabel("Açıklama"), 1, 0)
        metadata.addWidget(self.description_edit, 1, 1, 1, 3)
        metadata.addWidget(QLabel("Etiketler"), 1, 4)
        metadata.addWidget(self.tags_edit, 1, 5)
        for field in (self.title_edit, self.author_edit, self.description_edit, self.tags_edit):
            field.textChanged.connect(self._mark_changed)
        self.difficulty_box.currentIndexChanged.connect(self._mark_changed)

        tools = QHBoxLayout()
        root.addLayout(tools)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.tool_buttons = {}
        for tool, caption in (("pencil", "✎ Kalem"), ("eraser", "⌫ Silgi"), ("fill", "▣ Dolgu")):
            button = QPushButton(caption)
            button.setCheckable(True)
            button.setChecked(tool == "pencil")
            button.clicked.connect(
                lambda checked=False, selected=tool: self.canvas.set_tool(selected)
            )
            group.addButton(button)
            tools.addWidget(button)
            self.tool_buttons[tool] = button
        tools.addSpacing(8)
        tools.addWidget(QLabel("Palette"))
        self.palette_box = QComboBox()
        self.palette_box.currentIndexChanged.connect(self._select_color)
        tools.addWidget(self.palette_box)
        self.add_color_button = QPushButton("+ Renk")
        self.add_color_button.clicked.connect(self._add_color)
        tools.addWidget(self.add_color_button)
        self.edit_color_button = QPushButton("Rengi Düzenle")
        self.edit_color_button.clicked.connect(self._edit_color)
        tools.addWidget(self.edit_color_button)
        self.remove_color_button = QPushButton("− Renk")
        self.remove_color_button.clicked.connect(self._remove_color)
        tools.addWidget(self.remove_color_button)
        tools.addStretch(1)

        dimensions = QHBoxLayout()
        root.addLayout(dimensions)
        dimensions.addWidget(QLabel("Izgara"))
        self.width_box = QSpinBox()
        self.height_box = QSpinBox()
        for box, value in (
            (self.width_box, self.draft.width),
            (self.height_box, self.draft.height),
        ):
            box.setRange(1, 100)
            box.setValue(value)
        dimensions.addWidget(self.width_box)
        dimensions.addWidget(QLabel("×"))
        dimensions.addWidget(self.height_box)
        self.width_box.valueChanged.connect(self._resize_grid)
        self.height_box.valueChanged.connect(self._resize_grid)
        dimensions.addSpacing(10)
        self.clear_button = QPushButton("Izgarayı Temizle")
        self.clear_button.clicked.connect(self._clear_grid)
        dimensions.addWidget(self.clear_button)
        preview_button = QPushButton("Önizleme")
        preview_button.clicked.connect(self.show_preview)
        dimensions.addWidget(preview_button)
        dimensions.addStretch(1)
        self.clue_label = QLabel("Hücreye gelince satır ve sütun ipuçları görünür.")
        self.clue_label.setStyleSheet("color: #BBC5C3;")
        dimensions.addWidget(self.clue_label)

        self.canvas = EditorCanvas(self.draft)
        self.canvas.changed.connect(self._on_grid_changed)
        self.canvas.hover_changed.connect(self._show_hover_clues)
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        root.addWidget(scroll, 1)

        self.status_label = QLabel("Çizimi tamamlayıp doğrulayarak kaydedin.")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self._refresh_palette()

    def open_image_import(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "Görsel Seç",
            "",
            "Görseller (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        dialog = ImageImportDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.import_from_path(path, dialog.options())

    def import_from_path(self, path: str | Path, options: ImageImportOptions) -> None:
        try:
            result = convert_image_to_puzzle(path, options)
        except (OSError, ValueError) as exc:
            self.status_label.setText(f"Görsel dönüştürülemedi: {exc}")
            return
        self.draft = result.draft
        self.canvas.draft = result.draft
        for box, value in (
            (self.width_box, result.draft.width),
            (self.height_box, result.draft.height),
        ):
            box.blockSignals(True)
            box.setValue(value)
            box.blockSignals(False)
        self._refresh_palette()
        self.title_edit.setText(Path(path).stem[:200])
        self._mark_changed()
        status_text = {
            SolveStatus.SOLVED: "Tek çözüm",
            SolveStatus.MULTIPLE_SOLUTIONS: "Birden fazla çözüm",
            SolveStatus.NO_SOLUTION: "Çözüm yok",
            SolveStatus.UNKNOWN_LIMIT: "Doğrulama sınırına ulaşıldı",
        }[result.status]
        self.status_label.setText(
            f"Görsel {result.draft.width} × {result.draft.height} ızgaraya dönüştürüldü. "
            f"Solver: {status_text}. Kaydetmeden önce çizimi düzenleyebilirsiniz."
        )

    def _mark_changed(self, *_args) -> None:
        self.save_button.setEnabled(True)
        self.last_result = None

    def _on_grid_changed(self) -> None:
        self._mark_changed()
        self.status_label.setText("Satır ve sütun ipuçları güncellendi.")

    def _show_hover_clues(self, text: str) -> None:
        self.clue_label.setText(text or "Hücreye gelince satır ve sütun ipuçları görünür.")

    def _refresh_palette(self, preferred: int = 1) -> None:
        self.palette_box.blockSignals(True)
        self.palette_box.clear()
        for color_id, color in enumerate(self.draft.palette, 1):
            swatch = QPixmap(16, 16)
            swatch.fill(QColor(color))
            self.palette_box.addItem(QIcon(swatch), f"{color_id}: {color}", color_id)
        self.palette_box.setCurrentIndex(min(preferred, len(self.draft.palette)) - 1)
        self.palette_box.blockSignals(False)
        self.canvas.set_color_id(self.palette_box.currentData())
        self.remove_color_button.setEnabled(len(self.draft.palette) > 1)
        self.add_color_button.setEnabled(len(self.draft.palette) < 255)
        self.canvas.refresh_geometry()

    def _select_color(self, index: int) -> None:
        color_id = self.palette_box.itemData(index)
        if color_id is not None:
            self.canvas.set_color_id(color_id)

    def _add_color(self) -> None:
        color = QColorDialog.getColor(QColor("#D67D4A"), self, "Yeni Renk")
        if not color.isValid():
            return
        try:
            color_id = self.draft.add_color(color.name().upper())
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        self._refresh_palette(color_id)
        self._on_grid_changed()

    def _edit_color(self) -> None:
        color_id = self.palette_box.currentData()
        color = QColorDialog.getColor(
            QColor(self.draft.palette[color_id - 1]), self, "Rengi Düzenle"
        )
        if not color.isValid():
            return
        try:
            self.draft.set_palette_color(color_id, color.name().upper())
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        self._refresh_palette(color_id)
        self._on_grid_changed()

    def _remove_color(self) -> None:
        color_id = self.palette_box.currentData()
        try:
            self.draft.remove_color(color_id)
        except ValueError as exc:
            self.status_label.setText(str(exc))
            return
        self._refresh_palette(min(color_id, len(self.draft.palette)))
        self._on_grid_changed()

    def _resize_grid(self) -> None:
        if self.draft.resize(self.width_box.value(), self.height_box.value()):
            self.canvas.refresh_geometry()
            self._on_grid_changed()

    def _clear_grid(self) -> None:
        if self.draft.clear():
            self.canvas.refresh_geometry()
            self._on_grid_changed()

    def show_preview(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Bulmaca Önizlemesi")
        layout = QVBoxLayout(dialog)
        layout.addWidget(EditorPreview(self.draft))
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

    def save(self) -> None:
        if not self.save_button.isEnabled():
            return
        tags = tuple(tag.strip() for tag in self.tags_edit.text().split(",") if tag.strip())
        try:
            result = save_editor_puzzle(
                self.draft,
                self.directory,
                title=self.title_edit.text(),
                author=self.author_edit.text(),
                description=self.description_edit.text(),
                difficulty=Difficulty(self.difficulty_box.currentData()),
                tags=tags,
            )
        except (OSError, ValueError) as exc:
            self.status_label.setText(f"Kaydedilemedi: {exc}")
            return
        self.last_result = result
        messages = {
            SolveStatus.SOLVED: "Tek çözüm — bulmaca .nono dosyasına kaydedildi.",
            SolveStatus.MULTIPLE_SOLUTIONS: "Birden fazla çözüm — bulmaca kaydedilmedi.",
            SolveStatus.NO_SOLUTION: "Çözüm yok — bulmaca kaydedilmedi.",
            SolveStatus.UNKNOWN_LIMIT: "Doğrulama sınırına ulaşıldı — bulmaca kaydedilmedi.",
        }
        self.status_label.setText(messages[result.status])
        if result.status is SolveStatus.SOLVED:
            self.save_button.setEnabled(False)
            self.saved.emit(result.puzzle)
