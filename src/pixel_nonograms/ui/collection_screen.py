"""Offline puzzle browser with filters, sorting, and favorite cards."""

from PySide6.QtCore import QSettings, QSize, Qt, Signal
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import (
    QButtonGroup,
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

from pixel_nonograms.i18n import tr
from pixel_nonograms.services.inventory import ITEM_NAMES
from pixel_nonograms.services.puzzle_library import (
    DIFFICULTY_LABELS,
    PuzzleEntry,
    PuzzleLibrary,
    PuzzleQuery,
    PuzzleStatus,
)

from .branding import logo_pixmap
from .language_picker import LanguagePicker
from .progression import ProgressionDialog, progression_summary
from .theme import (
    PuzzlePreview,
    apply_theme,
    paint_wallpaper,
    set_theme_style,
    theme_for,
)


class PuzzleCard(QFrame):
    open_requested = Signal(str)
    favorite_changed = Signal(str, bool)

    def __init__(
        self, entry: PuzzleEntry, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.entry = entry
        puzzle = entry.puzzle
        self.setObjectName("puzzle_card")
        self.setFixedHeight(256)
        set_theme_style(
            self,
            """
            QFrame#puzzle_card { background: $panel; border: 1px solid $border;
                border-radius: 12px; }
            QFrame#puzzle_card:hover { border-color: $teal; }
            QFrame#puzzle_card QLabel { border: none; background: transparent;
                color: $text; }
            QFrame#puzzle_card QPushButton { background: $accent; color: $on_accent;
                border: 1px solid $accent; border-radius: 7px; padding: 9px 14px;
                font-weight: 700; }
            QFrame#puzzle_card QPushButton:hover { background: $accent; }
        """,
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(7)

        revealed = entry.status is PuzzleStatus.COMPLETED
        self.preview = PuzzlePreview(
            puzzle,
            self,
            revealed=revealed,
            cells=entry.preview_cells if entry.status is PuzzleStatus.IN_PROGRESS else None,
        )
        self.preview.setFixedSize(96, 96)
        layout.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)

        heading = QHBoxLayout()
        self.title_label = QLabel(tr(puzzle.title))
        self.title_label.setToolTip(tr(puzzle.title))
        self.title_label.setWordWrap(True)
        set_theme_style(self.title_label, "font-size: 13px; font-weight: 600;")
        heading.addWidget(self.title_label, 1)
        self.favorite_button = QToolButton()
        self.favorite_button.setCheckable(True)
        self.favorite_button.setChecked(entry.favorite)
        self.favorite_button.setText(tr("★" if entry.favorite else "☆"))
        set_theme_style(
            self.favorite_button,
            "color: $accent; background: transparent; font-size: 22px; border: none;",
        )
        self.favorite_button.setToolTip(
            tr("Favorilerden çıkar" if entry.favorite else "Favorilere ekle")
        )
        self.favorite_button.clicked.connect(self._favorite_clicked)
        heading.addWidget(self.favorite_button)
        layout.addLayout(heading)

        details = QLabel(
            tr(f"{puzzle.width} × {puzzle.height}   ·   "
            f"{DIFFICULTY_LABELS[puzzle.difficulty]}"
            + ("   ·   Renkli" if puzzle.is_colored else ""))
        )
        set_theme_style(details, "color: $muted; font-weight: 600;")
        layout.addWidget(details)
        if puzzle.reward_item_id is not None:
            reward_text = (
                f"Ödül alındı: {ITEM_NAMES[puzzle.reward_item_id]}"
                if entry.reward_claimed
                else f"İlk tamamlama ödülü: {ITEM_NAMES[puzzle.reward_item_id]}"
            )
            self.reward_label = QLabel(tr("✓ ◇" if entry.reward_claimed else "◇ +1"))
            self.reward_label.setToolTip(tr(reward_text))
            set_theme_style(self.reward_label, "color: $teal;")
            layout.addWidget(self.reward_label)
        self.progress_label = QLabel(tr("!" if entry.status is PuzzleStatus.ERROR else "✓" if revealed else f"{round(entry.progress)}%" if entry.progress else ""))
        self.progress_label.setToolTip(tr(self._progress_text(entry)))
        self.progress_label.hide()
        self.setToolTip(tr(self._progress_text(entry)))
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(round(entry.progress))
        progress_bar.setTextVisible(False)
        progress_bar.setFixedHeight(3)
        set_theme_style(
            progress_bar,
            """
            QProgressBar { background: $well; border: none; border-radius: 4px; }
            QProgressBar::chunk { background: $accent; border-radius: 4px; }
        """,
        )
        layout.addWidget(progress_bar)

        self.open_button = QPushButton(tr("↻" if revealed else "▶"))
        self.open_button.setToolTip(tr("Yeniden aç" if revealed else "Bulmacayı aç"))
        self.open_button.setAccessibleName(tr("Bulmacayı aç"))
        self.open_button.setFixedHeight(36)
        set_theme_style(self.open_button, """
            QPushButton { background: $primary; color: $on_primary; padding: 0;
                min-height: 34px; font-size: 20px; border: none; border-radius: 7px; }
            QPushButton:hover { background: $primary_hover; }
            QPushButton:disabled { background: $disabled; color: $disabled_text; }
        """)
        self.open_button.setEnabled(entry.status is not PuzzleStatus.ERROR)
        self.open_button.clicked.connect(lambda: self.open_requested.emit(puzzle.id))
        layout.addWidget(self.open_button)
        apply_theme(self, theme_for(self).name)

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
        self.favorite_button.setText(tr("★" if checked else "☆"))
        self.favorite_button.setToolTip(tr("Favorilerden çıkar" if checked else "Favorilere ekle"))
        self.favorite_changed.emit(self.entry.puzzle.id, checked)


class CollectionScreen(QWidget):
    puzzle_requested = Signal(str)
    editor_requested = Signal()
    language_changed = Signal(str)
    settings_requested = Signal()

    def __init__(
        self,
        library: PuzzleLibrary,
        parent: QWidget | None = None,
        *,
        settings: QSettings | None = None,
    ) -> None:
        super().__init__(parent)
        self.library = library
        self.settings = (
            settings
            if settings is not None
            else QSettings(
                QSettings.Format.IniFormat,
                QSettings.Scope.UserScope,
                "Pixel Nonograms",
                "Pixel Nonograms",
            )
        )
        self.setProperty("theme_name", "night")
        self.visible_entries: tuple[PuzzleEntry, ...] = ()
        self.cards: list[PuzzleCard] = []
        self.setObjectName("collection_screen")
        set_theme_style(
            self,
            """
            QWidget#card_container, QScrollArea { background: transparent; }
            QLabel, QCheckBox { background: transparent; color: $text; }
            QPushButton, QComboBox, QToolButton { background: $button; color: $text;
                border: 1px solid $border; border-radius: 8px; padding: 8px 12px; }
            QPushButton:hover, QToolButton:hover { background: $hover; }
            QPushButton:checked { background: $selected; color: $selected_text;
                border-color: $teal; }
            QScrollBar:vertical { background: $paper; width: 9px; margin: 0; }
            QScrollBar::handle:vertical { background: $border; border-radius: 5px;
                min-height: 28px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent; }
        """,
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)
        hero = QFrame()
        hero.setObjectName("collection_hero")
        set_theme_style(hero, """
            QFrame#collection_hero { background: $panel; border: 1px solid $border;
                border-radius: 12px; }
        """)
        heading = QHBoxLayout(hero)
        heading.setContentsMargins(20, 18, 20, 18)
        heading.setSpacing(14)
        root.addWidget(hero)
        emblem = QLabel()
        emblem.setPixmap(logo_pixmap(56))
        heading.addWidget(emblem)
        brand = QVBoxLayout()
        brand.setSpacing(3)
        title = QLabel(tr("PİKSEL NONOGRAM"))
        set_theme_style(title, "font-size: 24px; font-weight: 800; color: $accent;")
        brand.addWidget(title)
        tagline = QLabel(tr("Sayıları takip et. Pikselleri tamamla."))
        set_theme_style(tagline, "color: $muted; font-size: 13px;")
        brand.addWidget(tagline)
        heading.addLayout(brand, 1)
        self.language_picker = LanguagePicker(self, self.set_language)
        heading.addWidget(self.language_picker)
        from .tool_icons import tool_icon

        self.settings_button = QPushButton()
        self.settings_button.setIcon(tool_icon("settings"))
        self.settings_button.setToolTip(tr("Ayarlar"))
        self.settings_button.setAccessibleName(tr("Ayarlar"))
        self.settings_button.clicked.connect(self.settings_requested.emit)
        self.exit_button = QPushButton()
        self.exit_button.setIcon(tool_icon("exit"))
        self.exit_button.setToolTip(tr("Çıkış"))
        self.exit_button.setAccessibleName(tr("Çıkış"))
        self.exit_button.clicked.connect(lambda: self.window().close())
        for button in (self.settings_button, self.exit_button):
            button.setFixedSize(40, 40)
            button.setIconSize(QSize(22, 22))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            heading.addWidget(button)
        progression_row = QHBoxLayout()
        self.progression_label = QLabel()
        self.progression_label.setWordWrap(True)
        set_theme_style(self.progression_label, "color: $teal; font-weight: 600;")
        progression_row.addWidget(self.progression_label, 1)
        self.missions_button = QPushButton(tr("◇"))
        self.missions_button.setToolTip(tr("Görevler ve ödüller"))
        self.missions_button.setAccessibleName(tr("Görevler ve ödüller"))
        self.missions_button.setFixedWidth(38)
        self.missions_button.clicked.connect(self.open_progression)
        progression_row.addWidget(self.missions_button)
        root.addLayout(progression_row)
        category_bar = QFrame()
        category_bar.setObjectName("category_bar")
        set_theme_style(category_bar, """
            QFrame#category_bar { background: $well; border: 1px solid $border;
                border-radius: 12px; }
            QPushButton { background: transparent; color: $muted;
                border: 1px solid transparent; padding: 10px; font-weight: 600; }
            QPushButton:hover { background: $hover; color: $text; }
            QPushButton:checked { background: $selected; color: $selected_text;
                border: 1px solid $teal; }
        """)
        category_row = QHBoxLayout(category_bar)
        category_row.setContentsMargins(6, 6, 6, 6)
        category_row.setSpacing(5)
        root.addWidget(category_bar)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.category_buttons: dict[str, QPushButton] = {}
        self.category = "Tümü"
        for category in ("Tümü", "Kolay", "Orta", "Zor", "Uzman", "Renkli"):
            button = QPushButton(tr(category))
            button.setCheckable(True)
            button.setChecked(category == self.category)
            button.clicked.connect(
                lambda checked=False, value=category: self.select_category(value)
            )
            group.addButton(button)
            category_row.addWidget(button)
            self.category_buttons[category] = button

        self.count_label = QLabel()
        set_theme_style(self.count_label, "color: $muted; font-weight: 600;")
        root.addWidget(self.count_label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.card_container = QWidget()
        self.card_container.setObjectName("card_container")
        self.card_layout = QGridLayout(self.card_container)
        self.card_layout.setSpacing(12)
        self.card_layout.setContentsMargins(0, 0, 0, 0)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.card_container)
        root.addWidget(scroll, 1)
        self.refresh()
        apply_theme(self, "night")

    def open_progression(self) -> None:
        dialog = ProgressionDialog(self.library.database, self)
        dialog.exec()
        self.refresh()

    def open_tutorial(self) -> None:
        from .tutorial import open_tutorial

        open_tutorial(self, self.settings)

    def set_language(self, code: str) -> None:
        from pixel_nonograms.i18n import set_language, translate_widgets

        self.settings.setValue("language", code)
        set_language(code)
        translate_widgets(self)
        self.language_changed.emit(code)

    def select_category(self, category: str) -> None:
        if category not in self.category_buttons:
            raise ValueError("Bilinmeyen kategori")
        self.category = category
        self.category_buttons[category].setChecked(True)
        self.refresh()

    def refresh(self, *_args) -> None:
        load_error = False
        try:
            entries = self.library.entries()
            summary = progression_summary(self.library.database)
            self.progression_label.setText(tr(summary.split("\n")[0]))
            self.progression_label.setToolTip(tr(summary))
            self.visible_entries = self.library.filter_entries(entries, PuzzleQuery(category=self.category))
        except Exception as exc:
            load_error = True
            self.visible_entries = ()
            self.count_label.setText(tr(f"Kütüphane yüklenemedi: {exc}"))
        else:
            self.count_label.setText(tr(f"{len(self.visible_entries)} bulmaca"))
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.cards = []
        for index, entry in enumerate(self.visible_entries):
            card = PuzzleCard(entry, self)
            card.open_requested.connect(self.puzzle_requested)
            card.favorite_changed.connect(self._set_favorite)
            self.card_layout.addWidget(card, index // self._card_columns(), index % self._card_columns())
            self.cards.append(card)
        if not self.visible_entries:
            empty = QLabel(
                tr("Kütüphane yüklenemedi." if load_error else "Bu filtrelere uygun bulmaca yok.")
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.card_layout.addWidget(empty, 0, 0, 1, 3)

    def _card_columns(self):
        return max(2, min(8, (self.width() - 64) // 205))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "cards"):
            for index, card in enumerate(self.cards):
                self.card_layout.addWidget(card, index // self._card_columns(), index % self._card_columns())

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        paint_wallpaper(painter, self)
        painter.end()

    def _set_favorite(self, puzzle_id: str, favorite: bool) -> None:
        try:
            self.library.set_favorite(puzzle_id, favorite)
        except Exception as exc:
            self.refresh()
            self.count_label.setText(tr(f"Favori kaydedilemedi: {exc}"))
        else:
            self.refresh()
