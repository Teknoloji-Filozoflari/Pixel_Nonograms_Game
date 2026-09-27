import os
from dataclasses import replace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, QPointF, QRectF, QSettings, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from pixel_nonograms.core import (
    CellState,
    Difficulty,
    GameSession,
    HelperItemId,
    LineStatus,
    Puzzle,
)
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.rendering import BoardWidget, Camera
from pixel_nonograms.services import InventoryService, built_in_puzzles
from pixel_nonograms.ui.game_screen import GameScreen


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def puzzle_for(solution, palette=("#112233",)):
    return Puzzle(
        id="ui-test",
        title="Tahta",
        author="Test",
        description="",
        width=len(solution[0]),
        height=len(solution),
        difficulty=Difficulty.EASY,
        tags=(),
        palette=palette,
        solution=solution,
    )


def board_for(app, solution, palette=("#112233",)):
    session = GameSession(puzzle_for(solution, palette))
    board = BoardWidget(session)
    board.resize(620, 520)
    board.show()
    app.processEvents()
    return board, session


def cell_point(board, x, y):
    origin = board.camera.cell_origin(x, y, board.grid_viewport())
    half = board.camera.cell_size / 2
    return QPoint(round(origin.x() + half), round(origin.y() + half))


def row_clue_point(board, y, offset=0):
    row_edge, _ = board._clue_edges(board.grid_viewport())
    width = board.grid_viewport().left()
    capacity = board._clue_capacity(width)
    slot = min(26.0, (width - 8) / capacity)
    return QPoint(round(row_edge - 8 - (offset + 0.5) * slot), cell_point(board, 0, y).y())


def column_clue_point(board, x, offset=0):
    _, column_edge = board._clue_edges(board.grid_viewport())
    height = board.grid_viewport().top()
    capacity = board._clue_capacity(height)
    slot = min(26.0, (height - 8) / capacity)
    return QPoint(cell_point(board, x, 0).x(), round(column_edge - 8 - (offset + 0.5) * slot))


def test_camera_transform_zoom_and_fit():
    camera = Camera()
    viewport = QRectF(60, 50, 500, 400)
    camera.fit(viewport, 10, 10)
    assert camera.visible_cells(viewport, 10, 10) == (0, 0, 10, 10)
    center = QPointF(300, 250)
    before = camera.screen_to_cell(center, viewport, 10, 10)
    camera.zoom_at(center, 1.5, viewport, 10, 10)
    assert camera.screen_to_cell(center, viewport, 10, 10) == before
    assert camera.screen_to_cell(QPointF(10, 10), viewport, 10, 10) is None
    x0, y0, x1, y1 = camera.visible_cells(viewport, 10, 10)
    assert x0 <= before[0] < x1 and y0 <= before[1] < y1
    camera.fit(viewport, 100, 100)
    assert camera.cell_size * 100 <= viewport.width()
    assert camera.cell_size * 100 <= viewport.height()


def test_single_canvas_click_right_click_clear_undo_redo(app):
    board, session = board_for(app, ((1, 0),))
    assert board.findChildren(QWidget) == []
    first, second = cell_point(board, 0, 0), cell_point(board, 1, 0)
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=first)
    QTest.mouseClick(board, Qt.MouseButton.RightButton, pos=second)
    assert session.cell_at(0, 0).state is CellState.FILLED
    assert session.cell_at(1, 0).state is CellState.EMPTY
    assert session.move_count == 2
    board.undo()
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    board.redo()
    assert session.cell_at(1, 0).state is CellState.EMPTY
    board.set_tool("clear")
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=first)
    assert session.cell_at(0, 0).state is CellState.UNKNOWN
    board.close()


def test_corner_overview_tracks_filled_cells_without_revealing_solution(app):
    board, session = board_for(app, ((1, 0), (0, 1)))
    rect = board._marked_overview_rect(board.grid_viewport())

    def overview_pixel(x, y):
        point = QPoint(round(rect.left() + (x + 0.5) * rect.width() / 2),
                       round(rect.top() + (y + 0.5) * rect.height() / 2))
        return board.grab().toImage().pixelColor(point)

    blank = overview_pixel(0, 0)
    assert overview_pixel(1, 1) == blank  # The answer is still hidden.
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 0, 0))
    assert session.cell_at(0, 0).state is CellState.FILLED
    assert overview_pixel(0, 0) != blank
    assert overview_pixel(1, 1) == blank
    board.undo()
    assert overview_pixel(0, 0) == blank
    board.redo()
    assert overview_pixel(0, 0) != blank
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 0, 0))
    assert overview_pixel(0, 0) == blank
    board.close()


def test_every_fifth_row_and_column_has_corner_number(app):
    solution = tuple(tuple(int(x == 0 and y == 0) for x in range(10)) for y in range(10))
    board, _session = board_for(app, solution)
    image = board.grab().toImage()

    def bright_pixels_in_lower_right(x, y):
        origin = board.camera.cell_origin(x, y, board.grid_viewport())
        size = board.camera.cell_size
        left = round(origin.x() + size - 18)
        top = round(origin.y() + size - 17)
        return sum(
            image.pixelColor(px, py).red() > 150
            for py in range(top, round(origin.y() + size - 3))
            for px in range(left, round(origin.x() + size - 3))
        )

    assert bright_pixels_in_lower_right(9, 4) > bright_pixels_in_lower_right(9, 3)
    assert bright_pixels_in_lower_right(4, 9) > bright_pixels_in_lower_right(3, 9)
    assert bright_pixels_in_lower_right(9, 9) > bright_pixels_in_lower_right(8, 9)
    board.close()


def test_nonmultiple_blank_tail_is_hidden_but_saved_marks_remain_visible(app):
    puzzles = {puzzle.title: puzzle for puzzle in built_in_puzzles()}
    tulip = puzzles["Lale"]
    board = BoardWidget(GameSession(tulip))
    assert (board.display_width, board.display_height) == (15, 17)
    board.close()
    sailboat = puzzles["Yelkenli"]
    board = BoardWidget(GameSession(sailboat))
    assert (board.display_width, board.display_height) == (27, 25)
    board.close()
    session = GameSession(tulip)
    session.mark_empty(16, 0)
    board = BoardWidget(session)
    assert (board.display_width, board.display_height) == (17, 17)
    board.close()


def test_board_frame_drags_over_fixed_wallpaper(app, tmp_path):
    settings = QSettings(str(tmp_path / "floating.ini"), QSettings.Format.IniFormat)
    screen = GameScreen(GameSession(puzzle_for(((0, 1, 0, 0, 0),) * 5)), settings=settings)
    screen.show()
    app.processEvents()
    original = screen.board_shell.pos()
    stage_position = screen.board_stage.pos()
    camera_pan = (screen.board.camera.pan_x, screen.board.camera.pan_y)
    handle = screen.board_drag_handle
    center = handle.rect().center()
    QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=center)
    QTest.mouseMove(handle, center + QPoint(60, 25))
    QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=center + QPoint(60, 25))
    assert screen.board_shell.pos() != original
    assert screen.board_shell.parent() is screen.board_stage
    assert screen.board_stage.pos() == stage_position
    assert (screen.board.camera.pan_x, screen.board.camera.pan_y) == camera_pan
    screen.close()
    expert = next(p for p in built_in_puzzles() if p.title == "Büyük Çiçek")
    screen = GameScreen(GameSession(expert), settings=settings)
    screen.show()
    app.processEvents()
    original_y = screen.board_shell.y()
    screen.board_stage.drag_by(QPoint(0, 30))
    assert screen.board_shell.y() == original_y + 30
    screen.close()


@pytest.mark.parametrize(
    "button,expected",
    [(Qt.MouseButton.LeftButton, CellState.FILLED), (Qt.MouseButton.RightButton, CellState.EMPTY)],
)
def test_drag_is_one_command(app, button, expected):
    board, session = board_for(app, ((1, 1, 1, 1, 1),))
    start, end = cell_point(board, 0, 0), cell_point(board, 4, 0)
    QTest.mousePress(board, button, pos=start)
    QTest.mouseMove(board, end)
    QTest.mouseRelease(board, button, pos=end)
    assert [session.cell_at(x, 0).state for x in range(5)] == [expected] * 5
    assert session.move_count == 1
    board.undo()
    assert all(session.cell_at(x, 0).state is CellState.UNKNOWN for x in range(5))
    board.close()


def test_zoom_pan_fit_and_hover(app):
    board, _session = board_for(app, ((1,) * 20,) * 20)
    center = board.grid_viewport().center()
    board.zoom(3.0, center)
    size = board.camera.cell_size
    before = board.camera.pan_x
    start = QPoint(round(center.x()), round(center.y()))
    end = QPoint(start.x() - 40, start.y())
    QTest.mousePress(board, Qt.MouseButton.MiddleButton, pos=start)
    QTest.mouseMove(board, end)
    QTest.mouseRelease(board, Qt.MouseButton.MiddleButton, pos=end)
    assert board.camera.pan_x < before
    QTest.mouseMove(board, start)
    assert board.hover == board.camera.screen_to_cell(QPointF(start), board.grid_viewport(), 20, 20)
    before_space_pan = board.camera.pan_x
    QTest.keyPress(board, Qt.Key.Key_Space)
    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(board, end)
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=end)
    QTest.keyRelease(board, Qt.Key.Key_Space)
    assert board.camera.pan_x < before_space_pan
    before_wheel = board.camera.cell_size
    wheel = QWheelEvent(
        QPointF(start),
        QPointF(start),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(board, wheel)
    assert board.camera.cell_size > before_wheel
    board.fit_to_screen()
    assert board.camera.cell_size < size
    board.close()


def test_tools_and_colored_selection(app, tmp_path):
    session = GameSession(puzzle_for(((1, 2),), ("#112233", "#445566")))
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    screen = GameScreen(session, settings=settings)
    screen.show()
    app.processEvents()
    assert screen.color_picker.isVisible()
    screen.color_picker.setCurrentIndex(1)
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 1, 0))
    assert session.cell_at(1, 0).color_id == 2
    assert screen.undo_button.isEnabled()
    screen.undo_button.click()
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    screen.board.setFocus()
    QTest.keyClick(screen.board, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
    assert session.cell_at(1, 0).color_id == 2
    QTest.mouseMove(screen.board, cell_point(screen.board, 0, 0))
    assert "Satır 1:" in screen.clue_focus_label.text()
    assert "Sütun 1:" in screen.clue_focus_label.text()
    screen.close()


def test_legacy_automatic_settings_do_not_cross_clues_or_cells(app, tmp_path):
    settings_path = tmp_path / "settings.ini"
    settings = QSettings(str(settings_path), QSettings.Format.IniFormat)
    settings.setValue("auto_x_completed_lines", True)
    settings.setValue("auto_cross_completed_clues", True)
    session = GameSession(puzzle_for(((1, 0, 0), (0, 1, 1))))
    screen = GameScreen(session, settings=settings)
    screen.show()
    app.processEvents()
    assert not session.auto_x_completed_lines
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 0, 0))
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    assert not session.is_clue_crossed("row", 0, 0)
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton,
                     pos=row_clue_point(screen.board, 0))
    assert session.is_clue_crossed("row", 0, 0)
    assert session.cell_at(1, 0).state is CellState.EMPTY
    assert session.move_count == 2
    screen.board.undo()
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    assert not session.is_clue_crossed("row", 0, 0)
    screen.close()


def test_clue_paint_changes_only_after_manual_click(app, monkeypatch):
    board, session = board_for(app, ((1, 0), (0, 1)))
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 0, 0))
    assert board._analysis.rows[0].completed_clues == (True,)
    rendered = []
    monkeypatch.setattr(
        board, "_draw_clue", lambda painter, rect, clue, done: rendered.append(done)
    )
    board.grab()
    assert rendered and not any(rendered)
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=row_clue_point(board, 0))
    rendered.clear()
    board.grab()
    assert True in rendered
    assert board._analysis.rows[0].completed_clues == (True,)
    assert session.cell_at(0, 0).state is CellState.FILLED
    board.close()


def test_fill_click_toggles_same_cell_and_overfill_only_counts_marks(app):
    board, session = board_for(app, ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    wrong = cell_point(board, 1, 0)
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=wrong)
    assert session.cell_at(1, 0).state is CellState.FILLED
    assert board._overfilled_lines() == ((), ())
    untouched = cell_point(board, 2, 1)
    before_grid = board.grab().toImage().pixelColor(untouched)
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 0, 0))
    assert board._overfilled_lines()[0] == (0,)
    warning = board._warning_row_rect(0, board.grid_viewport())
    row_edge, _ = board._clue_edges(board.grid_viewport())
    assert row_edge < warning.right() <= board.grid_viewport().right()
    border = board.grab().toImage().pixelColor(
        QPoint(round(warning.left()), round(warning.center().y()))
    )
    assert border.red() > border.green()
    assert board.grab().toImage().pixelColor(untouched) == before_grid
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=wrong)
    assert session.cell_at(1, 0).state is CellState.UNKNOWN
    assert board._overfilled_lines() == ((), ())
    board.undo()
    assert session.cell_at(1, 0).state is CellState.FILLED
    board.close()


def test_column_clue_click_crosses_remaining_unknown_cells(app):
    board, session = board_for(app, ((1, 0), (1, 1), (0, 0)))
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 0, 0))
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 0, 1))
    assert session.cell_at(0, 2).state is CellState.UNKNOWN
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=column_clue_point(board, 0))
    assert session.is_clue_crossed("column", 0, 0)
    assert session.cell_at(0, 2).state is CellState.EMPTY
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=column_clue_point(board, 0))
    assert not session.is_clue_crossed("column", 0, 0)
    assert session.cell_at(0, 2).state is CellState.UNKNOWN
    board.undo()
    assert session.cell_at(0, 2).state is CellState.EMPTY
    board.close()


def test_overfilled_column_frame_stays_inside_clue_band(app):
    board, session = board_for(app, ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 1, 0))
    untouched = cell_point(board, 2, 2)
    before_grid = board.grab().toImage().pixelColor(untouched)
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 1, 1))
    assert board._overfilled_lines() == ((), (1,))
    warning = board._warning_column_rect(1, board.grid_viewport())
    _, column_edge = board._clue_edges(board.grid_viewport())
    assert column_edge < warning.bottom() <= board.grid_viewport().bottom()
    border = board.grab().toImage().pixelColor(
        QPoint(round(warning.center().x()), round(warning.top()))
    )
    assert border.red() > border.green()
    assert board.grab().toImage().pixelColor(untouched) == before_grid
    board.close()


def test_assumption_buttons_and_tentative_cell_visuals(app, tmp_path):
    session = GameSession(puzzle_for(((1, 1, 1),)))
    settings = QSettings(str(tmp_path / "trial.ini"), QSettings.Format.IniFormat)
    screen = GameScreen(session, settings=settings)
    screen.show()
    app.processEvents()
    board = screen.board
    assert screen.assumption_start_button.isVisible()
    assert not screen.assumption_accept_button.isVisible()

    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 0, 0))
    baseline = session.cells
    screen.assumption_start_button.click()
    assert session.assumption_active
    assert not screen.assumption_start_button.isVisible()
    assert screen.assumption_accept_button.isVisible()
    assert "Deneme" in screen.status_label.text()
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 1, 0))
    assert session.is_assumption_cell(1, 0)
    assert screen.status_label.text() == "Deneme modu"
    origin = board.camera.cell_origin(1, 0, board.grid_viewport())
    sample = QPoint(round(origin.x() + 4), round(origin.y() + 4))
    trial_color = board.grab().toImage().pixelColor(sample)

    screen.assumption_cancel_button.click()
    assert session.cells == baseline
    assert not session.assumption_active
    assert screen.assumption_start_button.isVisible()
    screen.assumption_start_button.click()
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 1, 0))
    screen.assumption_accept_button.click()
    assert session.cell_at(1, 0).state is CellState.FILLED
    assert trial_color != board.grab().toImage().pixelColor(sample)
    screen.undo_button.click()
    assert session.cells == baseline
    screen.close()


def test_periodic_and_close_autosave(app, tmp_path):
    puzzle = puzzle_for(((1, 1),))
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    session = GameSession(puzzle)
    screen = GameScreen(session, settings=settings, save_manager=manager)
    screen.show()
    app.processEvents()
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 0, 0))
    assert manager.load(puzzle) is None
    screen._autosave_timer.timeout.emit()
    assert manager.load(puzzle).cell_at(0, 0).state is CellState.FILLED
    screen.board.set_tool("empty")
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 1, 0))
    assert screen.close()
    assert manager.load(puzzle).cell_at(1, 0).state is CellState.EMPTY
    database.close()


def test_completion_and_app_exit_save(app, tmp_path):
    puzzle = puzzle_for(((1, 1),))
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    screen = GameScreen(GameSession(puzzle), settings=settings, save_manager=manager)
    screen.show()
    app.processEvents()
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 0, 0))
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 1, 0))
    assert manager.load(puzzle).completed
    screen.board.undo()
    assert screen.save_before_exit()
    assert not manager.load(puzzle).completed
    screen.close()
    database.close()


def test_completion_dialog_reports_first_reward_once(app, tmp_path):
    puzzle = replace(puzzle_for(((1,),)), reward_item_id=HelperItemId.LOGIC_HINT)
    database = Database(tmp_path / "reward.sqlite3")
    manager = SaveManager(database)
    inventory = InventoryService(database, manager)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    screen = GameScreen(GameSession(puzzle), settings=settings, save_manager=manager,
                        inventory=inventory)
    screen.show()
    app.processEvents()

    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 0, 0))
    app.processEvents()
    assert screen.completion_dialog is not None
    assert screen.completion_dialog.isVisible()
    assert "Bulmaca tamamlandı" in screen.completion_dialog.windowTitle()
    assert "Kazandığın ödül: 1 × Mantık İpucu" in screen.completion_reward_label.text()
    assert all(
        "saniye" not in label.text() and "hamle" not in label.text()
        for label in screen.completion_dialog.findChildren(QLabel)
    )
    assert database.item_count(HelperItemId.LOGIC_HINT) == 1

    screen.completion_dialog.accept()
    screen.board.undo()
    screen.board.redo()
    app.processEvents()
    assert "daha önce alındı" in screen.completion_reward_label.text()
    assert database.item_count(HelperItemId.LOGIC_HINT) == 1
    screen.completion_dialog.accept()
    screen.close()
    database.close()


def test_icon_toolbar_pan_does_not_mark_cells(app, tmp_path):
    session = GameSession(puzzle_for(((1, 1),)))
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    screen = GameScreen(session, settings=settings)
    screen.show()
    app.processEvents()
    assert screen.status_label.text() == ""
    assert all(button.text() == "" for button in screen.tool_buttons.values())
    screen.tool_buttons["pan"].click()
    assert screen.board.tool == "pan"
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 0, 0))
    assert session.cell_at(0, 0).state is CellState.UNKNOWN
    screen.tool_buttons["fill"].click()
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 0, 0))
    assert session.cell_at(0, 0).state is CellState.FILLED
    assert screen.status_label.text() == ""
    screen.close()


def test_failed_close_save_keeps_window_open_and_shows_error(app, tmp_path, monkeypatch):
    puzzle = puzzle_for(((1,),))
    database = Database(tmp_path / "progress.sqlite3")
    manager = SaveManager(database)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    screen = GameScreen(GameSession(puzzle), settings=settings, save_manager=manager)
    screen.show()
    app.processEvents()
    original_save = manager.save

    def fail_save(session):
        raise OSError("disk full")

    monkeypatch.setattr(manager, "save", fail_save)
    assert not screen.close()
    assert screen.isVisible()
    assert "disk full" in screen.save_status_label.text()
    monkeypatch.setattr(manager, "save", original_save)
    assert screen.close()
    database.close()


def test_completed_clue_and_line_indicator_follow_undo(app):
    board, _session = board_for(app, ((1, 1, 1),))
    viewport = board.grid_viewport()
    row_edge, _ = board._clue_edges(viewport)
    center_y = cell_point(board, 0, 0).y()
    indicator = QPoint(round(row_edge - 2), center_y)
    before = board.grab().toImage().pixelColor(indicator)
    start, end = cell_point(board, 0, 0), cell_point(board, 2, 0)
    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(board, end)
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=end)
    app.processEvents()
    assert board._analysis.rows[0].status is LineStatus.COMPLETED
    assert board._analysis.rows[0].completed_clues == (True,)
    assert all(column.status is LineStatus.COMPLETED for column in board._analysis.columns)
    after = board.grab().toImage().pixelColor(indicator)
    assert before != after
    board.undo()
    assert board._analysis.rows[0].completed_clues == (False,)
    board.close()


def test_deep_clue_bands_scroll_independently_and_stay_pinned(app):
    pattern = tuple(tuple((x + y) % 2 for x in range(50)) for y in range(50))
    board, _session = board_for(app, pattern)
    viewport = board.grid_viewport()
    row_edge, column_edge = board._clue_edges(viewport)
    assert len(board.session.puzzle.row_clues[0]) > board._clue_capacity(row_edge)
    assert len(board.session.puzzle.column_clues[0]) > board._clue_capacity(column_edge)

    def wheel_at(point):
        event = QWheelEvent(
            point,
            point,
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.ScrollUpdate,
            False,
        )
        QApplication.sendEvent(board, event)

    original_zoom = board.camera.cell_size
    wheel_at(QPointF(row_edge - 5, viewport.center().y()))
    assert board.row_clue_offset == 1
    assert board.camera.cell_size == original_zoom
    wheel_at(QPointF(viewport.center().x(), column_edge - 5))
    assert board.column_clue_offset == 1
    assert board.camera.cell_size == original_zoom
    board.zoom(3.0, viewport.center())
    row_edge, column_edge = board._clue_edges(board.grid_viewport())
    assert row_edge == board.grid_viewport().left()
    assert column_edge == board.grid_viewport().top()
    board.close()
