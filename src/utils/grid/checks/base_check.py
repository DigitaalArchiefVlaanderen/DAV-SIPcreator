from dataclasses import dataclass

from pandas import DataFrame


@dataclass
class CellRange:
    row_start: int
    row_end: int
    col_start: int
    col_end: int

# NOTE: row, col, value, cell_tooltip, wide_tooltip
BulkResult = tuple[int, int, str, str | None, str | None]


class BaseCheck:
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        return []
