import pandas as pd
from PySide6 import QtCore

from src.utils.constants import ANALOOG_DEFAULT_VALUE, ColumnName, RowType
from src.utils.data_objects.sip import SIP
from src.utils.grid.checks.analog import AnalogPathInSipCheck, BeschrijvingCheck, VerpakkingCheck
from src.utils.grid.checks.base_check import CellRange
from src.utils.grid.table.common import CellColor, CommonDataVerificationTable, MarkingSource
from src.utils.workers.worker import Worker

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

    def _get_empty_rows(self) -> set[int]:
        return {row for row in range(self.raw_data.shape[0]) if self._is_row_empty(row)}

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

        first_new = self.raw_data.shape[0]
        self.beginInsertRows(QtCore.QModelIndex(), first_new, first_new + count - 1)

        self.raw_data = pd.concat([self.raw_data, new_df], ignore_index=True)
        self.sip.grid_data.data_as_df = self.raw_data

        self.endInsertRows()

        for row in range(first_new, first_new + count):
            self._mark_disabled_columns_for_row(row)

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
            QtCore.QTimer.singleShot(0, self._ensure_empty_bottom_row)

        self.data_rows_changed_signal.emit(self.count_data_rows())

        return True

    def set_bulk_data(self, changes: list[tuple[QtCore.QModelIndex, str]]) -> None:
        if not changes:
            return

        # Mark all active workers as stale and stop them — their results are based on old data
        for worker, _ in self._active_workers:
            worker.stale = True
            worker.forcibly_stop_signal.emit()

        max_row_needed = max(index.row() for index, _ in changes)

        if max_row_needed >= self.raw_data.shape[0]:
            extra = max_row_needed - self.raw_data.shape[0] + 2
            self._insert_empty_rows(extra)

        raw_changes = [(index.row(), index.column(), self._sanitize_value(value)) for index, value in changes]

        df_copy = self.raw_data.copy()
        columns = list(df_copy.columns)
        disabled_col_indices = [df_copy.columns.get_loc(col) for col in DISABLED_COLUMNS if col in df_copy.columns]

        def background_apply():
            auto_fill_rows: list[tuple[int, str]] = []

            for row, col, value in raw_changes:
                if columns[col] == ColumnName.PATH_IN_SIP.value:
                    auto_fill_rows.append((row, value))

                df_copy.iat[row, col] = value

            if auto_fill_rows:
                self._background_bulk_auto_fill(df_copy, auto_fill_rows)

            markings = self._background_build_disabled_markings(df_copy, disabled_col_indices)
            data_row_count = self._background_count_data_rows(df_copy)
            needs_empty_row = df_copy.shape[0] == 0 or not self._background_is_row_empty(df_copy, df_copy.shape[0] - 1)

            return df_copy, markings, data_row_count, needs_empty_row

        Worker.start(
            background_apply,
            on_result=self._on_analog_bulk_data_applied,
            on_finished=self._check_validation_complete,
            track_in=self._active_workers,
        )

    def _on_analog_bulk_data_applied(self, result: tuple) -> None:
        df_copy, markings, data_row_count, needs_empty_row = result

        self.beginResetModel()
        self.raw_data = df_copy
        self.sip.grid_data.data_as_df = self.raw_data
        self.markings = markings
        self.endResetModel()

        if needs_empty_row:
            self._insert_empty_rows(1)

        cell_range = CellRange(
            row_start=0,
            row_end=self.raw_data.shape[0] - 1,
            col_start=0,
            col_end=self.raw_data.shape[1] - 1,
        )

        self.validate_range(cell_range)

        self.data_rows_changed_signal.emit(data_row_count)

    @staticmethod
    def _background_build_disabled_markings(
        df: "pd.DataFrame",
        disabled_col_indices: list[int],
    ) -> dict:
        markings = {}

        for col in disabled_col_indices:
            for row in df.index:
                markings[(row, col, MarkingSource.CELL)] = (CellColor.GREY, "")

        return markings

    @staticmethod
    def _background_count_data_rows(df: "pd.DataFrame") -> int:
        count = 0

        for row in range(df.shape[0]):
            if not AnalogDataVerificationTable._background_is_row_empty(df, row):
                count += 1

        return count

    @staticmethod
    def _background_is_row_empty(df: "pd.DataFrame", row: int) -> bool:
        for col in range(df.shape[1]):
            if str(df.iat[row, col]) != "":
                return False

        return True

    @staticmethod
    def _background_bulk_auto_fill(df: "pd.DataFrame", rows: list[tuple[int, str]]) -> None:
        if ColumnName.TYPE.value not in df.columns:
            return

        type_col = df.columns.get_loc(ColumnName.TYPE.value)
        dossier_ref_col = df.columns.get_loc(ColumnName.DOSSIER_REF.value)
        analoog_col = df.columns.get_loc(ColumnName.ANALOOG.value)
        has_naam = ColumnName.NAAM.value in df.columns
        naam_col = df.columns.get_loc(ColumnName.NAAM.value) if has_naam else None

        for row, value in rows:
            if value:
                new_type = RowType.STUK if "/" in value else RowType.DOSSIER
                new_ref = value.split("/", 1)[0]
                new_analoog = ANALOOG_DEFAULT_VALUE
            else:
                new_type = ""
                new_ref = ""
                new_analoog = ""

            df.iat[row, type_col] = new_type
            df.iat[row, dossier_ref_col] = new_ref
            df.iat[row, analoog_col] = new_analoog

            if has_naam:
                df.iat[row, naam_col] = value

    def _auto_fill_from_path(self, row: int, value: str) -> None:
        if ColumnName.TYPE.value not in self.raw_data.columns:
            return

        type_col = self.raw_data.columns.get_loc(ColumnName.TYPE.value)
        dossier_ref_col = self.raw_data.columns.get_loc(ColumnName.DOSSIER_REF.value)
        analoog_col = self.raw_data.columns.get_loc(ColumnName.ANALOOG.value)

        if value:
            new_type = RowType.STUK if "/" in value else RowType.DOSSIER
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
        insert_pos = col_loc + spaces
        self.raw_data.insert(insert_pos, new_column_name, "")

        self.shift_markings_for_insert(insert_pos)
        self.endResetModel()

    def get_non_empty_df(self) -> pd.DataFrame:
        non_empty_mask = [not self._is_row_empty(row) for row in range(self.raw_data.shape[0])]

        return self.raw_data[non_empty_mask].reset_index(drop=True)
