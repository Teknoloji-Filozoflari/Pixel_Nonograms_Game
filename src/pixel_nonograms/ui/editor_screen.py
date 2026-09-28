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
from pixel_nonograms.i18n import tr
from pixel_nonograms.importer import GRID_SIZES, ImageImportOptions
from pixel_nonograms.services import convert_image_to_puzzle, save_editor_puzzle
from pixel_nonograms.services.puzzle_library import DIFFICULTY_LABELS
from pixel_nonograms.services.puzzle_quality import assess_quality, quality_text
from pixel_nonograms.solver import SolveStatus

from .editor_canvas import EditorCanvas, EditorPreview
from .theme import set_theme_style


class ImageImportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Görselden Nonogram"))
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)
        self.size_box = QComboBox()
        for size in GRID_SIZES:
            self.size_box.addItem(tr(f"{size} × {size}"), size)
        self.size_box.setCurrentIndex(2)
        form.addRow(tr("Izgara"), self.size_box)
        self.mode_box = QComboBox()
        self.mode_box.addItem(tr("Siyah beyaz"), "mono")
        self.mode_box.addItem(tr("Renkli"), "color")
        form.addRow(tr("Dönüşüm"), self.mode_box)
        self.threshold_box = QSpinBox()
        self.threshold_box.setRange(1, 254)
        self.threshold_box.setValue(180)
        self.threshold_box.setToolTip(tr("Daha yüksek değer daha çok hücreyi doldurur"))
        form.addRow(tr("Doluluk eşiği"), self.threshold_box)
        self.colors_box = QSpinBox()
        self.colors_box.setRange(2, 8)
        self.colors_box.setValue(4)
        self.colors_box.setEnabled(False)
        self.mode_box.currentIndexChanged.connect(
            lambda: self.colors_box.setEnabled(self.mode_box.currentData() == "color")
        )
        form.addRow(tr("Renk sayısı"), self.colors_box)
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
        set_theme_style(
            self,
            """
            QWidget, QScrollArea { background: $paper; color: $text; font-size: 13px; }
            QLineEdit, QSpinBox, QComboBox, QPushButton { background: $button; color: $text;
                border: 1px solid $border; border-radius: 6px; padding: 6px 9px; }
            QPushButton:hover { background: $hover; }
            QPushButton:checked { background: $selected; border-color: $accent; }
            QPushButton:disabled { color: $disabled_text; background: $disabled; }
        """,
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        root.addLayout(header)
        self.back_button = QPushButton(tr("← Kütüphane"))
        self.back_button.clicked.connect(self.back_requested.emit)
        header.addWidget(self.back_button)
        title = QLabel(tr("Bulmaca Editörü"))
        set_theme_style(title, "font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch(1)
        self.import_button = QPushButton(tr("Görselden Oluştur"))
        self.import_button.clicked.connect(self.open_image_import)
        header.addWidget(self.import_button)
        self.quality_button = QPushButton(tr("Kalite Analizi"))
        self.quality_button.clicked.connect(self.analyze_quality)
        header.addWidget(self.quality_button)
        self.save_button = QPushButton(tr("Doğrula ve Kaydet"))
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
        self.tags_edit.setPlaceholderText(tr("Etiketler, virgülle ayrılmış"))
        self.difficulty_box = QComboBox()
        for difficulty in Difficulty:
            self.difficulty_box.addItem(tr(DIFFICULTY_LABELS[difficulty]), difficulty)
        for col, label, widget in (
            (0, "Başlık", self.title_edit),
            (2, "Yazar", self.author_edit),
            (4, "Zorluk", self.difficulty_box),
        ):
            metadata.addWidget(QLabel(tr(label)), 0, col)
            metadata.addWidget(widget, 0, col + 1)
        metadata.addWidget(QLabel(tr("Açıklama")), 1, 0)
        metadata.addWidget(self.description_edit, 1, 1, 1, 3)
        metadata.addWidget(QLabel(tr("Etiketler")), 1, 4)
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
            button = QPushButton(tr(caption))
            button.setCheckable(True)
            button.setChecked(tool == "pencil")
            button.clicked.connect(
                lambda checked=False, selected=tool: self.canvas.set_tool(selected)
            )
            group.addButton(button)
            tools.addWidget(button)
            self.tool_buttons[tool] = button
        tools.addSpacing(8)
        tools.addWidget(QLabel(tr("Palette")))
        self.palette_box = QComboBox()
        self.palette_box.currentIndexChanged.connect(self._select_color)
        tools.addWidget(self.palette_box)
        self.add_color_button = QPushButton(tr("+ Renk"))
        self.add_color_button.clicked.connect(self._add_color)
        tools.addWidget(self.add_color_button)
        self.edit_color_button = QPushButton(tr("Rengi Düzenle"))
        self.edit_color_button.clicked.connect(self._edit_color)
        tools.addWidget(self.edit_color_button)
        self.remove_color_button = QPushButton(tr("− Renk"))
        self.remove_color_button.clicked.connect(self._remove_color)
        tools.addWidget(self.remove_color_button)
        tools.addStretch(1)

        dimensions = QHBoxLayout()
        root.addLayout(dimensions)
        dimensions.addWidget(QLabel(tr("Izgara")))
        self.width_box = QSpinBox()
        self.height_box = QSpinBox()
        for box, value in (
            (self.width_box, self.draft.width),
            (self.height_box, self.draft.height),
        ):
            box.setRange(1, 100)
            box.setValue(value)
        dimensions.addWidget(self.width_box)
        dimensions.addWidget(QLabel(tr("×")))
        dimensions.addWidget(self.height_box)
        self.width_box.valueChanged.connect(self._resize_grid)
        self.height_box.valueChanged.connect(self._resize_grid)
        dimensions.addSpacing(10)
        self.clear_button = QPushButton(tr("Izgarayı Temizle"))
        self.clear_button.clicked.connect(self._clear_grid)
        dimensions.addWidget(self.clear_button)
        preview_button = QPushButton(tr("Önizleme"))
        preview_button.clicked.connect(self.show_preview)
        dimensions.addWidget(preview_button)
        dimensions.addStretch(1)
        self.clue_label = QLabel(tr("Hücreye gelince satır ve sütun ipuçları görünür."))
        set_theme_style(self.clue_label, "color: $muted;")
        dimensions.addWidget(self.clue_label)

        self.canvas = EditorCanvas(self.draft)
        self.canvas.changed.connect(self._on_grid_changed)
        self.canvas.hover_changed.connect(self._show_hover_clues)
        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(False)
        root.addWidget(scroll, 1)

        self.status_label = QLabel(tr("Çizimi tamamlayıp doğrulayarak kaydedin."))
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.quality_label = QLabel(tr("Mantıksal çözüm ve tek çözüm ayrı değerlendirilir."))
        self.quality_label.setWordWrap(True)
        root.addWidget(self.quality_label)
        self._refresh_palette()

    def analyze_quality(self) -> None:
        try:
            puzzle = self.draft.to_puzzle(title=self.title_edit.text(), author=self.author_edit.text())
            self.quality_label.setText(tr(quality_text(assess_quality(puzzle))))
        except ValueError as exc:
            self.quality_label.setText(tr(f"Analiz yapılamadı: {exc}"))

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
            self.status_label.setText(tr(f"Görsel dönüştürülemedi: {exc}"))
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
        self.title_edit.setText(tr(Path(path).stem[:200]))
        self._mark_changed()
        status_text = {
            SolveStatus.SOLVED: "Tek çözüm",
            SolveStatus.MULTIPLE_SOLUTIONS: "Birden fazla çözüm",
            SolveStatus.NO_SOLUTION: "Çözüm yok",
            SolveStatus.UNKNOWN_LIMIT: "Doğrulama sınırına ulaşıldı",
        }[result.status]
        self.status_label.setText(
            tr(f"Görsel {result.draft.width} × {result.draft.height} ızgaraya dönüştürüldü. "
            f"Solver: {status_text}. Kaydetmeden önce çizimi düzenleyebilirsiniz.")
        )

        self.analyze_quality()

    def _mark_changed(self, *_args) -> None:
        self.save_button.setEnabled(True)
        self.last_result = None
        self.quality_label.setText(tr("Çizim değişti; kalite analizini yenileyin."))

    def _on_grid_changed(self) -> None:
        self._mark_changed()
        self.status_label.setText(tr("Satır ve sütun ipuçları güncellendi."))

    def _show_hover_clues(self, text: str) -> None:
        self.clue_label.setText(tr(text or "Hücreye gelince satır ve sütun ipuçları görünür."))

    def _refresh_palette(self, preferred: int = 1) -> None:
        self.palette_box.blockSignals(True)
        self.palette_box.clear()
        for color_id, color in enumerate(self.draft.palette, 1):
            swatch = QPixmap(16, 16)
            swatch.fill(QColor(color))
            self.palette_box.addItem(QIcon(swatch), tr(f"{color_id}: {color}"), color_id)
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
            self.status_label.setText(tr(str(exc)))
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
            self.status_label.setText(tr(str(exc)))
            return
        self._refresh_palette(color_id)
        self._on_grid_changed()

    def _remove_color(self) -> None:
        color_id = self.palette_box.currentData()
        try:
            self.draft.remove_color(color_id)
        except ValueError as exc:
            self.status_label.setText(tr(str(exc)))
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
        dialog.setWindowTitle(tr("Bulmaca Önizlemesi"))
        layout = QVBoxLayout(dialog)
        layout.addWidget(EditorPreview(self.draft))
        close_button = QPushButton(tr("Kapat"))
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
            self.status_label.setText(tr(f"Kaydedilemedi: {exc}"))
            return
        self.analyze_quality()
        self.last_result = result
        messages = {
            SolveStatus.SOLVED: "Tek çözüm — bulmaca .nono dosyasına kaydedildi.",
            SolveStatus.MULTIPLE_SOLUTIONS: "Birden fazla çözüm — bulmaca kaydedilmedi.",
            SolveStatus.NO_SOLUTION: "Çözüm yok — bulmaca kaydedilmedi.",
            SolveStatus.UNKNOWN_LIMIT: "Doğrulama sınırına ulaşıldı — bulmaca kaydedilmedi.",
        }
        self.status_label.setText(tr(messages[result.status]))
        if result.status is SolveStatus.SOLVED:
            self.save_button.setEnabled(False)
            self.saved.emit(result.puzzle)
