"""Shared coral and teal themes for the Pixel game family."""

from dataclasses import dataclass
from string import Template

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, QPen
from PySide6.QtWidgets import QWidget

from pixel_nonograms.core import CellMark, CellState, Puzzle
from pixel_nonograms.i18n import tr


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    colors: dict[str, str]


BOARD_COLORS = {
    "board": "#FFFFFF", "clue": "#EDF1F2", "ink": "#29343B",
    "grid": "#D5DDE0", "grid_major": "#8999A1", "cross": "#73838B",
    "note": "#FFFFFF",
}

THEMES = {
    "night": Theme("night", "Karanlık", {
        **BOARD_COLORS,
        "paper": "#23272E", "panel": "#2D333B", "text": "#E6E6E6",
        "muted": "#AEB9C4", "accent": "#F3946F", "primary": "#F06C3B",
        "primary_hover": "#FF8658", "on_primary": "#171D25",
        "border": "#48505B", "button": "#343B45", "hover": "#414B58",
        "selected": "#315B51", "selected_text": "#DCFFF0", "teal": "#8BC9B5",
        "well": "#1C2229", "disabled": "#2B3038", "disabled_text": "#87929F",
        "on_accent": "#171D25", "danger": "#FF98A5", "hint": "#E7BD78",
    }),
}

CONTROL_STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 13px; }
QMainWindow, QStackedWidget, QDialog { background: $paper; color: $text; }
QLabel { background: transparent; color: $text; }
QPushButton, QToolButton { background: $button; color: $text;
    border: 1px solid $border; border-radius: 7px; padding: 8px 12px; }
QPushButton:hover, QToolButton:hover { background: $hover; }
QPushButton:focus, QToolButton:focus, QComboBox:focus, QLineEdit:focus {
    border: 1px solid $accent; }
QPushButton:disabled, QToolButton:disabled { background: $disabled; color: $disabled_text; }
QLineEdit, QComboBox, QSpinBox { background: $well; color: $text;
    border: 1px solid $border; border-radius: 6px; padding: 6px; }
QComboBox QAbstractItemView { background: $panel; color: $text;
    selection-background-color: $selected; selection-color: $selected_text; }
QToolTip { background: $panel; color: $text; border: 1px solid $border; padding: 6px; }
"""


def theme_for(widget: QWidget) -> Theme:
    current = widget
    while current is not None:
        name = current.property("theme_name")
        if name in THEMES:
            return THEMES[name]
        current = current.parentWidget()
    return THEMES["night"]


def theme_color(widget: QWidget, role: str) -> QColor:
    return QColor(theme_for(widget).colors[role])


def contrasting_ink(background: QColor) -> QColor:
    """Choose black or white text by relative luminance, including midtone colors."""
    channels = (background.redF(), background.greenF(), background.blueF())
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
    luminance = sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    return QColor("#000000" if luminance > 0.179 else "#FFFFFF")


def set_theme_style(widget: QWidget, template: str) -> None:
    widget._theme_style = template
    widget.setStyleSheet(Template(template).substitute(theme_for(widget).colors))


def apply_theme(root: QWidget, name: str) -> None:
    if name not in THEMES:
        name = "night"
    root.setProperty("theme_name", name)
    palette = root.palette()
    for role, key in (
        (QPalette.ColorRole.Window, "paper"),
        (QPalette.ColorRole.WindowText, "text"),
        (QPalette.ColorRole.Base, "button"),
        (QPalette.ColorRole.Text, "text"),
        (QPalette.ColorRole.Button, "button"),
        (QPalette.ColorRole.ButtonText, "text"),
        (QPalette.ColorRole.Highlight, "accent"),
        (QPalette.ColorRole.HighlightedText, "on_accent"),
    ):
        palette.setColor(role, QColor(THEMES[name].colors[key]))
    root.setPalette(palette)
    widgets = [root, *root.findChildren(QWidget)]
    for widget in widgets:
        if widget.property("theme_name") is not None:
            widget.setProperty("theme_name", name)
    for widget in widgets:
        widget.setPalette(palette)
        template = getattr(widget, "_theme_style", None)
        if template is not None:
            set_theme_style(widget, template)
        icon_name = widget.property("theme_icon")
        if icon_name:
            from .tool_icons import tool_icon

            widget.setIcon(tool_icon(icon_name, theme_for(widget)))
        refresh = getattr(widget, "refresh_theme", None)
        if refresh is not None:
            refresh()
        QWidget.update(widget)


# Backwards-compatible night palette for callers that use a standalone preview.
PAPER = QColor(THEMES["night"].colors["paper"])
INK = QColor(THEMES["night"].colors["ink"])
CLUE = QColor(THEMES["night"].colors["clue"])
GOLD = QColor(THEMES["night"].colors["accent"])
BOARD = QColor(THEMES["night"].colors["board"])
TEXT = QColor(THEMES["night"].colors["text"])


def paint_wallpaper(painter: QPainter, widget: QWidget) -> None:
    painter.fillRect(widget.rect(), theme_color(widget, "paper"))


class PuzzlePreview(QWidget):
    """Show player marks by default; expose the answer only after completion."""

    def __init__(
        self,
        puzzle: Puzzle,
        parent: QWidget | None = None,
        *,
        revealed: bool = False,
        cells: tuple[tuple[CellMark, ...], ...] | None = None,
    ) -> None:
        super().__init__(parent)
        self.puzzle = puzzle
        self.hidden = not revealed and cells is None
        self.setAccessibleName(
            tr("Tamamlanan resim"
            if revealed
            else "Gizli resim"
            if self.hidden
            else "Kaydedilmiş hamleler")
        )
        self.setMinimumSize(88, 88)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        pixels = ()
        if revealed:
            pixels = puzzle.solution
        elif cells is not None:
            pixels = tuple(
                tuple(mark.color_id if mark.state is CellState.FILLED else 0 for mark in row)
                for row in cells
            )
        self._pixels = pixels
        self.refresh_theme()

    def refresh_theme(self) -> None:
        puzzle = self.puzzle
        self.image = QImage(puzzle.width, puzzle.height, QImage.Format.Format_RGB32)
        self.image.fill(theme_color(self, "board"))
        for y, row in enumerate(self._pixels):
            for x, color_id in enumerate(row):
                if color_id:
                    color = (
                        QColor(puzzle.palette[color_id - 1])
                        if puzzle.is_colored
                        else theme_color(self, "ink")
                    )
                    self.image.setPixelColor(x, y, color)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(theme_color(self, "well" if self.hidden else "board"))
        painter.setPen(QPen(theme_color(self, "border"), 1.5))
        outer = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(outer, 7, 7)
        side = min(outer.width(), outer.height()) - 12
        target = QRectF(
            outer.center().x() - side / 2,
            outer.center().y() - side / 2,
            side,
            side,
        )
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        if self.hidden:
            painter.setPen(QPen(theme_color(self, "border"), 0.6))
            for index in range(1, 5):
                step = side * index / 5
                painter.drawLine(
                    target.left() + step, target.top(), target.left() + step, target.bottom()
                )
                painter.drawLine(
                    target.left(), target.top() + step, target.right(), target.top() + step
                )
            font = painter.font()
            font.setPixelSize(int(side * 0.5))
            painter.setFont(font)
            painter.setPen(theme_color(self, "accent"))
            painter.drawText(target, Qt.AlignmentFlag.AlignCenter, tr("?"))
        else:
            painter.drawImage(target, self.image)
        painter.end()
