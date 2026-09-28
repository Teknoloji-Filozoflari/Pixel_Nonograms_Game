"""Optional permanent missions and selectable profile badges."""

import sqlite3

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from pixel_nonograms.core import HelperItemId
from pixel_nonograms.core.progression import MISSION_REWARDS, MISSIONS, mission_count
from pixel_nonograms.i18n import tr
from pixel_nonograms.services.inventory import ITEM_NAMES

from .theme import apply_theme, set_theme_style, theme_for


def mission_reward_text(mission_id):
    return ", ".join(f"{count} × {ITEM_NAMES[HelperItemId(item)]}"
                     for item, count in MISSION_REWARDS[mission_id])


def progression_summary(database) -> str:
    history = database.completion_history()
    selected = database.selected_badge()
    badge = next((m.badge for m in MISSIONS if m.id == selected), 'Rozet seçilmedi')
    upcoming = next((m for m in MISSIONS if mission_count(m, history) < m.target), None)
    text = f'★ {len(history)} yıldız · {badge}'
    if upcoming:
        text += f'\nSıradaki: {upcoming.title} ({mission_count(upcoming, history)}/{upcoming.target})'
        text += f' → {mission_reward_text(upcoming.id)} + {upcoming.badge} rozeti'
    else:
        text += '\nTüm görevler tamamlandı!'
    return text


class ProgressionDialog(QDialog):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.database = database
        self.setWindowTitle(tr('Görevler ve rozetler'))
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        intro = QLabel(tr('Süre sınırı yok. Her farklı bulmaca bir yıldız kazandırır.\nYardım kullanmak görevleri engellemez.'))
        intro.setWordWrap(True)
        layout.addWidget(intro)
        history = database.completion_history()
        unlocked = database.milestone_ids()
        self.bars = {}
        for mission in MISSIONS:
            label = QLabel(tr(f'{mission.title} → {mission.badge} rozeti'
                           + (' · Açıldı' if mission.id in unlocked else '')))
            label.setWordWrap(True)
            layout.addWidget(label)
            reward_label = QLabel(tr(mission_reward_text(mission.id)))
            reward_label.setWordWrap(True)
            layout.addWidget(reward_label)
            bar = QProgressBar()
            bar.setRange(0, mission.target)
            bar.setValue(mission_count(mission, history))
            bar.setFormat('%v / %m')
            layout.addWidget(bar)
            self.bars[mission.id] = bar
        starter = QLabel(tr('Başlangıç üçlüsü: İlk Adım, Elmas ve Kalp.\nRozetler yalnızca profil görünümünü değiştirir.'))
        starter.setWordWrap(True)
        layout.addWidget(starter)
        layout.addWidget(QLabel(tr('Profil rozeti')))
        self.badge_picker = QComboBox()
        self.badge_picker.addItem(tr('Rozet kullanma'), None)
        for mission in MISSIONS:
            if mission.id in unlocked:
                self.badge_picker.addItem(tr(mission.badge), mission.id)
        self.badge_picker.setCurrentIndex(max(0, self.badge_picker.findData(database.selected_badge())))
        self.badge_picker.currentIndexChanged.connect(self._select_badge)
        layout.addWidget(self.badge_picker)
        self.status = QLabel()
        layout.addWidget(self.status)
        close = QPushButton(tr('Kapat'))
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        set_theme_style(self, """
            QDialog { background: $paper; color: $text; }
            QLabel { color: $text; }
            QProgressBar { border: 1px solid $border; border-radius: 4px;
                background: $panel; color: $text; text-align: center; min-height: 20px; }
            QProgressBar::chunk { background: $selected; border-radius: 3px; }
        """)
        apply_theme(self, theme_for(parent).name if parent else 'paper')

    def _select_badge(self):
        try:
            self.database.select_badge(self.badge_picker.currentData())
        except (sqlite3.Error, ValueError) as exc:
            self.status.setText(tr(f'Rozet kaydedilemedi: {exc}'))
        else:
            self.status.setText(tr('Profil rozeti kaydedildi.'))
