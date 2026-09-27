"""A movable puzzle frame over the fixed game wallpaper."""

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import QLabel, QWidget

from pixel_nonograms.rendering import BoardWidget


class BoardDragHandle(QLabel):
    dragged = Signal(QPoint)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("⠿  Tahtayı sürükle", parent)
        self.setFixedHeight(24)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip("Bulmaca çerçevesini taşımak için sürükle")
        self.setStyleSheet(
            "background: #3B4650; color: #F0D6A6; border: 1px solid #A98855;"
            "border-radius: 4px; font-size: 11px; font-weight: 700;"
        )
        self._last_global: QPoint | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_global = event.globalPosition().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._last_global is not None:
            position = event.globalPosition().toPoint()
            self.dragged.emit(position - self._last_global)
            self._last_global = position
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._last_global = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class FloatingBoardStage(QWidget):
    """Size the frame to the visible grid and keep it within the wallpaper area."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.shell: QWidget | None = None
        self.board: BoardWidget | None = None
        self._user_moved = False

    def attach(self, shell: QWidget, board: BoardWidget) -> None:
        shell.setParent(self)
        self.shell = shell
        self.board = board
        self.layout_board()

    def layout_board(self) -> None:
        if self.shell is None or self.board is None or self.width() < 1 or self.height() < 1:
            return
        left, top = self.board._clue_bands()
        max_width = max(1, self.width() - 12)
        max_height = max(1, self.height() - 12)
        frame_extra_height = 42  # Border, padding, gap, and drag handle.
        cell_size = min(
            80,
            max(2, (max_width - left - 26) / self.board.display_width),
            max(2, (max_height - top - 12 - frame_extra_height) / self.board.display_height),
        )
        board_width = max(120, round(left + self.board.display_width * cell_size + 12))
        board_height = max(120, round(top + self.board.display_height * cell_size + 12))
        old_position = self.shell.pos()
        self.shell.setFixedSize(board_width + 14, board_height + frame_extra_height)
        if self._user_moved:
            self._place(old_position)
        else:
            self._place(QPoint((self.width() - self.shell.width()) // 2,
                               (self.height() - self.shell.height()) // 2))
        self.board.fit_to_screen()

    def drag_by(self, delta: QPoint) -> None:
        if self.shell is None:
            return
        self._user_moved = True
        self._place(self.shell.pos() + delta)

    def _place(self, position: QPoint) -> None:
        if self.shell is None:
            return
        # A little overflow leaves room to move a frame that nearly fills the stage.
        overflow = 72 if self._user_moved else 0
        x = min(max(-overflow, position.x()),
                max(0, self.width() - self.shell.width()) + overflow)
        y = min(max(0, position.y()),
                max(0, self.height() - self.shell.height()) + overflow)
        self.shell.move(x, y)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.layout_board()
