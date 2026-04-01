from dataclasses import dataclass

from pandas import DataFrame


@dataclass
class CellRange:
    row_start: int
    row_end: int
    col_start: int
    col_end: int


# (row, col, value, cell_tooltip, wide_tooltip)
# - row, col: cell position in the DataFrame
# - value: transformed cell value, or None if the check did not change it.
#          Only non-None values get written back to raw_data.
# - cell_tooltip: error message for this specific cell, or None
# - wide_tooltip: error message spanning related cells (e.g. duplicates), or None
BulkResult = tuple[int, int, str | None, str | None, str | None]


class BaseCheck:
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        return []
