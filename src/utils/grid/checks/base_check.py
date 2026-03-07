from dataclasses import dataclass

from pandas import DataFrame
from PySide6 import QtCore


@dataclass
class CellRange:
    row_start: int
    row_end: int
    col_start: int
    col_end: int

    def contains(self, index: QtCore.QModelIndex) -> bool:
        return (
            self.row_start <= index.row() <= self.row_end
            and self.col_start <= index.column() <= self.col_end
        )


CellIssue = tuple[QtCore.QModelIndex, str]
# NOTE: row, col, value, cell_tooltip, wide_tooltip
BulkResult = tuple[int, int, str, str | None, str | None]


class BaseCheck:
    def check_cell(self, index: QtCore.QModelIndex, value: str) -> str | CellIssue:
        return value

    def check_wide(self, raw_data: DataFrame, index: QtCore.QModelIndex, value: str) -> list[CellIssue]:
        return []

    # NOTE: this is for pastes/initial load of data
    def check_bulk(self, raw_data: DataFrame, col: int, changed_range: CellRange) -> list[BulkResult]:
        return []
