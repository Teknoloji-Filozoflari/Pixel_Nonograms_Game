"""Offline puzzle browser with filters, sorting, and favorite cards."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pixel_nonograms.core import Difficulty
from pixel_nonograms.services.inventory import ITEM_NAMES
from pixel_nonograms.services.puzzle_library import (
    CATEGORIES,
    DIFFICULTY_LABELS,
    PuzzleEntry,
    PuzzleLibrary,
    PuzzleQuery,
    PuzzleSort,
    PuzzleStatus,
)

from .theme import PuzzlePreview, paint_wallpaper


class PuzzleCard(QFrame):
    open_requested = Signal(str)
    favorite_changed = Signal(str, bool)

    def __init__(self, entry: PuzzleEntry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.entry = entry
        puzzle = entry.puzzle
        self.setObjectName("puzzle_card")
        self.setStyleSheet("""
            QFrame#puzzle_card { background: #252E36; border: 1px solid #58666D;
                border-radius: 12px; }
            QFrame#puzzle_card QLabel { border: none; background: transparent;
                color: #E8E7DF; }
            QFrame#puzzle_card QPushButton { background: #B68A4C; color: #182028;
                border: 1px solid #D3A65C; border-radius: 7px; padding: 9px 14px;
                font-weight: 700; }
            QFrame#puzzle_card QPushButton:hover { background: #D3A65C; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 17, 18, 18)
        layout.setSpacing(10)

        self.preview = PuzzlePreview(puzzle)
        self.preview.setFixedSize(144, 144)
        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)

        heading = QHBoxLayout()
        self.title_label = QLabel(puzzle.title)
        self.title_label.setStyleSheet("font-size: 19px; font-weight: 700;")
        heading.addWidget(self.title_label, 1)
        self.favorite_button = QToolButton()
        self.favorite_button.setCheckable(True)
        self.favorite_button.setChecked(entry.favorite)
        self.favorite_button.setText("★" if entry.favorite else "☆")
        self.favorite_button.setStyleSheet(
            "color: #E8BD78; background: transparent; font-size: 22px; border: none;"
        )
        self.favorite_button.setToolTip(
            "Favorilerden çıkar" if entry.favorite else "Favorilere ekle"
        )
        self.favorite_button.clicked.connect(self._favorite_clicked)
        heading.addWidget(self.favorite_button)
        layout.addLayout(heading)

        details = QLabel(
            f"{puzzle.width} × {puzzle.height}   ·   "
            f"{DIFFICULTY_LABELS[puzzle.difficulty]}"
            + ("   ·   Renkli" if puzzle.is_colored else "")
        )
        details.setStyleSheet("color: #B8C1C2; font-weight: 600;")
        layout.addWidget(details)
        if puzzle.reward_item_id is not None:
            reward_text = (
                f"Ödül alındı: {ITEM_NAMES[puzzle.reward_item_id]}"
                if entry.reward_claimed
                else f"İlk tamamlama ödülü: {ITEM_NAMES[puzzle.reward_item_id]}"
            )
            self.reward_label = QLabel(reward_text)
            self.reward_label.setStyleSheet("color: #E8BD78;")
            layout.addWidget(self.reward_label)
        self.progress_label = QLabel(self._progress_text(entry))
        layout.addWidget(self.progress_label)
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(round(entry.progress))
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(9)
        progress_bar.setStyleSheet("""
            QProgressBar { background: #3C4850; border: none; border-radius: 4px; }
            QProgressBar::chunk { background: #D3A65C; border-radius: 4px; }
        """)
        layout.addWidget(progress_bar)

        self.open_button = QPushButton(
            "DEVAM ET"
            if entry.status is PuzzleStatus.IN_PROGRESS
            else "YENİDEN AÇ"
            if entry.status is PuzzleStatus.COMPLETED
            else "OYNA"
        )
        self.open_button.setEnabled(entry.status is not PuzzleStatus.ERROR)
        self.open_button.clicked.connect(lambda: self.open_requested.emit(puzzle.id))
        layout.addWidget(self.open_button)

    @staticmethod
    def _progress_text(entry: PuzzleEntry) -> str:
        if entry.status is PuzzleStatus.ERROR:
            return f"Kayıt hatası: {entry.error}"
        if entry.status is PuzzleStatus.COMPLETED:
            return "Tamamlandı"
        if entry.status is PuzzleStatus.UNSTARTED:
            return "Başlanmamış"
        return "Devam ediyor"

    def _favorite_clicked(self, checked: bool) -> None:
        self.favorite_button.setText("★" if checked else "☆")
        self.favorite_button.setToolTip("Favorilerden çıkar" if checked else "Favorilere ekle")
        self.favorite_changed.emit(self.entry.puzzle.id, checked)


class CollectionScreen(QWidget):
    puzzle_requested = Signal(str)
    editor_requested = Signal()

    def __init__(self, library: PuzzleLibrary, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.library = library
        self.visible_entries: tuple[PuzzleEntry, ...] = ()
        self.cards: list[PuzzleCard] = []
        self.setObjectName("collection_screen")
        self.setStyleSheet("""
            QWidget#card_container, QScrollArea { background: transparent; }
            QLabel, QCheckBox { background: transparent; color: #E8E7DF; }
            QPushButton, QComboBox, QToolButton { background: #2D3740; color: #E8E7DF;
                border: 1px solid #66717A; border-radius: 8px; padding: 8px 12px; }
            QPushButton:hover, QToolButton:hover { background: #3D4A54; }
            QPushButton:checked { background: #B68A4C; color: #182028;
                border-color: #D3A65C; }
            QScrollBar:vertical { background: #202830; width: 12px; margin: 0; }
            QScrollBar::handle:vertical { background: #596873; border-radius: 5px;
                min-height: 28px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(16)
        heading = QHBoxLayout()
        root.addLayout(heading)
        title = QLabel("NONOGRAM ATÖLYESİ")
        title.setStyleSheet("font-size: 26px; font-weight: 800; color: #F0D6A6;")
        heading.addWidget(title)
        heading.addStretch(1)
        editor_button = QPushButton("+ Kendi Bulmacanı Oluştur")
        editor_button.clicked.connect(self.editor_requested.emit)
        heading.addWidget(editor_button)
        subtitle = QLabel("Bir desen seç, sayıların izini sür.")
        subtitle.setStyleSheet("color: #B8C1C2; font-size: 14px;")
        root.addWidget(subtitle)

        category_row = QHBoxLayout()
        root.addLayout(category_row)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.category_buttons: dict[str, QPushButton] = {}
        self.category = "Tümü"
        for category in ("Tümü", "Kolay", "Orta", "Zor", "Uzman"):
            button = QPushButton(category)
            button.setCheckable(True)
            button.setChecked(category == self.category)
            button.clicked.connect(
                lambda checked=False, value=category: self.select_category(value)
            )
            group.addButton(button)
            category_row.addWidget(button)
            self.category_buttons[category] = button

        filters = QHBoxLayout()
        root.addLayout(filters)
        self.size_combo = QComboBox()
        self.size_combo.addItem("Tüm boyutlar", None)
        for width, height in sorted({(p.width, p.height) for p in library.puzzles}):
            self.size_combo.addItem(f"{width} × {height}", f"{width}x{height}")
        filters.addWidget(self.size_combo)
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItem("Tüm zorluklar", None)
        for difficulty in Difficulty:
            self.difficulty_combo.addItem(DIFFICULTY_LABELS[difficulty], difficulty)
        filters.addWidget(self.difficulty_combo)
        self.color_combo = QComboBox()
        for label, value in (
            ("Tüm renk türleri", "all"),
            ("Siyah beyaz", "mono"),
            ("Renkli", "color"),
        ):
            self.color_combo.addItem(label, value)
        filters.addWidget(self.color_combo)
        self.status_combo = QComboBox()
        for label, value in (
            ("Tüm durumlar", None),
            ("Tamamlanan", PuzzleStatus.COMPLETED),
            ("Devam eden", PuzzleStatus.IN_PROGRESS),
            ("Başlanmamış", PuzzleStatus.UNSTARTED),
        ):
            self.status_combo.addItem(label, value)
        filters.addWidget(self.status_combo)
        self.favorites_checkbox = QCheckBox("Yalnız favoriler")
        filters.addWidget(self.favorites_checkbox)
        filters.addStretch(1)
        self.sort_combo = QComboBox()
        for label, value in (
            ("Ada göre", PuzzleSort.NAME),
            ("Boyuta göre", PuzzleSort.SIZE),
            ("Zorluğa göre", PuzzleSort.DIFFICULTY),
            ("Son oynanana göre", PuzzleSort.LAST_PLAYED),
            ("İlerlemeye göre", PuzzleSort.PROGRESS),
        ):
            self.sort_combo.addItem(label, value)
        filters.addWidget(self.sort_combo)
        for combo in (
            self.size_combo,
            self.difficulty_combo,
            self.color_combo,
            self.status_combo,
            self.sort_combo,
        ):
            combo.currentIndexChanged.connect(self.refresh)
        self.favorites_checkbox.toggled.connect(self.refresh)

        self.count_label = QLabel()
        self.count_label.setStyleSheet("color: #BBC5C3; font-weight: 600;")
        root.addWidget(self.count_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.card_container = QWidget()
        self.card_container.setObjectName("card_container")
        self.card_layout = QGridLayout(self.card_container)
        self.card_layout.setSpacing(14)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.card_container)
        root.addWidget(scroll, 1)
        self.refresh()

    def select_category(self, category: str) -> None:
        if category not in CATEGORIES:
            raise ValueError("Bilinmeyen kategori")
        self.category = category
        self.category_buttons[category].setChecked(True)
        self.refresh()

    def _query(self) -> PuzzleQuery:
        size = self.size_combo.currentData()
        difficulty = self.difficulty_combo.currentData()
        status = self.status_combo.currentData()
        return PuzzleQuery(
            category=self.category,
            size=tuple(map(int, size.split("x"))) if size is not None else None,
            difficulty=Difficulty(difficulty) if difficulty is not None else None,
            color_mode=self.color_combo.currentData(),
            status=PuzzleStatus(status) if status is not None else None,
            favorites_only=self.favorites_checkbox.isChecked(),
            sort=PuzzleSort(self.sort_combo.currentData()),
        )

    def refresh(self, *_args) -> None:
        sizes = sorted({(p.width, p.height) for p in self.library.puzzles})
        current_sizes = {
            self.size_combo.itemData(index) for index in range(1, self.size_combo.count())
        }
        expected_sizes = {f"{width}x{height}" for width, height in sizes}
        if current_sizes != expected_sizes:
            selected_size = self.size_combo.currentData()
            self.size_combo.blockSignals(True)
            self.size_combo.clear()
            self.size_combo.addItem("Tüm boyutlar", None)
            for width, height in sizes:
                self.size_combo.addItem(f"{width} × {height}", f"{width}x{height}")
            if selected_size is not None:
                index = self.size_combo.findData(selected_size)
                if index >= 0:
                    self.size_combo.setCurrentIndex(index)
            self.size_combo.blockSignals(False)
        load_error = False
        try:
            self.visible_entries = self.library.query(self._query())
        except Exception as exc:
            load_error = True
            self.visible_entries = ()
            self.count_label.setText(f"Kütüphane yüklenemedi: {exc}")
        else:
            self.count_label.setText(f"{len(self.visible_entries)} bulmaca")
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.cards = []
        for index, entry in enumerate(self.visible_entries):
            card = PuzzleCard(entry)
            card.open_requested.connect(self.puzzle_requested)
            card.favorite_changed.connect(self._set_favorite)
            self.card_layout.addWidget(card, index // 3, index % 3)
            self.cards.append(card)
        if not self.visible_entries:
            empty = QLabel(
                "Kütüphane yüklenemedi." if load_error else "Bu filtrelere uygun bulmaca yok."
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.addWidget(empty, 0, 0, 1, 3)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        paint_wallpaper(painter, self)
        painter.end()

    def _set_favorite(self, puzzle_id: str, favorite: bool) -> None:
        try:
            self.library.set_favorite(puzzle_id, favorite)
        except Exception as exc:
            self.refresh()
            self.count_label.setText(f"Favori kaydedilemedi: {exc}")
        else:
            self.refresh()
