"""Offscreen checks for explicit targets and small inventory controls."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from pixel_nonograms.core import Difficulty, HelperItemId, Puzzle
from pixel_nonograms.ui.inventory_toolbar import InventoryToolbar


def puzzle():
    return Puzzle(
        id="toolbar",
        title="Araçlar",
        author="Test",
        description="",
        width=5,
        height=3,
        difficulty=Difficulty.EASY,
        tags=(),
        palette=("#123456",),
        solution=((1, 0, 0, 0, 0), (1, 0, 0, 0, 0), (1, 0, 0, 0, 0)),
    )


def toolbar(*, compact=False):
    app = QApplication.instance() or QApplication([])
    widget = InventoryToolbar(puzzle(), compact=compact)
    widget.set_counts({item: 2 for item in HelperItemId})
    widget.show()
    app.processEvents()
    return widget


def test_line_helper_supports_both_axes_and_requires_target():
    widget = toolbar(compact=True)
    requested = []
    widget.use_requested.connect(lambda *args: requested.append(args))
    widget.item_buttons[HelperItemId.ROW_SCANNER].click()
    assert requested == [(HelperItemId.ROW_SCANNER, None, None)]
    assert HelperItemId.COLUMN_SCANNER not in widget.item_buttons
    assert not widget.isVisible()
    widget.close()


def test_automatic_helpers_and_empty_stock():
    widget = toolbar()
    for item in HelperItemId:
        if item == HelperItemId.ROW_SCANNER:
            continue
        widget.select_item(item)
        assert not widget.axis_box.isVisible()
        assert widget.use_button.isEnabled()
    widget.set_counts({})
    assert not widget.use_button.isEnabled()
    widget.close()
