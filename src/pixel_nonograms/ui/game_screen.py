"""Playable board and compact tool strip."""

from PySide6.QtCore import QPropertyAnimation, QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QActionGroup, QColor, QIcon, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWidgetAction,
)

from pixel_nonograms.core import GameSession, HelperItemId
from pixel_nonograms.core.progression import MISSIONS
from pixel_nonograms.i18n import tr
from pixel_nonograms.persistence import SaveManager
from pixel_nonograms.rendering import BoardWidget
from pixel_nonograms.services import ITEM_NAMES, InventoryService
from pixel_nonograms.services.inventory import AREA_SIZES
from pixel_nonograms.solver import HintPlan

from .floating_board import BoardDragHandle, FloatingBoardStage
from .inventory_toolbar import InventoryToolbar
from .language_picker import LanguagePicker
from .progression import mission_reward_text, progression_summary
from .theme import (
    PuzzlePreview,
    apply_theme,
    paint_wallpaper,
    set_theme_style,
    theme_for,
)
from .tool_icons import tool_icon


class GameScreen(QWidget):
    back_requested = Signal()
    next_requested = Signal()
    language_changed = Signal(str)

    def __init__(
        self,
        session: GameSession,
        parent: QWidget | None = None,
        *,
        settings: QSettings | None = None,
        save_manager: SaveManager | None = None,
        inventory: InventoryService | None = None,
        autosave_interval_ms: int = 30_000,
        show_back_button: bool = False,
    ) -> None:
        super().__init__(parent)
        self.session = session
        self.save_manager = save_manager
        self.inventory = inventory
        self._active_hint_plan: HintPlan | None = None
        self._hint_level = 0
        if type(autosave_interval_ms) is not int or autosave_interval_ms < 1:
            raise ValueError("Otomatik kayıt aralığı pozitif olmalı")
        self._last_completion = session.completed
        self.completion_dialog: QDialog | None = None
        self.has_next_puzzle = False
        self._show_back_button = show_back_button
        self.board_fullscreen_dialog = None
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
        session.auto_x_completed_lines = self.settings.value("assist/auto_x", False, type=bool)
        session.auto_x_crossed_lines = self.settings.value("assist/clue_x", True, type=bool)
        self.setObjectName("game_screen")
        display_title = (
            session.puzzle.title
        )
        self.setWindowTitle(tr(f"Nonogram · {display_title}"))
        self.resize(1000, 780)
        set_theme_style(
            self,
            """
            QLabel { background: transparent; color: $text; font-size: 13px; }
            QPushButton, QComboBox { background: $button; color: $text;
                border: 1px solid $border; border-radius: 7px;
                padding: 7px 10px; min-height: 20px; }
            QPushButton:hover { background: $hover; }
            QPushButton:checked { background: $selected; color: $selected_text;
                border-color: $teal; }
            QPushButton:disabled { color: $disabled_text; background: $disabled; }
            QMenu { background: $panel; color: $text; border: 1px solid $border; }
            QMenu::item:selected { background: $selected; }
        """,
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 12)
        root.setSpacing(8)

        header_panel = QFrame()
        header_panel.setObjectName("game_header")
        set_theme_style(header_panel, """
            QFrame#game_header { background: $panel; border: 1px solid $border;
                border-radius: 12px; }
        """)
        header = QHBoxLayout(header_panel)
        header.setContentsMargins(12, 10, 12, 10)
        self.back_button = self._icon_button("back", tr("Kütüphaneye dön"))
        self.back_button.clicked.connect(self.return_to_library)
        self.back_button.setVisible(show_back_button)
        header.addWidget(self.back_button)
        title = QLabel(tr(display_title))
        self.title_label = title
        set_theme_style(title, "font-size: 22px; font-weight: 800; color: $accent;")
        header.addWidget(title)
        header.addStretch(1)
        self.language_picker = LanguagePicker(self, self.set_language)
        header.addWidget(self.language_picker)
        self.status_label = QLabel()
        header.addWidget(self.status_label)
        self.save_status_label = QLabel()
        set_theme_style(self.save_status_label, "color: $danger;")
        self.save_status_label.hide()
        header.addWidget(self.save_status_label)
        settings_button = self._icon_button("settings", tr("Ayarlar"), size=40)
        self.settings_button = settings_button
        settings_menu = QMenu(settings_button)
        tutorial_action = settings_menu.addAction(tr("Uygulamalı öğretici"))
        tutorial_action.triggered.connect(self.open_tutorial)
        self.reduce_motion_action = settings_menu.addAction(tr("Hareketi azalt"))
        self.reduce_motion_action.setCheckable(True)
        self.reduce_motion_action.setChecked(
            self.settings.value("appearance/reduce_motion", False, type=bool)
        )
        self.reduce_motion_action.toggled.connect(
            lambda value: self.settings.setValue("appearance/reduce_motion", value)
        )
        help_action = settings_menu.addAction(tr("Nasıl oynanır?"))
        help_action.triggered.connect(
            lambda: QMessageBox.information(
                self,
                tr("Oyun kontrolleri"),
                tr("Dolu kareye aynı renkle tekrar tıklayarak boyayı kaldır. "
                "İpucu sayısına tıklayarak çizik at veya kaldır; kaldırınca yalnız o çizginin otomatik X'leri kaldırılır; elle konanlar korunur. "
                "Bir satır veya sütunun tüm sayılarını çizdiğinde kalan boş kareler X olur. "
                "Kalem notları kesin işaret değildir ve çözümü etkilemez. Sağ tık X koyar. Sürüklemede ilk hareket yönü kilitlenir; ayarlardan kapatılabilir. "
                "Sayaç geçilen farklı hücreleri sayar. Büyük bulmacalarda ipucu yazısını "
                "büyüt veya okunabilir yakınlaştırmayı kullan; uzun ipucu şeritlerinde fare "
                "tekerleğiyle sayıları kaydır. Üst şeridi sürükleyerek çerçeveyi taşı; "
                "orta tuş veya taşıma aracıyla yakınlaştırılmış ızgarayı kaydır."),
            )
        )
        settings_button.setMenu(settings_menu)
        header.addWidget(settings_button)
        self.exit_button = self._icon_button("exit", tr("Çıkış"), size=40)
        self.exit_button.clicked.connect(lambda: self.window().close())
        header.addWidget(self.exit_button)
        root.addWidget(header_panel)

        self.board_stage = FloatingBoardStage()
        self.board_shell = QFrame(self.board_stage)
        self.board_shell.setObjectName("game_board_shell")
        set_theme_style(
            self.board_shell,
            """
            QFrame#game_board_shell { background: $panel;
                border: 1px solid $border; border-radius: 6px; }
        """,
        )
        shell_layout = QVBoxLayout(self.board_shell)
        shell_layout.setContentsMargins(7, 7, 7, 7)
        shell_layout.setSpacing(4)
        self.board_drag_handle = BoardDragHandle()
        shell_layout.addWidget(self.board_drag_handle)
        self.board = BoardWidget(session)
        self.board.auto_cross_clues = self.settings.value("assist/auto_clues", False, type=bool)
        self.board.show_errors = self.settings.value("assist/errors", True, type=bool)
        assist_menu = settings_menu.addMenu(tr("Yardım tercihleri"))
        self.assist_actions = {}
        for key, text, value in (
            (
                "auto_x",
                "Tamamlanan çizgilerin boşlarını otomatik X yap",
                session.auto_x_completed_lines,
            ),
            ("clue_x", "Son sayıyı çizince kalan hücreleri X yap", session.auto_x_crossed_lines),
            ("auto_clues", "Kesin tamamlanan sayıları otomatik çiz", self.board.auto_cross_clues),
            ("errors", "Çizgide fazla dolu hücre uyarısı göster", self.board.show_errors),
        ):
            action = assist_menu.addAction(tr(text))
            action.setCheckable(True)
            action.setChecked(value)
            action.toggled.connect(lambda enabled, option=key: self._set_assist(option, enabled))
            self.assist_actions[key] = action
        self.board.axis_lock = self.settings.value("controls/axis_lock", True, type=bool)
        self.board.pin_clues = self.settings.value("view/pin_clues", True, type=bool)
        self.board.expanded_clues = self.settings.value("view/expanded_clues", False, type=bool)
        try:
            font_size = int(self.settings.value("view/clue_font_size", 15))
        except (TypeError, ValueError):
            font_size = 15
        self.board.clue_font_size = font_size if font_size in (12, 15, 18, 22) else 15
        settings_menu.addSeparator()
        self.axis_lock_action = settings_menu.addAction(tr("Sürüklemeyi yatay/dikey kilitle"))
        self.axis_lock_action.setCheckable(True)
        self.axis_lock_action.setChecked(self.board.axis_lock)
        self.axis_lock_action.toggled.connect(self._set_axis_lock)
        self.pin_clues_action = settings_menu.addAction(tr("İpucu şeritlerini sabitle"))
        self.pin_clues_action.setCheckable(True)
        self.pin_clues_action.setChecked(self.board.pin_clues)
        self.pin_clues_action.toggled.connect(
            lambda value: self._set_board_view("pin_clues", value)
        )
        self.expanded_clues_action = settings_menu.addAction(tr("Geniş ipucu şeritleri"))
        self.expanded_clues_action.setCheckable(True)
        self.expanded_clues_action.setChecked(self.board.expanded_clues)
        self.expanded_clues_action.toggled.connect(
            lambda value: self._set_board_view("expanded_clues", value)
        )
        font_menu = settings_menu.addMenu(tr("İpucu yazı boyutu"))
        font_group = QActionGroup(self)
        font_group.setExclusive(True)
        self.clue_font_actions = {}
        for size, label in ((12, "Küçük"), (15, "Normal"), (18, "Büyük"), (22, "Çok büyük")):
            action = font_menu.addAction(tr(label))
            action.setCheckable(True)
            action.setChecked(size == self.board.clue_font_size)
            font_group.addAction(tr(action))
            action.triggered.connect(
                lambda checked=False, value=size: self._set_board_view("clue_font_size", value)
            )
            self.clue_font_actions[size] = action
        self.readable_zoom_action = settings_menu.addAction(tr("İpuçlarını okuyacak kadar yakınlaştır"))
        self.readable_zoom_action.triggered.connect(self.board.readable_zoom)
        self.stroke_label = QLabel()
        self.stroke_label.setMinimumWidth(0)
        set_theme_style(self.stroke_label, "color: $accent; font-weight: 600;")
        header.insertWidget(2, self.stroke_label)
        self.board.stroke_changed.connect(self.stroke_label.setText)
        shell_layout.addWidget(self.board)
        self.board_stage.attach(self.board_shell, self.board)
        self.board_drag_handle.dragged.connect(self.board_stage.drag_by)
        self.board.session_changed.connect(self._refresh_status)
        self.board.session_changed.connect(self._on_session_changed)
        self.clue_focus_label = QLabel(tr("Aktif hücrenin satır ve sütun ipuçları burada görünür."))
        set_theme_style(
            self.clue_focus_label,
            "color: $muted; background: $panel; border: 1px solid $border;border-radius: 5px; padding: 5px 9px; font-size: 12px;",
        )
        self.clue_focus_label.setWordWrap(True)
        self.assumption_banner = QLabel(
            tr("DENEME MODU · Kesik çerçeveler geçici hamlelerdir. ✓ Kabul et veya × İptal et.")
        )
        self.assumption_banner.setWordWrap(True)
        set_theme_style(
            self.assumption_banner,
            "color: $text; background: $selected; border: 2px dashed $accent; padding: 6px;",
        )
        self.clue_focus_label.hide()
        self.board.active_clues_changed.connect(self.clue_focus_label.setText)

        tools = QHBoxLayout()
        tools.setSpacing(6)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.tool_buttons = {}
        for key, caption in (
            ("fill", "Doldur"),
            ("empty", "X işareti"),
            ("note", "Kalem notu (aynı nota tekrar basarak sil)"),
            ("pan", "Tahtayı taşı"),
        ):
            button = self._icon_button(key, tr(caption))
            button.setCheckable(True)
            button.setChecked(key == "fill")
            if key == "note":
                button.clicked.connect(self._open_marker_menu)
            else:
                button.clicked.connect(lambda checked=False, tool=key: self._select_tool(tool))
            group.addButton(button)
            tools.addWidget(button)
            self.tool_buttons[key] = button

        self.marker_menu = QMenu(self)
        panel = QWidget()
        marker_grid = QGridLayout(panel)
        marker_grid.setContentsMargins(8, 8, 8, 8)
        marker_grid.setSpacing(5)
        marker_group = QButtonGroup(panel)
        self.marker_buttons = {}
        self.clear_marker_button = self._icon_button("clear", tr("İşareti sil"))
        self.clear_marker_button.setText(tr("İşareti sil"))
        self.clear_marker_button.setFixedWidth(224)
        self.clear_marker_button.clicked.connect(self._select_clear_marker)
        marker_grid.addWidget(self.clear_marker_button, 0, 0, 1, 6)
        symbols = ("A", "B", "C", "!", "?", "☯", "", "/", "←", "→", "↑", "↓")
        for index, symbol in enumerate(symbols):
            button = QPushButton(tr(symbol or "•"))
            button.setFixedSize(34, 34)
            button.setCheckable(True)
            button.setChecked(symbol == "")
            button.setToolTip(tr(f"Geçici işaret: {symbol or 'Nokta'}"))
            button.setAccessibleName(tr(f"Geçici işaret {symbol or 'Nokta'}"))
            button.clicked.connect(lambda checked=False, value=symbol: self._select_marker(value))
            marker_group.addButton(button)
            marker_grid.addWidget(button, 1 + index // 6, index % 6)
            self.marker_buttons[symbol] = button
        action = QWidgetAction(self.marker_menu)
        action.setDefaultWidget(panel)
        self.marker_menu.addAction(tr(action))
        set_theme_style(panel, """
            QWidget { background: $panel; color: $text; }
            QPushButton { padding: 0; min-height: 0; font-size: 19px;
                border: 1px solid $border; border-radius: 4px; background: $button; }
            QPushButton:checked { background: $selected; color: $selected_text;
                border-color: $teal; }
        """)

        self.color_picker = QComboBox()
        self.color_picker.setIconSize(QSize(24, 24))
        for index, color in enumerate(session.puzzle.palette, 1):
            swatch = QPixmap(24, 24)
            swatch.fill(QColor(color))
            self.color_picker.addItem(QIcon(swatch), tr(f"Renk {index}"), index)
        self.color_picker.currentIndexChanged.connect(self._select_color)
        self.color_picker.setToolTip(tr("Doldurma rengi"))
        self.color_picker.setAccessibleName(tr("Doldurma rengi"))
        if len(session.puzzle.palette) == 1:
            self.color_picker.hide()
        tools.addWidget(self.color_picker)
        self.color_buttons = {}
        if session.puzzle.is_colored:
            self.color_picker.hide()
            color_group = QButtonGroup(self)
            for index, color in enumerate(session.puzzle.palette, 1):
                button = QPushButton(tr(str(index)))
                button.setFixedSize(32, 32)
                button.setCheckable(True)
                button.setChecked(index == 1)
                button.setToolTip(tr(f"Renk {index} · {color}"))
                button.setAccessibleName(tr(f"Doldurma rengi {index}"))
                from .theme import contrasting_ink
                foreground = contrasting_ink(QColor(color)).name()
                button.setStyleSheet(
                    f"QPushButton {{ background: {color}; color: {foreground}; padding: 0; "
                    "border: 2px solid transparent; border-radius: 5px; }"
                    f"QPushButton:checked {{ border: 2px solid {foreground}; }}"
                )
                button.clicked.connect(lambda checked=False, value=index: self.color_picker.setCurrentIndex(value - 1))
                color_group.addButton(button)
                tools.addWidget(button)
                self.color_buttons[index] = button
        tools.addWidget(self._tool_separator())

        self.undo_button = self._tool_button(tools, "undo", "Geri al", self.board.undo)
        self.redo_button = self._tool_button(tools, "redo", "İleri al", self.board.redo)
        tools.addWidget(self._tool_separator())
        tools.addStretch(1)
        self._tool_button(tools, "zoom_out", "Uzaklaştır", lambda: self.board.zoom(1 / 1.2))
        self._tool_button(tools, "zoom_in", "Yakınlaştır", lambda: self.board.zoom(1.2))
        self._tool_button(tools, "fit", "Ekrana sığdır", self.board.fit_to_screen)
        self.fullscreen_button = self._tool_button(
            tools, "fullscreen", "Bulmacayı tam ekran aç · F11", self.toggle_board_fullscreen
        )
        tools.addWidget(self._tool_separator())
        self.assumption_start_button = self._tool_button(
            tools, "trial", "Deneme modunu başlat", self.board.begin_assumption
        )
        self.assumption_accept_button = self._tool_button(
            tools, "accept", "Denemeyi kabul et", self.board.accept_assumption
        )
        self.assumption_cancel_button = self._tool_button(
            tools, "cancel", "Denemeyi iptal et", self.board.cancel_assumption
        )

        if self.inventory is not None:
            self.inventory_toolbar = InventoryToolbar(session.puzzle, self, compact=True)
            self.inventory_toolbar.use_requested.connect(self._use_inventory_item)
            self.inventory_toolbar.next_hint_requested.connect(self._advance_hint)
            self.inventory_toolbar.selection_changed.connect(self._inventory_selection_changed)
            self.board.area_target_selected.connect(self._apply_area_helper)
            self.board.line_target_selected.connect(self._apply_line_helper)
            self.hints_button = self._icon_button("hint", tr("İpuçları"))
            self.hints_button.clicked.connect(self._open_hints_menu)
            tools.insertWidget(4, self.hints_button)
            self._refresh_inventory()

        toolbar = QFrame()
        self.toolbar = toolbar
        toolbar.setObjectName("game_toolbar")
        set_theme_style(
            toolbar,
            """
            QFrame#game_toolbar { background: $panel; border: 1px solid $border;
                border-radius: 9px; }
            QFrame#game_toolbar QPushButton { background: $button;
                border: 1px solid $border; border-radius: 6px; padding: 0; }
            QFrame#game_toolbar QPushButton:hover { background: $hover; }
            QFrame#game_toolbar QPushButton:checked { background: $selected;
                border: 2px solid $teal; }
            QFrame#game_toolbar QPushButton:disabled { background: $disabled;
                border-color: $disabled; }
        """,
        )
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 7, 8, 7)
        toolbar_layout.addLayout(tools)
        root.addWidget(toolbar)
        root.addWidget(self.assumption_banner)
        if self.inventory is not None:
            root.addWidget(self.inventory_toolbar)
        root.addWidget(self.board_stage, 1)

        for sequence, handler in (
            ("Ctrl+Z", self.board.undo),
            ("Ctrl+Y", self.board.redo),
            ("Ctrl+Shift+Z", self.board.redo),
            ("F", self.board.fit_to_screen),
        ):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(autosave_interval_ms)
        self._autosave_timer.timeout.connect(self.save_now)
        if self.save_manager is not None:
            self._autosave_timer.start()
        self._refresh_status()
        apply_theme(self, "night")

    def open_tutorial(self) -> None:
        from .tutorial import open_tutorial

        self.board.finish_active_stroke()
        open_tutorial(self, self.settings)

    def toggle_board_fullscreen(self) -> None:
        if self.board_fullscreen_dialog is not None:
            self.exit_board_fullscreen()
            return
        self.board.finish_active_stroke()
        self.marker_menu.close()
        if self.inventory is not None:
            self.inventory_toolbar.menu.close()
        dialog = QDialog(self, Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        dialog.setGeometry(self.window().screen().geometry())
        self.board_fullscreen_dialog = dialog
        dialog.setWindowTitle(tr("Bulmaca · Tam ekran"))
        set_theme_style(dialog, "QDialog { background: $paper; }")
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.layout().removeWidget(self.board_stage)
        self._normal_max_cell_size = self.board.camera.max_cell_size
        self._normal_pin_clues = self.board.pin_clues
        self.board.fullscreen_clues = True
        self.board.pin_clues = True
        self.board.row_clue_offset = self.board.column_clue_offset = 0
        self.board.camera.max_cell_size = max(dialog.width(), dialog.height())
        self.board_stage.expanded = True
        self.board_drag_handle.hide()
        layout.addWidget(self.board_stage, 1)
        self.board_stage.show()
        controls = QFrame(dialog)
        set_theme_style(controls, """
            QFrame { background: $panel; }
            QPushButton, QComboBox { background: $button; color: $text;
                border: 1px solid $border; border-radius: 5px; }
            QPushButton:hover { background: $hover; }
        """)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(6, 3, 6, 3)
        controls_layout.setSpacing(5)
        layout.insertWidget(0, controls)
        close = self._icon_button("back", tr("Tam ekrandan çık · Esc"), size=36)
        controls_layout.addWidget(close)
        close.clicked.connect(dialog.reject)
        close.show()
        close.raise_()
        self._fullscreen_close = close
        for text, tooltip, action in (
            ("▣", "Boya", lambda: self._select_tool("fill")),
            ("×", "Boş işaretle", lambda: self._select_tool("empty")),
            ("↔", "Taşı · Boşluk + sürükle", lambda: self._select_tool("pan")),
            ("↶", "Geri al", self.board.undo),
            ("−", "Uzaklaştır", lambda: self.board.zoom(.8)),
            ("+", "Yakınlaştır", lambda: self.board.zoom(1.25)),
            ("⊞", "Ekrana sığdır", self.board.fit_to_screen),
            ("⌕", "Okunabilir yakınlaştırma", self.board.readable_zoom),
        ):
            button = QPushButton(text, controls)
            button.setFixedSize(36, 36)
            button.setToolTip(tr(tooltip))
            button.setAccessibleName(tr(tooltip))
            button.clicked.connect(lambda checked=False, handler=action: (handler(), self.board.setFocus()))
            controls_layout.addWidget(button)
        if self.session.puzzle.is_colored:
            palette = QComboBox(controls)
            for index, color in enumerate(self.session.puzzle.palette, 1):
                swatch = QPixmap(20, 20)
                swatch.fill(QColor(color))
                palette.addItem(QIcon(swatch), str(index), index)
            palette.setCurrentIndex(self.board.color_id - 1)
            palette.currentIndexChanged.connect(lambda index: (
                self._select_color(self.color_picker.findData(index + 1))
            ))
            controls_layout.addWidget(palette)
        controls_layout.addStretch(1)
        controls.setToolTip(tr("Fare tekerleği: yakınlaştır · Boşluk + sürükle: taşı · Sağ tık: X"))
        self._fullscreen_controls = controls
        shortcut = QShortcut(QKeySequence("F11"), dialog)
        shortcut.activated.connect(dialog.reject)
        for sequence, handler in (("Ctrl+Z", self.board.undo),
                                  ("Ctrl+Y", self.board.redo),
                                  ("Ctrl+Shift+Z", self.board.redo),
                                  ("R", self.board.readable_zoom),
                                  ("B", lambda: self._select_tool("fill")),
                                  ("X", lambda: self._select_tool("empty")),
                                  ("F", self.board.fit_to_screen)):
            shortcut = QShortcut(QKeySequence(sequence), dialog)
            shortcut.activated.connect(handler)
        dialog.finished.connect(self._restore_board)
        dialog.showFullScreen()
        layout.activate()
        self.board_stage.layout_board()
        self.board.setFocus()

    def exit_board_fullscreen(self) -> None:
        if self.board_fullscreen_dialog is not None:
            self.board_fullscreen_dialog.reject()

    def _restore_board(self, _result=0) -> None:
        dialog = self.board_fullscreen_dialog
        if dialog is None:
            return
        self.board_fullscreen_dialog = None
        self.board.finish_active_stroke()
        self._fullscreen_close.hide()
        self._fullscreen_close.deleteLater()
        dialog.layout().removeWidget(self.board_stage)
        self.board_stage.expanded = False
        self.board.camera.max_cell_size = self._normal_max_cell_size
        self.board.fullscreen_clues = False
        self.board.pin_clues = self._normal_pin_clues
        self.board_drag_handle.show()
        self.layout().addWidget(self.board_stage, 1)
        self.board_stage.show()
        self.layout().activate()
        self.board_stage.layout_board()
        self.board.setFocus()
        dialog.deleteLater()

    def _set_assist(self, key: str, enabled: bool) -> None:
        self.board.finish_active_stroke()
        if key == "auto_x":
            self.session.set_auto_x_completed_lines(enabled)
        elif key == "clue_x":
            self.session.auto_x_crossed_lines = enabled
        elif key == "auto_clues":
            self.board.auto_cross_clues = enabled
        elif key == "errors":
            self.board.show_errors = enabled
        self.settings.setValue(f"assist/{key}", enabled)
        self.board.refresh_session()

    def _set_axis_lock(self, enabled: bool) -> None:
        self.board.finish_active_stroke()
        self.board.axis_lock = enabled
        self.settings.setValue("controls/axis_lock", enabled)

    def _set_board_view(self, key: str, value) -> None:
        options = {
            "pin_clues": self.board.pin_clues,
            "expanded_clues": self.board.expanded_clues,
            "clue_font_size": self.board.clue_font_size,
        }
        options[key] = value
        self.board.configure_view(**options)
        self.settings.setValue(f"view/{key}", value)
        if key == "clue_font_size":
            self.board.readable_zoom()

    def set_language(self, code: str) -> None:
        from pixel_nonograms.i18n import set_language, translate_widgets

        self.settings.setValue("language", code)
        set_language(code)
        translate_widgets(self)
        self.language_changed.emit(code)

    def _tool_separator(self) -> QFrame:
        line = QFrame()
        line.setFixedSize(1, 28)
        set_theme_style(line, "background: $border; border: none;")
        return line

    def save_now(self) -> bool:
        if self.save_manager is None:
            return True
        try:
            saved = self.save_manager.save(self.session)
        except Exception as exc:
            self.save_status_label.setText(tr(f"Kayıt hatası: {exc}"))
            self.save_status_label.show()
            return False
        if saved:
            self.save_status_label.clear()
            self.save_status_label.hide()
        return True

    def save_before_exit(self) -> bool:
        self.board.finish_active_stroke()
        return self.save_now()

    def return_to_library(self) -> None:
        if self.save_before_exit():
            self._autosave_timer.stop()
            self.back_requested.emit()

    def closeEvent(self, event) -> None:
        if not self.save_before_exit():
            event.ignore()
            return
        self._autosave_timer.stop()
        super().closeEvent(event)

    def _on_session_changed(self) -> None:
        if self._active_hint_plan is not None and not self._active_hint_plan.matches(
            self.session.cells
        ):
            self._active_hint_plan = None
            self._hint_level = 0
            self.board.set_hint_highlight()
            if (
                self.inventory is not None
                and self.inventory_toolbar.selected_item is HelperItemId.LOGIC_HINT
            ):
                self.inventory_toolbar.show_result(
                    "Tahta değişti; bu ipucu zinciri kapandı. Önceki eşya harcaması geri alınmaz.",
                    consumed=False,
                )
        completed = self.session.completed
        if completed and not self._last_completion:
            database = self.save_manager.database if self.save_manager is not None else None
            claimed_before = (
                database.reward_claimed(self.session.puzzle.id) if database is not None else False
            )
            completed_before = database is not None and self.session.puzzle.id in database.completion_history()
            milestones_before = database.milestone_ids() if database is not None else frozenset()
            saved = self.save_now()
            if saved and self.inventory is not None:
                self._refresh_inventory()
            reward_claimed = (
                database.reward_claimed(self.session.puzzle.id) if database is not None else False
            )
            self._show_completion(
                saved and database is not None, not claimed_before and reward_claimed,
                database.milestone_ids() - milestones_before if saved and database else frozenset(),
                new_star=bool(saved and database and not completed_before),
            )
        self._last_completion = completed

    def _show_completion(
        self, saved: bool, new_reward: bool, new_milestones=frozenset(), *, new_star=False
    ) -> None:
        if self.completion_dialog is not None:
            self.completion_dialog.close()
        dialog = QDialog(self)
        dialog.setWindowTitle(tr("Bulmaca tamamlandı"))
        dialog.setObjectName("completion_dialog")
        dialog.setModal(True)
        dialog.setMinimumWidth(360)
        set_theme_style(
            dialog,
            """
            QDialog { background: $panel; color: $text; }
            QLabel { color: $text; background: transparent; }
            QPushButton { background: $accent; color: $on_accent; border: 1px solid $accent;
                border-radius: 7px; padding: 9px 16px; }
            QPushButton:hover { background: $accent; }
        """,
        )
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(12)
        heading = QLabel(tr("★  Bulmaca tamamlandı!"))
        set_theme_style(heading, "font-size: 23px; font-weight: 700; color: $accent;")
        layout.addWidget(heading)
        self.completion_preview = PuzzlePreview(self.session.puzzle, dialog, revealed=True)
        self.completion_preview.setFixedSize(240, 240)
        layout.addWidget(self.completion_preview, 0, Qt.AlignmentFlag.AlignHCenter)
        title = QLabel(tr(self.session.puzzle.title))
        set_theme_style(title, "font-size: 17px; font-weight: 600;")
        layout.addWidget(title)
        reward = self.session.puzzle.reward_item_id
        if reward is None:
            reward_text = "Bu bulmacanın eşya ödülü bulunmuyor."
        elif not saved:
            reward_text = "Ödül kaydedilemedi. Kaydı tekrar deneyin."
        elif new_reward:
            reward_text = f"Kazandığın ödül: 1 × {ITEM_NAMES[reward]}"
        else:
            reward_text = f"{ITEM_NAMES[reward]} ödülü daha önce alındı."
        self.completion_reward_label = QLabel(tr(reward_text))
        self.completion_reward_label.setWordWrap(True)
        set_theme_style(
            self.completion_reward_label,
            "background: $panel; border: 1px solid $border; border-radius: 8px;padding: 13px; color: $accent; font-weight: 600;",
        )
        layout.addWidget(self.completion_reward_label)
        self.completion_progression_label = QLabel()
        self.completion_progression_label.setWordWrap(True)
        if saved and self.save_manager is not None:
            text = ("+1 yıldız · İlk tamamlama!\n" if new_star else "")
            text += progression_summary(self.save_manager.database)
            badges = [m.badge for m in MISSIONS if m.id in new_milestones]
            if badges:
                text += "\nYeni rozet: " + ", ".join(badges)
                text += "\nGörev ödülü: " + "; ".join(
                    mission_reward_text(m.id) for m in MISSIONS if m.id in new_milestones
                )
            self.completion_progression_label.setText(tr(text))
        else:
            self.completion_progression_label.setText(tr("Görev ilerlemesi kaydedilemedi."))
        layout.addWidget(self.completion_progression_label)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        actions.addStretch(1)
        if self._show_back_button:
            back = self._icon_button("back", tr("Kütüphaneye dön"))
            back.clicked.connect(dialog.accept)
            back.clicked.connect(self.return_to_library)
            actions.addWidget(back)
        self.next_button = QPushButton(tr("Sonraki bulmaca"))
        self.next_button.setVisible(self.has_next_puzzle)
        self.next_button.clicked.connect(self._request_next)
        actions.addWidget(self.next_button)
        close = QPushButton(tr("Tahtada kal"))
        close.clicked.connect(dialog.accept)
        actions.addWidget(close)
        self.completion_dialog = dialog
        apply_theme(dialog, theme_for(self).name)
        dialog.open()
        self.reveal_animation = None
        if not self.settings.value("appearance/reduce_motion", False, type=bool):
            effect = QGraphicsOpacityEffect(self.completion_preview)
            self.completion_preview.setGraphicsEffect(effect)
            self.reveal_animation = QPropertyAnimation(effect, b"opacity", dialog)
            self.reveal_animation.setDuration(450)
            self.reveal_animation.setStartValue(0.0)
            self.reveal_animation.setEndValue(1.0)
            dialog.finished.connect(self.reveal_animation.stop)
            self.reveal_animation.start()

    def _request_next(self) -> None:
        if self.session.completed and self.save_before_exit():
            self.next_requested.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        paint_wallpaper(painter, self)
        painter.end()

    def _refresh_inventory(self) -> None:
        if self.inventory is None:
            return
        self.inventory_toolbar.set_counts(self.inventory.counts())

    def _use_inventory_item(self, item_id, axis, line_index, *, origin=None) -> None:
        if self.inventory is None:
            return
        self.board.finish_active_stroke()
        if item_id in AREA_SIZES and origin is None:
            self.board.line_helper = False
            self.board.area_helper = item_id
            self.board.setFocus()
            self.board.update()
            return
        if item_id is HelperItemId.ROW_SCANNER and axis is None:
            self.board.area_helper = None
            self.board.line_helper = True
            self.board.setFocus()
            self.board.update()
            return
        self.board.area_helper = None
        self.board.line_helper = False
        database = self.inventory.database
        claimed_before = database.reward_claimed(self.session.puzzle.id)
        completed_before = self.session.puzzle.id in database.completion_history()
        milestones_before = database.milestone_ids()
        try:
            result = self.inventory.use(
                item_id,
                self.session,
                axis=axis,
                line_index=line_index,
                origin=origin,
            )
        except Exception as exc:
            self.inventory_toolbar.show_result(f"Yardım kullanılamadı: {exc}", consumed=False)
            return
        if result is not None and result.hint_plan is not None:
            self._active_hint_plan = result.hint_plan
            self._show_hint_step(1)
        else:
            self.inventory_toolbar.show_result(
                result.message
                if result is not None
                else "Yararlı sonuç bulunamadı; öğe harcanmadı.",
                consumed=result is not None,
            )
        self._refresh_inventory()
        if result is not None:
            if self.session.completed and not self._last_completion:
                # The helper transaction has already saved completion and its rewards.
                self._last_completion = True
                self._show_completion(
                    True, not claimed_before and database.reward_claimed(self.session.puzzle.id),
                    database.milestone_ids() - milestones_before,
                    new_star=not completed_before,
                )
            self.board.corrected_cell = result.corrected_cell
            self.board.refresh_session()
            self._refresh_status()
            self._on_session_changed()

    def _apply_area_helper(self, item_id, origin) -> None:
        self._use_inventory_item(item_id, None, None, origin=origin)

    def _apply_line_helper(self, axis, line_index) -> None:
        self._use_inventory_item(HelperItemId.ROW_SCANNER, axis, line_index)

    def _inventory_selection_changed(self, item_id) -> None:
        self.board.area_helper = None
        self.board.line_helper = False
        if item_id is HelperItemId.LOGIC_HINT and self._active_hint_plan is not None:
            if self._active_hint_plan.matches(self.session.cells):
                self._show_hint_step(self._hint_level)
                return
        self.board.set_hint_highlight()

    def _show_hint_step(self, level: int) -> None:
        plan = self._active_hint_plan
        if plan is None:
            return
        self._hint_level = level
        step = plan.step(level)
        self.inventory_toolbar.show_hint_step(step.message, level)
        move = plan.move
        row = move.line_index if move.axis == "row" else move.y if move.axis == "cross" else None
        column = (
            move.line_index if move.axis == "column" else move.x if move.axis == "cross" else None
        )
        self.board.set_hint_highlight(
            row=row,
            column=column,
            cell=(move.x, move.y) if level == 3 else None,
        )

    def _advance_hint(self) -> None:
        if self._active_hint_plan is None or self._hint_level not in (1, 2):
            return
        if not self._active_hint_plan.matches(self.session.cells):
            self._active_hint_plan = None
            self._hint_level = 0
            self.board.set_hint_highlight()
            self.inventory_toolbar.show_result(
                "Tahta değişti; ipucu zinciri kapandı.", consumed=False
            )
            return
        self._show_hint_step(self._hint_level + 1)

    def _icon_button(self, icon: str, title: str, *, size: int = 40) -> QPushButton:
        button = QPushButton()
        button.setProperty("theme_icon", icon)
        button.setIcon(tool_icon(icon, theme_for(self)))
        button.setIconSize(QSize(23, 23))
        button.setFixedSize(size, size)
        button.setToolTip(tr(title))
        button.setAccessibleName(tr(title))
        return button

    def _tool_button(self, layout: QHBoxLayout, icon: str, title: str, callback) -> QPushButton:
        button = self._icon_button(icon, tr(title))
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _open_hints_menu(self) -> None:
        self.board.finish_active_stroke()
        self._refresh_inventory()
        button = self.hints_button
        self.inventory_toolbar.menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def _select_clear_marker(self) -> None:
        self.marker_menu.close()
        button = self.tool_buttons["note"]
        button.setProperty("theme_icon", "clear")
        button.setIcon(tool_icon("clear", theme_for(self)))
        button.setText("")
        button.setToolTip(tr("İşareti sil"))
        button.setChecked(True)
        self.board.set_tool("clear")
        self.board.setFocus()

    def _open_marker_menu(self) -> None:
        self._select_tool("note")
        button = self.tool_buttons["note"]
        self.marker_menu.ensurePolished()
        from PySide6.QtCore import QPoint
        position = button.mapToGlobal(QPoint(0, button.height()))
        self.marker_menu.popup(position)
        self.marker_buttons[self.board.note_symbol].setFocus()

    def _select_marker(self, symbol: str) -> None:
        self.board.finish_active_stroke()
        self.board.note_symbol = symbol
        self.marker_menu.close()
        button = self.tool_buttons["note"]
        button.setProperty("theme_icon", None)
        button.setIcon(QIcon())
        button.setText(tr(symbol or "•"))
        button.setToolTip(tr(f"Geçici işaretçiler · {symbol or 'Nokta'}"))
        self._select_tool("note")

    def _select_tool(self, tool: str) -> None:
        self.tool_buttons[tool].setChecked(True)
        self.board.set_tool(tool)
        self.board.setFocus()

    def _select_color(self, index: int) -> None:
        color = self.color_picker.itemData(index)
        if color is not None:
            self.board.set_color(color)
            if color in self.color_buttons:
                self.color_buttons[color].setChecked(True)
            self._select_tool("fill")
        self.board.setFocus()

    def _refresh_status(self) -> None:
        session = self.session
        display_title = (
            session.puzzle.title
        )
        self.title_label.setText(tr(display_title))
        self.setWindowTitle(tr(f"Nonogram · {display_title}"))
        self.assumption_banner.setVisible(session.assumption_active)
        self.status_label.setText(
            tr("Deneme modu"
            if session.assumption_active
            else "Tamamlandı"
            if session.completed
            else "")
        )
        self.undo_button.setEnabled(session.can_undo)
        self.redo_button.setEnabled(session.can_redo)
        self.assumption_start_button.setVisible(not session.assumption_active)
        self.assumption_start_button.setEnabled(not session.completed)
        self.assumption_accept_button.setVisible(session.assumption_active)
        self.assumption_cancel_button.setVisible(session.assumption_active)
        if self.inventory is not None:
            self.inventory_toolbar.set_available(
                not session.completed and not session.assumption_active
            )
