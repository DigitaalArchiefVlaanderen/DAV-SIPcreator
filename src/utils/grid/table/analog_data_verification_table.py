from functools import partial

import pandas as pd
from PySide6 import QtCore

from src.utils.constants import ColumnName, ANALOOG_DEFAULT_VALUE, RowType, BusinessRules
from src.utils.data_objects.sip import SIP
from src.utils.grid.checks.analog import AnalogPathInSipCheck, BeschrijvingCheck, VerpakkingCheck
from src.utils.grid.checks.base_check import CellRange
from src.utils.grid.table.common import CommonDataVerificationTable, CellColor, MarkingSource


DISABLED_COLUMNS = [
    ColumnName.TYPE.value,
    ColumnName.DOSSIER_REF.value,
    ColumnName.ANALOOG.value,
]

NON_DUPLICATABLE_COLUMNS = {
    ColumnName.PATH_IN_SIP.value,
    ColumnName.TYPE.value,
    ColumnName.DOSSIER_REF.value,
    ColumnName.ANALOOG.value,
    ColumnName.NAAM.value,
    ColumnName.OPENINGSDATUM.value,
    ColumnName.SLUITINGSDATUM.value,
}


class AnalogDataVerificationTable(CommonDataVerificationTable):
    data_rows_changed_signal = QtCore.Signal(int)

    def __init__(self, sip: SIP, editable: bool = True) -> None:
        super().__init__(sip, editable)

        self.COLUMN_VALIDATORS = {
            **self.COLUMN_VALIDATORS,
            ColumnName.PATH_IN_SIP: AnalogPathInSipCheck(),
            ColumnName.ID_BESCHRIJVING: BeschrijvingCheck(),
            ColumnName.ID_VERPAKKING: VerpakkingCheck(),
        }

        self._mark_disabled_columns()
        self._ensure_empty_bottom_row()

    def _mark_disabled_columns(self) -> None:
        for col in DISABLED_COLUMNS:
            if col in self.raw_data.columns:
                self.disable_column(col)

    def _get_empty_rows(self, cell_range: CellRange) -> set[int]:
        return {
            row
            for row in range(cell_range.row_start, cell_range.row_end + 1)
            if self._is_row_empty(row)
        }

    def _is_row_empty(self, row: int) -> bool:
        for col in range(self.raw_data.shape[1]):
            if str(self.raw_data.iat[row, col]) != "":
                return False

        return True

    def count_data_rows(self) -> int:
        return sum(1 for row in range(self.raw_data.shape[0]) if not self._is_row_empty(row))

    def is_data_valid(self) -> bool:
        has_data_row = False

        for row in range(self.raw_data.shape[0]):
            if self._is_row_empty(row):
                continue

            has_data_row = True
            row_idx = self.raw_data.index[row]

            for col in range(self.raw_data.shape[1]):
                for source in (MarkingSource.CELL, MarkingSource.WIDE):
                    marking = self.markings.get((row_idx, col, source))

                    if marking and marking[0] == CellColor.RED:
                        return False

        return has_data_row

    def _ensure_empty_bottom_row(self) -> None:
        if self.raw_data.shape[0] == 0 or not self._is_row_empty(self.raw_data.shape[0] - 1):
            self._insert_empty_rows(1)

    def _insert_empty_rows(self, count: int) -> None:
        new_rows = []

        for _ in range(count):
            new_row = {col: "" for col in self.raw_data.columns}
            new_rows.append(new_row)

        new_df = pd.DataFrame(new_rows, columns=self.raw_data.columns)

        self.beginInsertRows(
            QtCore.QModelIndex(),
            self.raw_data.shape[0],
            self.raw_data.shape[0] + count - 1
        )

        self.raw_data = pd.concat([self.raw_data, new_df], ignore_index=True)
        self.sip.grid_data.data_as_df = self.raw_data

        self.endInsertRows()

    def setData(self, index, value: str, role=QtCore.Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role != QtCore.Qt.ItemDataRole.EditRole:
            return False

        value = self._sanitize_value(value)
        col_name = self.raw_data.columns[index.column()]

        if col_name == ColumnName.PATH_IN_SIP.value:
            self._auto_fill_from_path(index.row(), value)

        self.raw_data.iat[index.row(), index.column()] = value
        self.dataChanged.emit(index, index)

        self._validate_single_row(index.row())

        if index.row() == self.raw_data.shape[0] - 1 and value != "":
            QtCore.QTimer.singleShot(0, partial(self._insert_empty_rows, 1))

        self.data_rows_changed_signal.emit(self.count_data_rows())

        return True

    def set_bulk_data(self, changes: list[tuple[QtCore.QModelIndex, str]]) -> None:
        if not changes:
            return

        max_row_needed = max(index.row() for index, _ in changes)

        if max_row_needed >= self.raw_data.shape[0]:
            extra = max_row_needed - self.raw_data.shape[0] + 2
            self._insert_empty_rows(extra)

        min_row = float("inf")
        max_row = 0

        for index, value in changes:
            value = self._sanitize_value(value)
            col_name = self.raw_data.columns[index.column()]

            if col_name == ColumnName.PATH_IN_SIP.value:
                self._auto_fill_from_path(index.row(), value)

            self.raw_data.iat[index.row(), index.column()] = value

            min_row = min(min_row, index.row())
            max_row = max(max_row, index.row())

        self.dataChanged.emit(
            self.index(min_row, 0),
            self.index(max_row, self.raw_data.shape[1] - 1),
        )

        cell_range = CellRange(
            row_start=min_row,
            row_end=max_row,
            col_start=0,
            col_end=self.raw_data.shape[1] - 1,
        )

        self.validate_range(cell_range)
        self._ensure_empty_bottom_row()
        self.data_rows_changed_signal.emit(self.count_data_rows())

    def _auto_fill_from_path(self, row: int, value: str) -> None:
        if ColumnName.TYPE.value not in self.raw_data.columns:
            return

        type_col = self.raw_data.columns.get_loc(ColumnName.TYPE.value)
        dossier_ref_col = self.raw_data.columns.get_loc(ColumnName.DOSSIER_REF.value)
        analoog_col = self.raw_data.columns.get_loc(ColumnName.ANALOOG.value)

        if value:
            new_type = "" if "/" in value else RowType.DOSSIER
            new_ref = value.split("/", 1)[0]
            new_analoog = ANALOOG_DEFAULT_VALUE
        else:
            new_type = ""
            new_ref = ""
            new_analoog = ""

        self.raw_data.iat[row, type_col] = new_type
        self.raw_data.iat[row, dossier_ref_col] = new_ref
        self.raw_data.iat[row, analoog_col] = new_analoog

        if ColumnName.NAAM.value in self.raw_data.columns:
            naam_col = self.raw_data.columns.get_loc(ColumnName.NAAM.value)
            self.raw_data.iat[row, naam_col] = value

        self.dataChanged.emit(
            self.index(row, type_col),
            self.index(row, analoog_col),
        )

        self._mark_disabled_columns_for_row(row)

    def _mark_disabled_columns_for_row(self, row: int) -> None:
        row_idx = self.raw_data.index[row]

        for col_name in DISABLED_COLUMNS:
            if col_name not in self.raw_data.columns:
                continue

            col = self.raw_data.columns.get_loc(col_name)
            self.markings[(row_idx, col, MarkingSource.CELL)] = (CellColor.GREY, "")

    def insert_column(self, col_name: str) -> None:
        self.beginResetModel()

        new_column_name = col_name

        while (new_column_name := f"{new_column_name} ") in self.raw_data.columns:
            pass

        col_loc = self.raw_data.columns.get_loc(col_name)
        spaces = len(new_column_name) - len(col_name)
        self.raw_data.insert(col_loc + spaces, new_column_name, "")

        self.endResetModel()

    def get_non_empty_df(self) -> pd.DataFrame:
        non_empty_mask = [not self._is_row_empty(row) for row in range(self.raw_data.shape[0])]

        return self.raw_data[non_empty_mask].reset_index(drop=True)
