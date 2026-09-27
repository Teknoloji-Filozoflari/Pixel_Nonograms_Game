"""Fixed IDs for optional, deterministic puzzle aids."""

from enum import StrEnum


class HelperItemId(StrEnum):
    ANALYSIS_LENS = "analysis_lens"
    LOGIC_HINT = "logic_hint"
    ERROR_CHECK = "error_check"
    ROW_SCANNER = "row_scanner"
    COLUMN_SCANNER = "column_scanner"
    SECOND_LOOK = "second_look"
