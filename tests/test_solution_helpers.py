"""The six helpers apply exact solution edits and commit them atomically."""
from dataclasses import replace

import pytest
from test_inventory import grant, puzzle

from pixel_nonograms.core import CellState, GameSession, HelperItemId
from pixel_nonograms.persistence import Database, SaveManager
from pixel_nonograms.services import InventoryService


@pytest.fixture
def service(tmp_path):
    db = Database(tmp_path / "helpers.sqlite")
    manager = SaveManager(db)
    for item in HelperItemId:
        grant(manager, item)
        source = puzzle(f"extra-{item.value}", ((1,),), reward=item)
        completed = GameSession(source)
        completed.fill_cell(0, 0)
        manager.save(completed)
    yield InventoryService(db, manager)
    db.close()


def session(size=12):
    return GameSession(puzzle("target", tuple(tuple(int((x+y)%3 != 0)
                       for x in range(size)) for y in range(size))))


@pytest.mark.parametrize("axis,index", [("row", 2), ("column", 4)])
def test_entire_line_corrected_and_single_undo(service, axis, index):
    game = session()
    game.fill_cell(2, 2)
    before = game.cells
    result = service.use(HelperItemId.ROW_SCANNER, game, axis=axis, line_index=index)
    assert len(result.cells) >= 11
    for y in range(12):
        for x in range(12):
            if (axis == "row" and y == index) or (axis == "column" and x == index):
                mark = game.cell_at(x,y)
                assert mark.state is (CellState.FILLED if game.puzzle.solution[y][x]
                                      else CellState.EMPTY)
            else:
                assert game.cell_at(x,y) == before[y][x]
    after = game.cells
    assert service.save_manager.load(game.puzzle).cells == after
    game.undo()
    assert game.cells == before
    game.redo()
    assert game.cells == after


@pytest.mark.parametrize("item,side", [(HelperItemId.LOGIC_HINT,3),
                                     (HelperItemId.ERROR_CHECK,5),
                                     (HelperItemId.SECOND_LOOK,10)])
@pytest.mark.parametrize("size", [4,12])
def test_area_is_bounded_exact_and_does_not_auto_cross_outside(service,item,side,size):
    game = session(size)
    game.auto_x_completed_lines = True
    origin = (size-2, size-1)
    result = service.use(item,game,origin=origin)
    assert len(result.cells) == min(side,size)**2
    assert len({(x,y) for x,y,_ in result.cells}) == len(result.cells)
    for x,y,mark in result.cells:
        assert min(origin[0], size-side) <= x < size
        assert min(origin[1], size-side) <= y < size
        assert game.cell_at(x,y) == mark
        assert mark.color_id == game.puzzle.solution[y][x]
        assert mark.state is not CellState.UNKNOWN
    assert sum(m.state is not CellState.UNKNOWN for row in game.cells for m in row) == len(result.cells)


def test_smart_helper_corrects_wrong_fill_first_then_advances(service):
    game=session()
    game.fill_cell(0,0)  # solution is empty
    result=service.use(HelperItemId.ANALYSIS_LENS,game)
    assert result.corrected_cell == (0,0)
    assert game.cell_at(0,0).state is CellState.EMPTY
    game.undo()
    assert game.cell_at(0,0).state is CellState.FILLED
    game.redo()
    result=service.use(HelperItemId.ANALYSIS_LENS,game)
    assert result.corrected_cell is None
    assert len(result.cells)==1
    assert result.cells[0][2].state is CellState.FILLED


def test_color_correction_uses_actual_solution_color(service):
    p=replace(puzzle("colors",((1,0),(0,1))),palette=("#123456","#ABCDEF"),
              solution=((2,0),(0,1)), row_clues=None, column_clues=None)
    game=GameSession(p)
    game.fill_cell(0,0,1)
    result=service.use(HelperItemId.ANALYSIS_LENS,game)
    assert result.corrected_cell==(0,0)
    assert game.cell_at(0,0).color_id==2


def test_retired_five_cell_helper_cannot_be_used(service):
    game=session()
    before = game.cells
    with pytest.raises(ValueError, match="kaldırıldı"):
        service.use(HelperItemId.COLUMN_SCANNER,game)
    assert game.cells == before


def test_no_effect_and_failed_save_keep_board_history_and_inventory(service,monkeypatch):
    game=session()
    for x in range(12):
        if game.puzzle.solution[0][x]:
            game.fill_cell(x,0)
        else:
            game.mark_empty(x,0)
    counts=service.counts()
    assert service.use(HelperItemId.ROW_SCANNER,game,axis="row",line_index=0) is None
    assert service.counts()==counts
    before=game.cells
    moves=game.move_count
    def fail(*args,**kwargs):
        raise OSError("disk unavailable")
    monkeypatch.setattr(service.save_manager,"save",fail)
    with pytest.raises(OSError):
        service.use(HelperItemId.SECOND_LOOK,game,origin=(0,0))
    assert game.cells==before
    assert game.move_count==moves
    assert game.hint_count==0
    assert service.counts()==counts
