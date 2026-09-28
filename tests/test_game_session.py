from datetime import datetime, timezone

import pytest

from pixel_nonograms.core import (
    CellChangeCommand,
    CellMark,
    CellState,
    Difficulty,
    GameSession,
    MultiCellChangeCommand,
    Puzzle,
)


def puzzle_for(solution, palette=("#112233",)):
    return Puzzle(
        id="session-test",
        title="Oturum",
        author="Test",
        description="",
        width=len(solution[0]),
        height=len(solution),
        difficulty=Difficulty.EASY,
        tags=(),
        palette=palette,
        solution=solution,
    )


def test_initial_state_and_single_cell_actions():
    session = GameSession(puzzle_for(((1, 0),)))
    assert session.cells == ((CellMark(), CellMark()),)
    assert session.completion_percentage == 0
    assert not session.completed
    assert session.move_count == 0
    assert session.started_at.tzinfo is not None
    assert session.last_played_at == session.started_at

    assert session.mark_empty(1, 0)
    assert session.cell_at(1, 0) == CellMark(CellState.EMPTY)
    assert session.clear_cell(1, 0)
    assert session.cell_at(1, 0) == CellMark()
    assert session.fill_cell(0, 0)
    assert session.cell_at(0, 0) == CellMark(CellState.FILLED, 1)
    assert session.completed
    assert session.completion_percentage == 100
    assert session.move_count == 3
    assert session.last_played_at >= session.started_at


def test_no_op_does_not_count_or_clear_redo():
    session = GameSession(puzzle_for(((1, 0),)))
    assert not session.clear_cell(0, 0)
    session.fill_cell(0, 0)
    session.undo()
    assert session.can_redo
    assert not session.clear_cell(0, 0)
    assert session.can_redo
    assert session.move_count == 1


def test_undo_redo_and_completion_transitions():
    session = GameSession(puzzle_for(((1, 1),)))
    assert not session.undo()
    assert not session.redo()
    session.fill_cell(0, 0)
    assert session.completion_percentage == 50
    session.fill_cell(1, 0)
    assert session.completed
    assert session.undo()
    assert not session.completed
    assert session.completion_percentage == 50
    assert session.redo()
    assert session.completed
    assert (session.move_count, session.undo_count, session.redo_count) == (2, 1, 1)


def test_redo_is_cleared_by_new_move():
    session = GameSession(puzzle_for(((1, 0),)))
    session.fill_cell(0, 0)
    session.undo()
    session.mark_empty(1, 0)
    assert not session.can_redo
    assert not session.redo()


def test_external_command_uses_same_history_and_validates_atomically():
    session = GameSession(puzzle_for(((1, 1),)))
    first = CellChangeCommand(0, 0, CellMark(), CellMark(CellState.FILLED, 1))
    session.execute(first)
    assert session.can_undo
    invalid = MultiCellChangeCommand(
        (
            CellChangeCommand(1, 0, CellMark(), CellMark(CellState.FILLED, 1)),
            CellChangeCommand(0, 0, CellMark(), CellMark(CellState.EMPTY)),
        )
    )
    with pytest.raises(ValueError, match="eşleşmiyor"):
        session.execute(invalid)
    assert session.cells == ((CellMark(CellState.FILLED, 1), CellMark()),)
    assert session.move_count == 1


def test_drag_stroke_is_one_undo_and_revisit_keeps_original_before():
    session = GameSession(puzzle_for(((1, 1, 0),)))
    session.begin_stroke()
    session.fill_cell(0, 0)
    session.fill_cell(1, 0)
    session.mark_empty(2, 0)
    session.clear_cell(2, 0)
    session.mark_empty(2, 0)
    command = session.end_stroke()
    assert isinstance(command, MultiCellChangeCommand)
    assert len(command.changes) == 3
    assert session.move_count == 1
    assert session.completed
    session.undo()
    assert session.cells == ((CellMark(), CellMark(), CellMark()),)
    session.redo()
    assert session.completed


def test_empty_stroke_and_cancel_do_not_change_history():
    session = GameSession(puzzle_for(((1,),)))
    session.begin_stroke()
    session.fill_cell(0, 0)
    session.clear_cell(0, 0)
    assert session.end_stroke() is None
    assert session.move_count == 0
    session.begin_stroke()
    session.fill_cell(0, 0)
    session.cancel_stroke()
    assert session.cell_at(0, 0) == CellMark()
    assert not session.can_undo


def test_mistakes_and_hint_are_historical_counters():
    session = GameSession(puzzle_for(((1, 0),)))
    session.mark_empty(0, 0)
    session.fill_cell(1, 0)
    assert session.mistake_count == 2
    session.undo()
    session.undo()
    session.redo()
    assert session.mistake_count == 2
    session.record_hint()
    assert session.hint_count == 1


def test_color_ids_and_wrong_color_prevent_completion():
    session = GameSession(puzzle_for(((1, 2),), ("#112233", "#445566")))
    session.fill_cell(0, 0, 2)
    session.fill_cell(1, 0, 2)
    assert not session.completed
    assert session.completion_percentage == 50
    assert session.mistake_count == 1
    session.fill_cell(0, 0, 1)
    assert session.completed
    assert session.completion_percentage == 100


def test_all_empty_puzzle_is_complete_on_start():
    session = GameSession(puzzle_for(((0,),)))
    assert session.completed
    assert session.completion_percentage == 100
    assert session.elapsed_time == 0
    session.fill_cell(0, 0)
    assert not session.completed
    assert session.completion_percentage == 0


def test_wrong_extra_fill_prevents_completion_even_at_100_percent():
    session = GameSession(puzzle_for(((1, 0),)))
    session.fill_cell(0, 0)
    session.fill_cell(1, 0)
    assert session.completion_percentage == 100
    assert not session.completed
    session.mark_empty(1, 0)
    assert session.completed


@pytest.mark.parametrize("coordinate", [(-1, 0), (0, -1), (2, 0), (0, 1), (True, 0)])
def test_invalid_coordinates(coordinate):
    session = GameSession(puzzle_for(((1, 0),)))
    with pytest.raises(IndexError):
        session.fill_cell(*coordinate)
    assert session.move_count == 0


@pytest.mark.parametrize("color_id", [0, 2, -1, True, 1.0])
def test_invalid_colors(color_id):
    session = GameSession(puzzle_for(((1,),)))
    with pytest.raises(ValueError):
        session.fill_cell(0, 0, color_id)
    assert session.move_count == 0


def test_command_and_stroke_validation():
    with pytest.raises(ValueError):
        CellMark(CellState.EMPTY, 1)
    with pytest.raises(ValueError):
        CellMark(CellState.FILLED, 0)
    with pytest.raises(ValueError):
        CellChangeCommand(0, 0, CellMark(), CellMark())
    change = CellChangeCommand(0, 0, CellMark(), CellMark(CellState.FILLED, 1))
    with pytest.raises(ValueError):
        MultiCellChangeCommand((change, change))
    session = GameSession(puzzle_for(((1,),)))
    with pytest.raises(RuntimeError):
        session.end_stroke()
    session.begin_stroke()
    with pytest.raises(RuntimeError):
        session.begin_stroke()
    with pytest.raises(RuntimeError):
        session.undo()
    session.cancel_stroke()


def test_elapsed_time_pauses_and_freezes_on_completion(monkeypatch):
    ticks = iter((10.0, 15.0, 15.0, 20.0, 24.0, 24.0, 30.0, 36.0))
    monkeypatch.setattr("pixel_nonograms.core.game_session.monotonic", lambda: next(ticks))
    session = GameSession(puzzle_for(((1,),)))
    assert session.elapsed_time == 5
    session.pause()
    assert session.elapsed_time == 5
    session.resume()
    assert session.elapsed_time == 9
    session.fill_cell(0, 0)
    assert session.completed
    assert session.elapsed_time == 9
    session.undo()
    assert session.elapsed_time == 15


def test_started_at_is_utc():
    session = GameSession(puzzle_for(((1,),)))
    assert session.started_at.tzinfo == timezone.utc
    assert isinstance(session.last_played_at, datetime)


def test_auto_x_defaults_off_and_completed_row_is_one_undoable_move():
    puzzle = puzzle_for(((1, 0, 0), (0, 1, 1)))
    session = GameSession(puzzle)
    session.fill_cell(0, 0)
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    assert session.cell_at(2, 0).state is CellState.UNKNOWN

    assisted = GameSession(puzzle, auto_x_completed_lines=True)
    assisted.fill_cell(0, 0)
    assert [assisted.cell_at(x, 0).state for x in range(3)] == [
        CellState.FILLED,
        CellState.EMPTY,
        CellState.EMPTY,
    ]
    assert assisted.move_count == 1
    assert assisted.mistake_count == 0
    assisted.undo()
    assert all(mark.state is CellState.UNKNOWN for row in assisted.cells for mark in row)
    assisted.redo()
    assert assisted.cell_at(2, 0).state is CellState.EMPTY


def test_manual_clues_cross_remaining_cells_only_after_last_number_and_undo():
    session = GameSession(puzzle_for(((1, 0, 1, 0), (0, 1, 0, 0))))
    session.fill_cell(0, 0)
    assert session.toggle_clue("row", 0, 0)
    assert session.is_clue_crossed("row", 0, 0)
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    session.mark_empty(3, 0)
    assert session.toggle_clue("row", 0, 1)
    assert [session.cell_at(x, 0).state for x in range(4)] == [
        CellState.FILLED,
        CellState.EMPTY,
        CellState.EMPTY,
        CellState.EMPTY,
    ]
    assert session.undo()
    assert not session.is_clue_crossed("row", 0, 1)
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    assert session.redo()
    assert session.is_clue_crossed("row", 0, 1)
    assert session.cell_at(1, 0).state is CellState.EMPTY
    assert not session.toggle_clue("row", 0, 1)
    assert all(session.cell_at(x, 0).state is CellState.UNKNOWN for x in (1, 2))
    assert session.cell_at(3, 0).state is CellState.EMPTY
    assert session.undo()
    assert session.is_clue_crossed("row", 0, 1)
    assert all(session.cell_at(x, 0).state is CellState.EMPTY for x in (1, 2, 3))


def test_auto_x_completed_column_and_drag_share_history():
    session = GameSession(puzzle_for(((1, 0), (1, 1), (0, 1))), auto_x_completed_lines=True)
    session.begin_stroke()
    session.fill_cell(0, 0)
    session.fill_cell(0, 1)
    command = session.end_stroke()
    assert isinstance(command, MultiCellChangeCommand)
    assert session.cell_at(0, 2).state is CellState.EMPTY
    assert session.move_count == 1
    session.undo()
    assert all(session.cell_at(0, y).state is CellState.UNKNOWN for y in range(3))


def test_auto_x_waits_for_entire_line_not_just_first_clue():
    session = GameSession(puzzle_for(((1, 0, 1), (0, 1, 0))), auto_x_completed_lines=True)
    session.fill_cell(0, 0)
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    assert session.cell_at(2, 0).state is CellState.UNKNOWN


def test_enabling_auto_x_applies_existing_completed_lines_and_can_be_disabled():
    session = GameSession(puzzle_for(((1, 0, 0), (0, 1, 1))))
    session.fill_cell(0, 0)
    assert session.set_auto_x_completed_lines(True)
    assert session.cell_at(1, 0).state is CellState.EMPTY
    assert session.move_count == 2
    session.undo()
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    assert not session.set_auto_x_completed_lines(False)
    session.fill_cell(1, 1)
    assert session.cell_at(1, 0).state is CellState.UNKNOWN


def test_auto_x_skips_contradiction_and_respects_color():
    session = GameSession(
        puzzle_for(((1, 0, 2), (0, 2, 0)), ("#112233", "#445566")),
        auto_x_completed_lines=True,
    )
    session.fill_cell(0, 0, 2)
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    session.fill_cell(0, 0, 1)
    session.fill_cell(2, 0, 2)
    assert session.cell_at(1, 0).state is CellState.EMPTY


def test_auto_x_does_not_duplicate_a_manually_cleared_forced_empty_cell():
    session = GameSession(puzzle_for(((1, 0, 0), (0, 1, 1))), auto_x_completed_lines=True)
    session.fill_cell(0, 0)
    before = session.move_count
    assert not session.clear_cell(1, 0)
    assert session.cell_at(1, 0).state is CellState.EMPTY
    assert session.move_count == before
    session.undo()
    assert session.cell_at(0, 0).state is CellState.UNKNOWN


@pytest.mark.parametrize("enabled", [0, 1, None, "true"])
def test_auto_x_rejects_non_boolean_setting(enabled):
    puzzle = puzzle_for(((1,),))
    with pytest.raises(TypeError):
        GameSession(puzzle, auto_x_completed_lines=enabled)
    with pytest.raises(TypeError):
        GameSession(puzzle).set_auto_x_completed_lines(enabled)


def test_assumption_cancel_restores_board_and_normal_redo():
    session = GameSession(puzzle_for(((1, 1, 1),)))
    session.fill_cell(0, 0)
    session.fill_cell(1, 0)
    session.undo()
    baseline = session.cells
    counters = (session.move_count, session.undo_count, session.redo_count, session.mistake_count)
    session.begin_assumption()
    assert session.assumption_active
    assert not session.can_undo and not session.can_redo
    session.fill_cell(2, 0)
    assert session.is_assumption_cell(2, 0)
    assert session.assumption_move_count == 1
    assert not session.is_assumption_cell(0, 0)
    assert (
        session.move_count,
        session.undo_count,
        session.redo_count,
        session.mistake_count,
    ) == counters
    session.cancel_assumption()
    assert session.cells == baseline
    assert not session.assumption_active
    assert session.assumption_move_count == 0
    assert session.can_redo
    assert not session.is_assumption_cell(2, 0)
    session.redo()
    assert session.cell_at(1, 0).state is CellState.FILLED


def test_assumption_accept_commits_net_changes_as_one_undo_step():
    session = GameSession(puzzle_for(((1, 1, 1),)))
    session.fill_cell(0, 0)
    session.begin_assumption()
    session.begin_stroke()
    session.fill_cell(1, 0)
    session.fill_cell(2, 0)
    session.end_stroke()
    assert not session.completed
    assert session.completion_percentage == 100
    assert session.move_count == 1
    assert session.accept_assumption()
    assert session.completed
    assert session.move_count == 2
    assert not session.assumption_active
    session.undo()
    assert session.cells == ((CellMark(CellState.FILLED, 1), CellMark(), CellMark()),)
    session.redo()
    assert session.completed


def test_assumption_undo_redo_stay_inside_trial_and_no_net_accept_preserves_history():
    session = GameSession(puzzle_for(((1, 1, 1),)))
    session.fill_cell(0, 0)
    session.fill_cell(1, 0)
    session.undo()
    session.begin_assumption()
    session.fill_cell(2, 0)
    assert session.undo()
    assert not session.is_assumption_cell(2, 0)
    assert session.can_redo
    assert session.redo()
    assert session.is_assumption_cell(2, 0)
    assert session.undo()
    assert not session.accept_assumption()
    assert session.move_count == 2
    assert session.undo_count == 1
    assert session.redo_count == 0
    assert session.can_redo


def test_assumption_accept_counts_only_final_mistakes_and_clears_normal_redo():
    session = GameSession(puzzle_for(((1, 0, 1),)))
    session.fill_cell(0, 0)
    session.undo()
    session.begin_assumption()
    session.fill_cell(1, 0)  # Wrong hypothesis, then corrected before accepting.
    session.mark_empty(1, 0)
    session.fill_cell(0, 0)
    assert session.mistake_count == 0
    assert session.accept_assumption()
    assert session.mistake_count == 0
    assert not session.can_redo
    assert session.move_count == 2


def test_assumption_auto_x_changes_are_tentative():
    session = GameSession(puzzle_for(((1, 0, 0), (0, 1, 1))), auto_x_completed_lines=True)
    session.begin_assumption()
    session.fill_cell(0, 0)
    assert session.is_assumption_cell(1, 0)
    assert session.cell_at(1, 0).state is CellState.EMPTY
    session.cancel_assumption()
    assert all(mark.state is CellState.UNKNOWN for row in session.cells for mark in row)
    assert session.move_count == 0


def test_assumption_marks_color_change_against_starting_board():
    session = GameSession(puzzle_for(((1, 2),), ("#112233", "#445566")))
    session.fill_cell(0, 0, 1)
    session.begin_assumption()
    session.fill_cell(0, 0, 2)
    assert session.is_assumption_cell(0, 0)
    session.cancel_assumption()
    assert session.cell_at(0, 0) == CellMark(CellState.FILLED, 1)


def test_assumption_rejects_nested_and_invalid_transitions():
    session = GameSession(puzzle_for(((1, 1),)))
    with pytest.raises(RuntimeError, match="Etkin Deneme"):
        session.accept_assumption()
    with pytest.raises(RuntimeError, match="Etkin Deneme"):
        session.cancel_assumption()
    session.begin_assumption()
    with pytest.raises(RuntimeError, match="zaten açık"):
        session.begin_assumption()
    session.begin_stroke()
    with pytest.raises(RuntimeError, match="sürükleme"):
        session.cancel_assumption()
    session.cancel_stroke()
    session.cancel_assumption()
    session.fill_cell(0, 0)
    session.fill_cell(1, 0)
    with pytest.raises(RuntimeError, match="Tamamlanmış"):
        session.begin_assumption()


def test_manual_x_and_intersecting_sources_survive_clue_reopening():
    session = GameSession(puzzle_for(((1, 0, 0), (0, 1, 0), (0, 0, 1))))
    session.mark_empty(2, 0)
    session.toggle_clue("row", 0, 0)
    session.toggle_clue("column", 1, 0)
    assert session.cell_at(1, 0).auto_sources == 3
    session.toggle_clue("row", 0, 0)
    assert session.cell_at(1, 0).auto_sources == 2
    assert session.cell_at(2, 0) == CellMark(CellState.EMPTY)
    session.toggle_clue("column", 1, 0)
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    session.undo()
    assert session.cell_at(1, 0).auto_sources == 2
    session.undo()
    assert session.cell_at(1, 0).auto_sources == 3
    session.redo()
    assert session.cell_at(1, 0).auto_sources == 2


def test_manual_adoption_of_auto_x_and_disabled_clue_x():
    session = GameSession(puzzle_for(((1, 0), (0, 1))))
    session.toggle_clue("row", 0, 0)
    session.mark_empty(1, 0)
    session.toggle_clue("row", 0, 0)
    assert session.cell_at(1, 0) == CellMark(CellState.EMPTY)
    session.auto_x_crossed_lines = False
    session.toggle_clue("row", 1, 0)
    assert session.cell_at(0, 1) == CellMark()


def test_notes_do_not_affect_logic_and_trial_notes_are_temporary():
    from pixel_nonograms.core import analyze_board

    session = GameSession(puzzle_for(((1, 0), (0, 1))))
    before = analyze_board(session.puzzle, session.cells)
    session.mark_note(0, 0)
    assert session.cell_at(0, 0).state is CellState.UNKNOWN
    assert analyze_board(session.puzzle, session.cells) == before
    assert not session.completed and session.mistake_count == 0
    session.begin_assumption()
    session.mark_note(1, 0)
    assert not session.snapshot().cells[0][1].note
    session.cancel_assumption()
    assert session.cell_at(0, 0).note and not session.cell_at(1, 0).note
    session.begin_assumption()
    session.fill_cell(0, 0)
    session.accept_assumption()
    assert not session.cell_at(0, 0).note
    session.undo()
    assert session.cell_at(0, 0).note
    session.redo()
    assert session.cell_at(0, 0).state is CellState.FILLED
    assert not session.mark_note(0, 0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"note": 1},
        {"state": CellState.EMPTY, "note": True},
        {"auto_sources": 8},
        {"auto_sources": True},
        {"auto_sources": 1},
    ],
)
def test_invalid_note_and_source_metadata_rejected(kwargs):
    with pytest.raises(ValueError):
        CellMark(**kwargs)
