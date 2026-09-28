"""Replayable practice lessons isolated from puzzle progress and inventory."""

from dataclasses import dataclass

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from pixel_nonograms.core import CellState, Difficulty, GameSession, Puzzle
from pixel_nonograms.i18n import tr
from pixel_nonograms.rendering import BoardWidget
from pixel_nonograms.solver.hint_engine import create_hint_plan

from .theme import apply_theme, set_theme_style, theme_for


@dataclass(frozen=True)
class Lesson:
    title: str
    instruction: str
    solution: tuple[int, ...]
    palette: tuple[str, ...] = ("#252923",)


LESSONS = (
    Lesson(
        "Dolu blok",
        "5 sayısı, art arda beş dolu hücre demektir. Doldur aracını seç ve beş hücreyi sürükleyerek boya.",
        (1, 1, 1, 1, 1),
    ),
    Lesson(
        "Boş hücre de bir bilgidir",
        "1 1, iki ayrı blok demektir. İlk ve son hücreyi doldur; araya X koy. Aynı renkte iki blok arasında en az bir boş hücre gerekir.",
        (1, 0, 1),
    ),
    Lesson(
        "Aynı renk, ayrı bloklar",
        "Turuncu 2 2: iki turuncu hücre, bir X, iki turuncu hücre. Renkli bulmacada da aynı renkteki ayrı bloklar arasında boşluk gerekir.",
        (1, 1, 0, 1, 1),
        ("#CC7045", "#367F98"),
    ),
    Lesson(
        "Farklı renkler bitişebilir",
        "Turuncu 2 ve mavi 2 arasında boşluk gerekmez. İlk iki hücreyi turuncu, son iki hücreyi mavi boya. Rengi aşağıdaki seçiciden değiştir.",
        (1, 1, 2, 2),
        ("#CC7045", "#367F98"),
    ),
)


class TutorialDialog(QDialog):
    def __init__(self, parent, settings: QSettings) -> None:
        super().__init__(parent)
        self.settings = settings
        self.index = 0
        self.plan = None
        self.hint_level = 0
        self.board = None
        self.setWindowTitle(tr("Oynamayı öğren"))
        self.resize(680, 540)
        set_theme_style(
            self,
            """
            QDialog { background: $paper; color: $text; }
            QLabel { color: $text; background: transparent; }
            QPushButton, QComboBox { background: $button; color: $text; border: 1px solid $border;
                border-radius: 6px; padding: 7px; }
            QPushButton:checked { background: $selected; }
            QPushButton:disabled { color: $disabled_text; }
        """,
        )
        layout = QVBoxLayout(self)
        self.heading = QLabel()
        set_theme_style(self.heading, "font-size: 20px; font-weight: 700; color: $accent;")
        layout.addWidget(self.heading)
        self.instruction = QLabel()
        self.instruction.setWordWrap(True)
        layout.addWidget(self.instruction)
        note = QLabel(tr("Alıştırmalar ücretsizdir; envanter ve asıl bulmaca ilerlemen değişmez."))
        note.setWordWrap(True)
        set_theme_style(note, "color: $muted;")
        layout.addWidget(note)
        self.board_layout = QVBoxLayout()
        layout.addLayout(self.board_layout, 1)
        tools = QHBoxLayout()
        layout.addLayout(tools)
        group = QButtonGroup(self)
        self.tools = {}
        for key, label in (("fill", "Doldur"), ("empty", "X koy"), ("clear", "Sil")):
            button = QPushButton(tr(label))
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, value=key: self.board.set_tool(value))
            group.addButton(button)
            tools.addWidget(button)
            self.tools[key] = button
        self.colors = QComboBox()
        self.colors.setAccessibleName(tr("Alıştırma rengi"))
        self.colors.currentIndexChanged.connect(self._color_changed)
        tools.addWidget(self.colors)
        undo = QPushButton(tr("Geri al"))
        undo.clicked.connect(lambda: self.board.undo())
        tools.addWidget(undo)
        retry = QPushButton(tr("Baştan dene"))
        retry.clicked.connect(self.load_lesson)
        tools.addWidget(retry)
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        self.hint_text = QLabel()
        self.hint_text.setWordWrap(True)
        layout.addWidget(self.hint_text)
        navigation = QHBoxLayout()
        layout.addLayout(navigation)
        close = QPushButton(tr("Şimdilik kapat"))
        close.clicked.connect(self.reject)
        navigation.addWidget(close)
        self.previous = QPushButton(tr("Önceki"))
        self.previous.clicked.connect(self.go_back)
        navigation.addWidget(self.previous)
        self.hint_button = QPushButton(tr("Ücretsiz ipucu"))
        self.hint_button.clicked.connect(self.show_hint)
        navigation.addWidget(self.hint_button)
        self.next_button = QPushButton(tr("Sonraki"))
        self.next_button.clicked.connect(self.go_next)
        navigation.addWidget(self.next_button)
        self.load_lesson()
        apply_theme(self, theme_for(parent).name)

    def load_lesson(self) -> None:
        if self.board is not None:
            self.board.finish_active_stroke()
            self.board_layout.removeWidget(self.board)
            self.board.setParent(None)
            self.board.deleteLater()
        lesson = LESSONS[self.index]
        puzzle = Puzzle(
            id=f"practice-{self.index}",
            title=lesson.title,
            author="Pixel Nonograms",
            description="Alıştırma",
            width=len(lesson.solution),
            height=1,
            difficulty=Difficulty.EASY,
            tags=(),
            palette=lesson.palette,
            solution=(lesson.solution,),
        )
        session = GameSession(puzzle)
        session.auto_x_crossed_lines = False
        self.board = BoardWidget(session, self)
        self.board.show_errors = False
        self.board_layout.addWidget(self.board)
        self.board.session_changed.connect(self.check_answer)
        self.heading.setText(tr(f"{self.index + 1}/{len(LESSONS)} · {lesson.title}"))
        self.instruction.setText(tr(lesson.instruction))
        self.tools["fill"].setChecked(True)
        self.colors.blockSignals(True)
        self.colors.clear()
        for index in range(len(lesson.palette)):
            self.colors.addItem(tr("Turuncu" if index == 0 else "Mavi"), index + 1)
        self.colors.setVisible(len(lesson.palette) > 1)
        self.colors.blockSignals(False)
        self.previous.setEnabled(self.index > 0)
        self.next_button.setText(
            tr("Öğreticiyi bitir" if self.index == len(LESSONS) - 1 else "Sonraki")
        )
        self.plan = None
        self.hint_level = 0
        self.hint_text.clear()
        self.hint_button.setText(tr("Ücretsiz ipucu"))
        self.check_answer()

    def _color_changed(self, index: int) -> None:
        if self.board is not None and index >= 0:
            self.board.set_color(index + 1)
            self.board.set_tool("fill")
            self.tools["fill"].setChecked(True)

    def check_answer(self) -> None:
        cells = self.board.session.cells[0]
        answer = LESSONS[self.index].solution
        correct = all(
            (mark.state is CellState.FILLED and mark.color_id == target)
            if target
            else mark.state is CellState.EMPTY
            for mark, target in zip(cells, answer)
        )
        wrong = any(
            (mark.state is CellState.FILLED and mark.color_id != target)
            or (mark.state is CellState.EMPTY and target != 0)
            for mark, target in zip(cells, answer)
        )
        self.next_button.setEnabled(correct)
        self.feedback.setText(
            tr("Doğru! Sonraki adıma geçebilirsin."
            if correct
            else "Bazı işaretler kuralla uyuşmuyor. Geri al veya Sil ile düzelt."
            if wrong
            else "Sayıları izleyerek doldur; kesin boşları X ile işaretle.")
        )
        self.hint_button.setEnabled(not correct)
        if self.plan is not None and not self.plan.matches(self.board.session.cells):
            self.plan = None
            self.hint_level = 0
            self.hint_text.clear()
            self.hint_button.setText(tr("Ücretsiz ipucu"))
            self.board.set_hint_highlight()

    def show_hint(self) -> None:
        try:
            if self.plan is None:
                self.plan = create_hint_plan(self.board.session.puzzle, self.board.session.cells)
                self.hint_level = 0
            if self.plan is None:
                self.hint_text.setText(tr("Önce uyuşmayan işaretleri geri al veya silip tekrar dene."))
                return
            self.hint_level = min(3, self.hint_level + 1)
            step = self.plan.step(self.hint_level)
            self.hint_text.setText(tr(step.message + " · Ücretsiz alıştırma"))
            move = self.plan.move
            self.board.set_hint_highlight(
                row=move.y, column=move.x, cell=(move.x, move.y) if self.hint_level == 3 else None
            )
            self.hint_button.setText(
                tr({1: "Mantığı açıkla", 2: "Kesin hücreyi göster", 3: "İpucunu tekrar oku"}[
                    self.hint_level
                ])
            )
        except TimeoutError:
            self.hint_text.setText(tr("İpucu hesaplanamadı; tekrar deneyebilirsin."))

    def go_next(self) -> None:
        if not self.next_button.isEnabled():
            return
        if self.index == len(LESSONS) - 1:
            self.settings.setValue("tutorial/completed", True)
            self.accept()
        else:
            self.index += 1
            self.load_lesson()

    def go_back(self) -> None:
        if self.index:
            self.index -= 1
            self.load_lesson()


def open_tutorial(parent, settings: QSettings) -> TutorialDialog:
    dialog = TutorialDialog(parent, settings)
    parent.tutorial_dialog = dialog
    dialog.finished.connect(dialog.deleteLater)
    dialog.open()
    return dialog
