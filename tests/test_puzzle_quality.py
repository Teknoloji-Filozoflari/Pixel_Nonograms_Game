"""Quality analysis must distinguish stalled logic from uniqueness."""
import pytest

from pixel_nonograms.core import Difficulty, EditorDraft
from pixel_nonograms.services.puzzle_quality import assess_quality, quality_text


def puzzle(grid, colored=False):
    draft = EditorDraft(len(grid[0]), len(grid))
    if colored:
        draft.add_color('#FF0000')
    for y, row in enumerate(grid):
        for x, value in enumerate(row):
            draft.set_cell(x, y, value)
    return draft.to_puzzle(title='Quality', author='Test')


def test_logical_completion_and_techniques():
    report = assess_quality(puzzle([[1, 1, 1], [0, 1, 0]]))
    assert report.status == 'solved'
    assert report.resolved == report.total == 6
    assert sum(count for _, count in report.techniques) == 6
    assert report.difficulty in (Difficulty.EASY, Difficulty.MEDIUM)


def test_ambiguous_board_stalls_without_difficulty_claim():
    report = assess_quality(puzzle([[1, 0], [0, 1]]))
    assert report.status == 'stalled'
    assert report.difficulty is None
    assert 'kanıtlanmadı' in quality_text(report)


def test_touching_colors_and_large_board_deadline():
    report = assess_quality(puzzle([[1, 2]], colored=True))
    assert report.status == 'solved'
    limited = assess_quality(puzzle([[1] * 50] * 50), timeout_seconds=1e-9)
    assert limited.status == 'limit'
    assert limited.difficulty is None
    assert limited.resolved < limited.total
    assert report.teaching_key < limited.teaching_key


def test_noise_is_advisory_and_never_changes_artwork():
    candidate = puzzle([[int((x+y) % 2 == 0) for x in range(5)] for y in range(5)])
    original = candidate.solution
    report = assess_quality(candidate)
    assert any('gürültü' in text for text in report.warnings)
    assert candidate.solution == original


@pytest.mark.parametrize('limit', [0, -1, float('inf'), float('nan')])
def test_invalid_analysis_budget(limit):
    with pytest.raises(ValueError):
        assess_quality(puzzle([[1]]), timeout_seconds=limit)


def test_teaching_lessons_are_logically_solvable_in_rule_order():
    from pixel_nonograms.ui.tutorial import LESSONS

    assert len(LESSONS) == 4
    for lesson in LESSONS:
        report = assess_quality(puzzle([lesson.solution], colored=len(lesson.palette) > 1))
        assert report.status == 'solved'
        assert report.difficulty in (Difficulty.EASY, Difficulty.MEDIUM)
