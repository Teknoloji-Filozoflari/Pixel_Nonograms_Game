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


def toolbar():
    app = QApplication.instance() or QApplication([])
    widget = InventoryToolbar(puzzle())
    widget.set_counts({item: 2 for item in HelperItemId})
    widget.show()
    app.processEvents()
    return widget


def test_compact_buttons_show_counts_and_details_only_after_selection():
    widget = toolbar()
    assert not widget.detail.isVisible()
    assert widget.item_buttons[HelperItemId.ANALYSIS_LENS].text() == "Mercek 2"
    widget.item_buttons[HelperItemId.ANALYSIS_LENS].click()
    assert widget.detail.isVisible()
    assert "olası yerleşimlerini" in widget.description_label.text()
    assert "Kalan: 2" in widget.description_label.text()
    assert widget.target_label.text() == "Hedef: seçilmedi"
    assert not widget.use_button.isEnabled()
    widget.close()


def test_target_must_be_chosen_and_axis_change_clears_it():
    widget = toolbar()
    requested = []
    widget.use_requested.connect(lambda *args: requested.append(args))
    widget.item_buttons[HelperItemId.ANALYSIS_LENS].click()
    widget.use_button.click()
    assert requested == []
    widget.line_box.setCurrentIndex(2)
    assert widget.target_label.text() == "Hedef: 2. satır"
    assert widget.use_button.isEnabled()
    widget.axis_box.setCurrentIndex(1)
    assert widget.line_box.count() == 6  # Placeholder + five columns.
    assert widget.target_label.text() == "Hedef: seçilmedi"
    assert not widget.use_button.isEnabled()
    widget.line_box.setCurrentIndex(5)
    widget.use_button.click()
    assert requested == [(HelperItemId.ANALYSIS_LENS, "column", 4)]
    widget.show_result("5. sütun incelendi", consumed=True)
    assert widget.target_label.text() == "Hedef: seçilmedi"
    assert not widget.use_button.isEnabled()
    widget.close()


def test_scanners_require_target_and_automatic_aids_explain_scope():
    widget = toolbar()
    widget.item_buttons[HelperItemId.ROW_SCANNER].click()
    assert widget.axis_box.currentData() == "row"
    assert not widget.axis_box.isEnabled()
    assert widget.line_box.count() == 4
    assert not widget.use_button.isEnabled()
    widget.line_box.setCurrentIndex(3)
    assert widget.target_label.text() == "Hedef: 3. satır"
    widget.item_buttons[HelperItemId.COLUMN_SCANNER].click()
    assert widget.axis_box.currentData() == "column"
    assert widget.line_box.count() == 6
    assert not widget.use_button.isEnabled()
    widget.item_buttons[HelperItemId.ERROR_CHECK].click()
    assert "otomatik belirlenir" in widget.target_label.text()
    assert widget.use_button.isEnabled()
    widget.set_available(False)
    assert not widget.use_button.isEnabled()
    widget.close()


def test_zero_stock_can_be_inspected_but_not_used():
    widget = toolbar()
    widget.set_counts({})
    widget.item_buttons[HelperItemId.LOGIC_HINT].click()
    assert "Kalan: 0" in widget.description_label.text()
    assert not widget.use_button.isEnabled()
    widget.close()
