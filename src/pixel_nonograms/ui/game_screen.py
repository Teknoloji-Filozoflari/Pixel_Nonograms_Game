"""Playable board and compact tool strip."""

from PySide6.QtCore import QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pixel_nonograms.core import GameSession, HelperItemId
from pixel_nonograms.persistence import SaveManager
from pixel_nonograms.rendering import BoardWidget
from pixel_nonograms.services import ITEM_NAMES, InventoryService
from pixel_nonograms.solver import HintPlan

from .floating_board import BoardDragHandle, FloatingBoardStage
from .inventory_toolbar import InventoryToolbar
from .theme import paint_wallpaper
from .tool_icons import tool_icon


class GameScreen(QWidget):
    back_requested = Signal()

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
        self._show_back_button = show_back_button
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
        session.set_auto_x_completed_lines(False)
        self.setObjectName("game_screen")
        self.setWindowTitle(f"Nonogram · {session.puzzle.title}")
        self.resize(1000, 780)
        self.setStyleSheet("""
            QLabel { background: transparent; color: #E8E7DF; font-size: 13px; }
            QPushButton, QComboBox { background: #2D3740; color: #E8E7DF;
                border: 1px solid #66717A; border-radius: 7px;
                padding: 7px 10px; min-height: 20px; }
            QPushButton:hover { background: #3D4A54; }
            QPushButton:checked { background: #765F3F; border-color: #D3A65C; }
            QPushButton:disabled { color: #818A8B; background: #293139; }
            QMenu { background: #29333B; color: #E8E7DF; border: 1px solid #7B817D; }
            QMenu::item:selected { background: #765F3F; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 12, 20, 12)
        root.setSpacing(8)

        header = QHBoxLayout()
        self.back_button = QPushButton("‹  Kütüphane")
        self.back_button.clicked.connect(self.return_to_library)
        self.back_button.setVisible(show_back_button)
        header.addWidget(self.back_button)
        title = QLabel(session.puzzle.title)
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #F3E7CD;")
        header.addWidget(title)
        header.addStretch(1)
        self.status_label = QLabel()
        header.addWidget(self.status_label)
        self.save_status_label = QLabel()
        self.save_status_label.setStyleSheet("color: #FF999A;")
        self.save_status_label.hide()
        header.addWidget(self.save_status_label)
        settings_button = self._icon_button("menu", "Ayarlar", size=48)
        settings_menu = QMenu(settings_button)
        help_action = settings_menu.addAction("Nasıl oynanır?")
        help_action.triggered.connect(
            lambda: QMessageBox.information(
                self,
                "Oyun kontrolleri",
                "Dolu kareye aynı renkle tekrar tıklayarak boyayı kaldır. "
                "İpucu sayısına tıklayarak çizik at veya kaldır; kaldırınca o çizgideki X'ler silinir. "
                "Bir satır veya sütunun tüm sayılarını çizdiğinde kalan boş kareler X olur. "
                "Sağ tık X koyar. Üst şeridi sürükleyerek çerçeveyi taşı; "
                "orta tuş veya taşıma aracıyla yakınlaştırılmış ızgarayı kaydır.",
            )
        )
        settings_button.setMenu(settings_menu)
        root.addLayout(header)

        self.board_stage = FloatingBoardStage()
        self.board_shell = QFrame(self.board_stage)
        self.board_shell.setObjectName("game_board_shell")
        self.board_shell.setStyleSheet("""
            QFrame#game_board_shell { background: #29323A;
                border: 2px solid #A98855; border-radius: 6px; }
        """)
        shell_layout = QVBoxLayout(self.board_shell)
        shell_layout.setContentsMargins(7, 7, 7, 7)
        shell_layout.setSpacing(4)
        self.board_drag_handle = BoardDragHandle()
        shell_layout.addWidget(self.board_drag_handle)
        self.board = BoardWidget(session)
        shell_layout.addWidget(self.board)
        self.board_stage.attach(self.board_shell, self.board)
        self.board_drag_handle.dragged.connect(self.board_stage.drag_by)
        root.addWidget(self.board_stage, 1)
        self.board.session_changed.connect(self._refresh_status)
        self.board.session_changed.connect(self._on_session_changed)
        self.clue_focus_label = QLabel("Aktif hücrenin satır ve sütun ipuçları burada görünür.")
        self.clue_focus_label.setStyleSheet(
            "color: #D2D7D2; background: #27313A; border: 1px solid #58666D;"
            "border-radius: 5px; padding: 5px 9px; font-size: 12px;"
        )
        self.clue_focus_label.setWordWrap(True)
        root.addWidget(self.clue_focus_label)
        self.board.active_clues_changed.connect(self.clue_focus_label.setText)

        tools = QHBoxLayout()
        tools.setSpacing(6)
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.tool_buttons = {}
        for key, caption in (
            ("fill", "Doldur"), ("empty", "X işareti"),
            ("clear", "İşareti sil"), ("pan", "Tahtayı taşı"),
        ):
            button = self._icon_button(key, caption)
            button.setCheckable(True)
            button.setChecked(key == "fill")
            button.clicked.connect(lambda checked=False, tool=key: self._select_tool(tool))
            group.addButton(button)
            tools.addWidget(button)
            self.tool_buttons[key] = button

        self.color_picker = QComboBox()
        for index, _color in enumerate(session.puzzle.palette, 1):
            self.color_picker.addItem(f"● {index}", index)
        self.color_picker.currentIndexChanged.connect(self._select_color)
        self.color_picker.setToolTip("Doldurma rengi")
        self.color_picker.setAccessibleName("Doldurma rengi")
        if len(session.puzzle.palette) == 1:
            self.color_picker.hide()
        tools.addWidget(self.color_picker)
        tools.addSpacing(10)

        self.undo_button = self._tool_button(tools, "undo", "Geri al", self.board.undo)
        self.redo_button = self._tool_button(tools, "redo", "İleri al", self.board.redo)
        tools.addStretch(1)
        self._tool_button(tools, "zoom_out", "Uzaklaştır", lambda: self.board.zoom(1 / 1.2))
        self._tool_button(tools, "zoom_in", "Yakınlaştır", lambda: self.board.zoom(1.2))
        self._tool_button(tools, "fit", "Ekrana sığdır", self.board.fit_to_screen)
        self.assumption_start_button = self._tool_button(
            tools, "trial", "Deneme modunu başlat", self.board.begin_assumption
        )
        self.assumption_accept_button = self._tool_button(
            tools, "accept", "Denemeyi kabul et", self.board.accept_assumption
        )
        self.assumption_cancel_button = self._tool_button(
            tools, "cancel", "Denemeyi iptal et", self.board.cancel_assumption
        )
        tools.addWidget(settings_button)

        if self.inventory is not None:
            self.inventory_toolbar = InventoryToolbar(session.puzzle)
            self.inventory_toolbar.use_requested.connect(self._use_inventory_item)
            self.inventory_toolbar.next_hint_requested.connect(self._advance_hint)
            self.inventory_toolbar.selection_changed.connect(self._inventory_selection_changed)
            root.addWidget(self.inventory_toolbar)
            self._refresh_inventory()

        toolbar = QFrame()
        toolbar.setObjectName("game_toolbar")
        toolbar.setStyleSheet("""
            QFrame#game_toolbar { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 #37434C, stop:1 #252E36); border: 2px solid #8C734E;
                border-radius: 9px; }
            QFrame#game_toolbar QPushButton { background: #303B43;
                border: 1px solid #7A827D; border-radius: 6px; padding: 0; }
            QFrame#game_toolbar QPushButton:hover { background: #46545D; }
            QFrame#game_toolbar QPushButton:checked { background: #69563B;
                border: 2px solid #D3A65C; }
            QFrame#game_toolbar QPushButton:disabled { background: #293139;
                border-color: #485258; }
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 7, 8, 7)
        toolbar_layout.addLayout(tools)
        root.addWidget(toolbar)

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

    def save_now(self) -> bool:
        if self.save_manager is None:
            return True
        try:
            saved = self.save_manager.save(self.session)
        except Exception as exc:
            self.save_status_label.setText(f"Kayıt hatası: {exc}")
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
                    "Tahta değişti; bu ipucu zinciri kapandı.", consumed=False
                )
        completed = self.session.completed
        if completed and not self._last_completion:
            database = self.save_manager.database if self.save_manager is not None else None
            claimed_before = (
                database.reward_claimed(self.session.puzzle.id) if database is not None else False
            )
            saved = self.save_now()
            if saved and self.inventory is not None:
                self._refresh_inventory()
            reward_claimed = (
                database.reward_claimed(self.session.puzzle.id) if database is not None else False
            )
            self._show_completion(
                saved and database is not None, not claimed_before and reward_claimed
            )
        self._last_completion = completed

    def _show_completion(self, saved: bool, new_reward: bool) -> None:
        if self.completion_dialog is not None:
            self.completion_dialog.close()
        dialog = QDialog(self)
        dialog.setWindowTitle("Bulmaca tamamlandı")
        dialog.setObjectName("completion_dialog")
        dialog.setModal(True)
        dialog.setMinimumWidth(360)
        dialog.setStyleSheet("""
            QDialog { background: #222B33; color: #E9E7DE; }
            QLabel { color: #E9E7DE; background: transparent; }
            QPushButton { background: #9F7842; color: #161D23; border: 1px solid #D3A65C;
                border-radius: 7px; padding: 9px 16px; }
            QPushButton:hover { background: #D3A65C; }
        """)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(12)
        heading = QLabel("★  Bulmaca tamamlandı!")
        heading.setStyleSheet("font-size: 23px; font-weight: 700; color: #E8BD78;")
        layout.addWidget(heading)
        title = QLabel(self.session.puzzle.title)
        title.setStyleSheet("font-size: 17px; font-weight: 600;")
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
        self.completion_reward_label = QLabel(reward_text)
        self.completion_reward_label.setWordWrap(True)
        self.completion_reward_label.setStyleSheet(
            "background: #343B40; border: 1px solid #A98855; border-radius: 8px;"
            "padding: 13px; color: #F0D4A1; font-weight: 600;"
        )
        layout.addWidget(self.completion_reward_label)
        actions = QHBoxLayout()
        layout.addLayout(actions)
        actions.addStretch(1)
        if self._show_back_button:
            back = QPushButton("Kütüphaneye dön")
            back.clicked.connect(dialog.accept)
            back.clicked.connect(self.return_to_library)
            actions.addWidget(back)
        close = QPushButton("Tahtada kal")
        close.clicked.connect(dialog.accept)
        actions.addWidget(close)
        self.completion_dialog = dialog
        dialog.open()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        paint_wallpaper(painter, self)
        painter.end()

    def _refresh_inventory(self) -> None:
        if self.inventory is None:
            return
        self.inventory_toolbar.set_counts(self.inventory.counts())

    def _use_inventory_item(self, item_id, axis, line_index) -> None:
        if self.inventory is None:
            return
        try:
            result = self.inventory.use(
                item_id,
                self.session,
                axis=axis,
                line_index=line_index,
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

    def _inventory_selection_changed(self, item_id) -> None:
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

    def _icon_button(self, icon: str, title: str, *, size: int = 46) -> QPushButton:
        button = QPushButton()
        button.setIcon(tool_icon(icon))
        button.setIconSize(QSize(27, 27))
        button.setFixedSize(size, size)
        button.setToolTip(title)
        button.setAccessibleName(title)
        return button

    def _tool_button(
        self, layout: QHBoxLayout, icon: str, title: str, callback
    ) -> QPushButton:
        button = self._icon_button(icon, title)
        button.clicked.connect(callback)
        layout.addWidget(button)
        return button

    def _select_tool(self, tool: str) -> None:
        self.board.set_tool(tool)
        self.board.setFocus()

    def _select_color(self, index: int) -> None:
        color = self.color_picker.itemData(index)
        if color is not None:
            self.board.set_color(color)
        self.board.setFocus()

    def _refresh_status(self) -> None:
        session = self.session
        self.status_label.setText(
            "Deneme modu" if session.assumption_active else "Tamamlandı" if session.completed else ""
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
