"""Permanent, optional milestones; IDs and starter membership are stable."""
from dataclasses import dataclass

STARTER_IDS = frozenset({'ilk-adim-01', 'demo-elmas-01', 'kalp-10-01'})


@dataclass(frozen=True, slots=True)
class Mission:
    id: str
    title: str
    target: int
    kind: str
    badge: str


MISSIONS = (
    Mission('first', 'İlk bulmacanı tamamla', 1, 'total', 'İlk Adım'),
    Mission('three', '3 farklı bulmaca tamamla', 3, 'total', 'Desen Kaşifi'),
    Mission('color', 'Bir renkli bulmaca tamamla', 1, 'color', 'Renk Ustası'),
    Mission('starter', 'Başlangıç üçlüsünü tamamla', 3, 'starter', 'Koleksiyoncu'),
    Mission('ten', '10 farklı bulmaca tamamla', 10, 'total', 'Mozaik Ustası'),
)


def mission_count(mission: Mission, completions: dict[str, bool]) -> int:
    if mission.kind == 'color':
        count = sum(completions.values())
    elif mission.kind == 'starter':
        count = len(STARTER_IDS.intersection(completions))
    else:
        count = len(completions)
    return min(count, mission.target)


# Each completed mission grants its pack once, in addition to the profile badge.
MISSION_REWARDS = {
    "first": (("logic_hint", 2),),
    "three": (("logic_hint", 3), ("error_check", 1)),
    "color": (("analysis_lens", 2), ("row_scanner", 2)),
    "starter": (("logic_hint", 4), ("analysis_lens", 2)),
    "ten": (("logic_hint", 5), ("row_scanner", 2), ("analysis_lens", 2), ("second_look", 1)),
}
