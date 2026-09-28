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
        point = QPoint(
            round(rect.left() + (x + 0.5) * rect.width() / 2),
            round(rect.top() + (y + 0.5) * rect.height() / 2),
        )
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


def test_fifth_row_and_column_numbers_are_inside_edge_cells(app):
    solution = tuple(tuple(int(x == y) for x in range(15)) for y in range(10))
    board, _ = board_for(app, solution)
    viewport = board.grid_viewport()
    labels = board._five_step_labels(viewport)
    assert {axis for axis, _, _ in labels} == {"row", "column"}
    image = board.grab().toImage()
    for axis, number, rect in labels:
        expected = (14, number - 1) if axis == "row" else (number - 1, 9)
        assert board._cell_at(rect.center()) == expected
        assert viewport.contains(rect)
        colors = {image.pixelColor(x, y).rgba()
                  for x in range(int(rect.left()), int(rect.right()))
                  for y in range(int(rect.top()), int(rect.bottom()))}
        assert len(colors) > 1
    board.close()


def test_rectangular_board_has_distinct_final_row_and_column_numbers(app):
    board, _ = board_for(app, tuple(tuple(1 for _ in range(15)) for _ in range(10)))
    labels = board._five_step_labels(board.grid_viewport())
    row = next(rect for axis, n, rect in labels if axis == "row" and n == 10)
    column = next(rect for axis, n, rect in labels if axis == "column" and n == 15)
    assert not row.intersects(column)
    board.close()


def test_board_uses_exact_puzzle_dimensions_without_partial_trimming(app):
    puzzles = {puzzle.title: puzzle for puzzle in built_in_puzzles()}
    tulip = puzzles["Lale"]
    board = BoardWidget(GameSession(tulip))
    assert (board.display_width, board.display_height) == (17, 17)
    board.close()
    sailboat = puzzles["Yelkenli"]
    board = BoardWidget(GameSession(sailboat))
    assert (board.display_width, board.display_height) == (27, 27)
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
    assert all(button.isVisible() for button in screen.color_buttons.values())
    screen.color_buttons[2].click()
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
    QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=row_clue_point(screen.board, 0))
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
    border = (
        board.grab()
        .toImage()
        .pixelColor(QPoint(round(warning.left()), round(warning.center().y())))
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
    border = (
        board.grab().toImage().pixelColor(QPoint(round(warning.center().x()), round(warning.top())))
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


@pytest.mark.parametrize("use_helper", [False, "area", "row", "column"])
def test_completion_dialog_reports_first_reward_once(app, tmp_path, use_helper):
    puzzle = replace(puzzle_for(((1,),)), reward_item_id=HelperItemId.LOGIC_HINT)
    database = Database(tmp_path / "reward.sqlite3")
    manager = SaveManager(database)
    inventory = InventoryService(database, manager)
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    screen = GameScreen(
        GameSession(puzzle), settings=settings, save_manager=manager, inventory=inventory
    )
    screen.show()
    app.processEvents()

    if use_helper:
        item = HelperItemId.LOGIC_HINT if use_helper == "area" else HelperItemId.ROW_SCANNER
        with database.connection:
            database.connection.execute(
                "INSERT INTO inventory(item_id, quantity) VALUES (?, 1)",
                (item.value,),
            )
        screen._use_inventory_item(item, None, None)
        assert screen.completion_dialog is None
        QTest.mouseClick(screen.board, Qt.MouseButton.RightButton, pos=cell_point(screen.board, 0, 0))
        assert screen.board.area_helper is None
        assert not screen.board.line_helper
        assert not screen.session.completed
        assert database.item_count(item) == 1
        screen._use_inventory_item(item, None, None)
        point = (row_clue_point(screen.board, 0) if use_helper == "row" else
                 column_clue_point(screen.board, 0) if use_helper == "column" else
                 cell_point(screen.board, 0, 0))
        QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=point)
    else:
        QTest.mouseClick(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 0, 0))
    app.processEvents()
    assert screen.completion_dialog is not None
    assert screen.completion_dialog.isVisible()
    assert not screen.completion_preview.hidden
    assert screen.completion_preview.accessibleName() == "Tamamlanan resim"
    assert screen.title_label.text() == puzzle.title
    assert "Bulmaca tamamlandı" in screen.completion_dialog.windowTitle()
    assert "Kazandığın ödül: 1 × 3×3 Alan Çözücü" in screen.completion_reward_label.text()
    assert all(
        "saniye" not in label.text() and "hamle" not in label.text()
        for label in screen.completion_dialog.findChildren(QLabel)
    )
    assert database.item_count(HelperItemId.LOGIC_HINT) == 3

    screen.completion_dialog.accept()
    screen.board.undo()
    screen.board.redo()
    app.processEvents()
    assert "daha önce alındı" in screen.completion_reward_label.text()
    assert database.item_count(HelperItemId.LOGIC_HINT) == 3
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


def test_fullscreen_shows_all_deep_clues_and_keeps_them_clickable(app):
    pattern = tuple(tuple((x+y) % 2 for x in range(50)) for y in range(50))
    board, _session = board_for(app, pattern)
    board.fullscreen_clues = True
    board.resize(1600, 1000)
    board.fit_to_screen()
    viewport = board.grid_viewport()
    for edge in (viewport.left(), viewport.top()):
        capacity = board._clue_capacity(edge)
        assert set(board._visible_clue_indices(25, capacity, 0)) == set(range(25))
    assert board._clue_at(row_clue_point(board, 0, 24)) == ('row', 0, 0)
    assert board._clue_at(column_clue_point(board, 0, 24)) == ('column', 0, 0)
    board.readable_zoom()
    board.camera.pan_x = -200
    board.camera.pan_y = -200
    assert board._clue_edges(board.grid_viewport()) == (viewport.left(), viewport.top())
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


@pytest.mark.parametrize(
    "button,expected",
    [
        (Qt.MouseButton.LeftButton, CellState.FILLED),
        (Qt.MouseButton.RightButton, CellState.EMPTY),
    ],
)
@pytest.mark.parametrize("vertical", [False, True])
def test_axis_lock_prevents_drift_and_counts_unique_cells(app, button, expected, vertical):
    board, session = board_for(app, ((1,) * 10,) * 10)
    messages = []
    board.stroke_changed.connect(messages.append)
    start = cell_point(board, 1, 1)
    first = cell_point(board, 1, 3) if vertical else cell_point(board, 3, 1)
    drift = cell_point(board, 3, 7) if vertical else cell_point(board, 7, 3)
    QTest.mousePress(board, button, pos=start)
    QTest.mouseMove(board, first)
    QTest.mouseMove(board, drift)
    assert messages[-1] == ("Dikey" if vertical else "Yatay") + " · 7 hücre"
    # Retracing the same cells must not inflate the count.
    QTest.mouseMove(board, first)
    assert messages[-1].endswith("7 hücre")
    QTest.mouseRelease(board, button, pos=drift)
    assert messages[-1] == ""
    for y in range(10):
        for x in range(10):
            marked = (x == 1 and 1 <= y <= 7) if vertical else (y == 1 and 1 <= x <= 7)
            assert session.cell_at(x, y).state is (expected if marked else CellState.UNKNOWN)
    assert session.move_count == 1
    board.undo()
    assert all(mark.state is CellState.UNKNOWN for row in session.cells for mark in row)
    board.redo()
    assert sum(mark.state is expected for row in session.cells for mark in row) == 7
    board.close()


def test_freehand_and_release_endpoint_and_outside_press(app):
    board, session = board_for(app, ((1,) * 10,) * 10)
    board.axis_lock = False
    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 1, 1))
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 4, 4))
    assert all(session.cell_at(n, n).state is CellState.FILLED for n in range(1, 5))
    assert session.move_count == 1
    board.undo()
    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=QPoint(2, 2))
    QTest.mouseMove(board, cell_point(board, 3, 3))
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 3, 3))
    assert not board._stroke_active
    assert all(mark.state is CellState.UNKNOWN for row in session.cells for mark in row)
    board.close()


def test_axis_stroke_outside_and_reentry_stays_on_original_line(app):
    board, session = board_for(app, ((1,) * 10,) * 10)
    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 1, 2))
    QTest.mouseMove(board, cell_point(board, 3, 2))
    QTest.mouseMove(board, QPoint(board.width() + 20, board.height() + 20))
    QTest.mouseMove(board, cell_point(board, 7, 6))
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 7, 6))
    assert all(session.cell_at(x, 2).state is CellState.FILLED for x in range(1, 8))
    assert session.cell_at(7, 6).state is CellState.UNKNOWN
    assert session.move_count == 1
    board.close()


def test_large_board_readable_clues_hit_testing_and_pin_switch(app):
    pattern = tuple(tuple((x + y) % 2 for x in range(50)) for y in range(50))
    board, session = board_for(app, pattern)
    initial = board._clue_bands()
    board.configure_view(pin_clues=True, expanded_clues=True, clue_font_size=22)
    assert board._clue_bands()[0] > initial[0]
    assert board._clue_bands()[1] > initial[1]
    assert board.grid_viewport().width() >= 100
    board.readable_zoom()
    assert int(board.camera.cell_size * 0.58) >= 22
    viewport = board.grid_viewport()
    board.camera.pan_x = board.camera.pan_y = -400
    board.camera.constrain(viewport, 50, 50)
    assert board._clue_edges(viewport) == (viewport.left(), viewport.top())
    x0, y0, _, _ = board.camera.visible_cells(viewport, 50, 50)
    row = y0 + 1
    edge = board._clue_edges(viewport)[0]
    capacity = board._clue_capacity(viewport.left())
    slot = min(float(board.clue_font_size + 11), (viewport.left() - 8) / capacity)
    point = QPointF(
        edge - 8 - slot / 2,
        board.camera.cell_origin(0, row, viewport).y() + board.camera.cell_size / 2,
    )
    assert board._clue_at(point) == ("row", row, len(session.puzzle.row_clues[row]) - 1)
    before = session.cells
    board.configure_view(pin_clues=False, expanded_clues=True, clue_font_size=22)
    assert board._clue_edges(board.grid_viewport())[0] < board.grid_viewport().left()
    board.fit_to_screen()
    assert session.cells == before
    assert board.camera.cell_size * 50 <= board.grid_viewport().width()
    assert board.camera.cell_size * 50 <= board.grid_viewport().height()
    board.close()


def test_control_preferences_persist_and_live_counter_clears(app, tmp_path):
    settings = QSettings(str(tmp_path / "controls.ini"), QSettings.Format.IniFormat)
    puzzle = puzzle_for(((1,) * 10,) * 10)
    screen = GameScreen(GameSession(puzzle), settings=settings)
    screen.show()
    app.processEvents()
    screen.axis_lock_action.setChecked(False)
    screen.pin_clues_action.setChecked(False)
    screen.expanded_clues_action.setChecked(True)
    screen.clue_font_actions[22].trigger()
    screen.close()
    settings.sync()
    restored = QSettings(settings.fileName(), QSettings.Format.IniFormat)
    screen = GameScreen(GameSession(puzzle), settings=restored)
    screen.show()
    app.processEvents()
    assert not screen.board.axis_lock
    assert not screen.board.pin_clues
    assert screen.board.expanded_clues
    assert screen.board.clue_font_size == 22
    screen.board.fit_to_screen()
    QTest.mousePress(screen.board, Qt.MouseButton.LeftButton, pos=cell_point(screen.board, 0, 0))
    assert "1 hücre" in screen.stroke_label.text()
    screen.board.finish_active_stroke()
    assert screen.stroke_label.text() == ""
    assert screen.session.move_count == 1
    screen.close()


def test_note_tool_drag_undo_and_assumption_banner(app, tmp_path):
    settings = QSettings(str(tmp_path / "notes.ini"), QSettings.Format.IniFormat)
    screen = GameScreen(GameSession(puzzle_for(((1,) * 10,) * 10)), settings=settings)
    screen.show()
    app.processEvents()
    screen.tool_buttons["note"].click()
    board = screen.board
    start, end = cell_point(board, 1, 1), cell_point(board, 4, 1)
    QTest.mousePress(board, Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(board, end)
    QTest.mouseRelease(board, Qt.MouseButton.LeftButton, pos=end)
    assert all(screen.session.cell_at(x, 1).note for x in range(1, 5))
    assert screen.session.move_count == 1
    board.undo()
    assert not any(mark.note for row in screen.session.cells for mark in row)
    board.redo()
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=start)
    assert not screen.session.cell_at(1, 1).note
    screen.assumption_start_button.click()
    app.processEvents()
    assert screen.assumption_banner.isVisible()
    QTest.mouseClick(board, Qt.MouseButton.LeftButton, pos=cell_point(board, 0, 0))
    assert screen.session.cell_at(0, 0).note
    assert not screen.session.snapshot().cells[0][0].note
    screen.assumption_cancel_button.click()
    assert not screen.assumption_banner.isVisible()
    assert not screen.session.cell_at(0, 0).note
    screen.close()


def test_assist_preferences_are_independent_and_persist(app, tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "assist.ini"), QSettings.Format.IniFormat)
    puzzle = puzzle_for(((1, 0, 0), (0, 1, 1)))
    screen = GameScreen(GameSession(puzzle), settings=settings)
    screen.show()
    app.processEvents()
    for action in screen.assist_actions.values():
        action.setChecked(False)
    screen.session.fill_cell(0, 0)
    screen.board.refresh_session()
    assert screen.session.cell_at(1, 0).state is CellState.UNKNOWN
    screen.assist_actions["auto_clues"].setChecked(True)
    assert screen.board.auto_cross_clues
    assert screen.board._analysis.rows[0].completed_clues == (True,)
    assert not screen.session.is_clue_crossed("row", 0, 0)
    assert screen.session.cell_at(1, 0).state is CellState.UNKNOWN
    calls = []
    monkeypatch.setattr(screen.board, "_paint_overfilled_lines", lambda *args: calls.append(1))
    screen.board.grab()
    assert not calls
    screen.assist_actions["errors"].setChecked(True)
    screen.board.grab()
    assert calls
    screen.assist_actions["auto_x"].setChecked(True)
    assert screen.session.cell_at(1, 0).auto_sources == 4
    screen.board.undo()
    assert screen.session.cell_at(1, 0).state is CellState.UNKNOWN
    screen.close()
    settings.sync()
    restored = GameScreen(
        GameSession(puzzle), settings=QSettings(settings.fileName(), QSettings.Format.IniFormat)
    )
    assert restored.session.auto_x_completed_lines
    assert not restored.session.auto_x_crossed_lines
    assert restored.board.auto_cross_clues and restored.board.show_errors
    restored.close()


@pytest.mark.parametrize('theme', ['paper', 'night'])
def test_white_board_and_unboxed_coordinate_numbers(app, theme):
    from pixel_nonograms.ui.theme import apply_theme

    board, _ = board_for(app, tuple(tuple(1 for _ in range(10)) for _ in range(10)))
    apply_theme(board, theme)
    image = board.grab().toImage()
    assert image.pixelColor(cell_point(board, 2, 2)).name() == '#ffffff'
    for _, _, rect in board._five_step_labels(board.grid_viewport()):
        # A label corner must retain the white cell, rather than a theme-colored badge.
        pixel = image.pixelColor(int(rect.left()) + 1, int(rect.top()) + 1)
        assert pixel.name() == '#ffffff'
    board.close()


def test_colored_line_warning_uses_each_color_quota_and_follows_undo(app):
    board, session = board_for(app, ((1, 1, 0), (2, 0, 2)), ('#C64E68', '#38876A'))
    session.fill_cell(0, 0, 2)
    assert board._overfilled_lines() == ((0,), ())
    session.undo()
    session.fill_cell(1, 0, 2)
    assert board._overfilled_lines() == ((0,), (1,))
    session.undo()
    assert board._overfilled_lines() == ((), ())
    # Wrong color exceeds its own quota although the total filled count fits.
    board.close()
    board, session = board_for(app, ((1, 2, 0), (1, 2, 0)), ('#C64E68', '#38876A'))
    session.fill_cell(0, 0, 1)
    session.fill_cell(1, 0, 1)
    assert board._overfilled_lines() == ((0,), (1,))
    session.clear_cell(1, 0)
    assert board._overfilled_lines() == ((), ())
    session.mark_note(2, 0, symbol='?')
    assert board._overfilled_lines() == ((), ())
    board.close()
