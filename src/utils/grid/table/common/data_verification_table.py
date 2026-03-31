from PySide6 import QtCore

from src.utils.constants import ColumnName, RowType
from src.utils.data_objects.sip import SIP
from src.utils.grid.checks import BaseCheck, BulkResult, CellRange, DateCheck, NameCheck, RRNCheck
from src.utils.grid.checks.common.date_check import _check_format, _check_series_range, parse_date
from src.utils.grid.table.common.data_table import CellColor, DataTable, MarkingSource
from src.utils.workers.worker import Worker

DATE_COLUMNS = {ColumnName.OPENINGSDATUM.value, ColumnName.SLUITINGSDATUM.value}


class CommonDataVerificationTable(DataTable):
    validation_started_signal = QtCore.Signal()
    validation_finished_signal = QtCore.Signal()

    COLUMN_VALIDATORS: dict[ColumnName, BaseCheck] = {
        ColumnName.ID_RIJKSREGISTERNUMMER: RRNCheck(),
        ColumnName.NAAM: NameCheck(),
    }

    def __init__(self, sip: SIP, editable: bool = True) -> None:
        super().__init__(sip, editable)

        self._active_workers: list[tuple[Worker, QtCore.QThread]] = []

        date_check = DateCheck(series_provider=lambda: self.sip.series)
        self.COLUMN_VALIDATORS = {
            **self.COLUMN_VALIDATORS,
            ColumnName.OPENINGSDATUM: date_check,
            ColumnName.SLUITINGSDATUM: date_check,
        }

    @property
    def is_validating(self) -> bool:
        return len(self._active_workers) > 0

    def _sanitize_value(self, value: str) -> str:
        return str(value).encode(encoding="utf-8", errors="replace").decode("utf-8")

    def _get_empty_rows(self, cell_range: CellRange) -> set[int]:
        if ColumnName.TYPE.value not in self.raw_data.columns:
            return set()

        type_col = self.raw_data.columns.get_loc(ColumnName.TYPE.value)

        return {
            row
            for row in range(cell_range.row_start, cell_range.row_end + 1)
            if self.raw_data.iat[row, type_col] == RowType.GEEN
        }

    def _run_bulk_validators(self, cell_range: CellRange) -> tuple[list[BulkResult], set[int]]:
        results: list[BulkResult] = []
        empty_rows = self._get_empty_rows(cell_range)

        for column_name, check in self.COLUMN_VALIDATORS.items():
            if column_name.value not in self.raw_data.columns:
                continue

            col = self.raw_data.columns.get_loc(column_name.value)
            results.extend(r for r in check.check_bulk(self.raw_data, col, cell_range) if r[0] not in empty_rows)

        return results, empty_rows

    def _apply_bulk_results(
        self,
        results: list[BulkResult],
        cell_range: CellRange | None = None,
        empty_rows: set[int] | None = None,
    ) -> None:
        if cell_range:
            self._clear_validator_markings(cell_range, empty_rows or set())

        min_row = float("inf")
        max_row = 0
        min_col = float("inf")
        max_col = 0

        for row, col, value, cell_tooltip, wide_tooltip in results:
            self.raw_data.iat[row, col] = value
            index = self.index(row, col)

            if cell_tooltip:
                self.mark_cell(index, source=MarkingSource.CELL, tooltip=cell_tooltip)

            if wide_tooltip:
                self.mark_cell(index, source=MarkingSource.WIDE, tooltip=wide_tooltip)

            min_row = min(min_row, row)
            max_row = max(max_row, row)
            min_col = min(min_col, col)
            max_col = max(max_col, col)

        if cell_range:
            min_row = min(min_row, cell_range.row_start) if results else cell_range.row_start
            max_row = max(max_row, cell_range.row_end) if results else cell_range.row_end
            min_col = 0
            max_col = self.raw_data.shape[1] - 1

        if min_row <= max_row:
            self.dataChanged.emit(
                self.index(min_row, min_col),
                self.index(max_row, max_col),
            )

    def _clear_validator_markings(self, cell_range: CellRange, empty_rows: set[int]) -> None:
        row_range = set(range(cell_range.row_start, cell_range.row_end + 1)) - empty_rows
        valid_row_indices = {self.raw_data.index[row] for row in row_range}

        keys_to_remove = [
            key
            for key in self.markings
            if key[0] in valid_row_indices
            and (
                (key[2] == MarkingSource.WIDE)
                or (key[2] == MarkingSource.CELL and self.markings[key][0] != CellColor.GREY)
            )
        ]

        for key in keys_to_remove:
            del self.markings[key]

    def validate_all(self) -> None:
        if not self.raw_data.shape[0]:
            return

        self.validate_range(
            CellRange(
                row_start=0,
                row_end=self.raw_data.shape[0] - 1,
                col_start=0,
                col_end=self.raw_data.shape[1] - 1,
            )
        )

    def validate_range(self, cell_range: CellRange) -> None:
        self.validation_started_signal.emit()

        Worker.start(
            lambda: self._run_bulk_validators(cell_range),
            on_result=lambda result: self._apply_bulk_results(result[0], cell_range, result[1]),
            on_finished=self._check_validation_complete,
            track_in=self._active_workers,
        )

    def _check_validation_complete(self) -> None:
        if not self._active_workers:
            self.validation_finished_signal.emit()

    def _validate_single_row(self, row: int) -> None:
        self.validate_range(
            CellRange(
                row_start=row,
                row_end=row,
                col_start=0,
                col_end=self.raw_data.shape[1] - 1,
            )
        )

    def setData(self, index, value: str, role=QtCore.Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role != QtCore.Qt.ItemDataRole.EditRole:
            return False

        value = self._sanitize_value(value)

        self.raw_data.iat[index.row(), index.column()] = value
        self.dataChanged.emit(index, index)

        self._validate_single_row(index.row())

        col_name = self.raw_data.columns[index.column()]

        if col_name in DATE_COLUMNS:
            self._auto_update_dossier_dates(index)

        return True

    def set_bulk_data(self, changes: list[tuple[QtCore.QModelIndex, str]]) -> None:
        if not changes:
            return

        raw_changes = [(index.row(), index.column(), self._sanitize_value(value)) for index, value in changes]

        df_copy = self.raw_data.copy()

        def background_apply():
            date_rows: set[int] = set()

            for row, col, value in raw_changes:
                df_copy.iat[row, col] = value

                if df_copy.columns[col] in DATE_COLUMNS:
                    date_rows.add(row)

            return df_copy, date_rows

        Worker.start(
            background_apply,
            on_result=self._on_bulk_data_applied,
            on_finished=self._check_validation_complete,
            track_in=self._active_workers,
        )

    def _on_bulk_data_applied(self, result: tuple) -> None:
        df_copy, date_rows = result

        self.beginResetModel()
        self.raw_data = df_copy
        self.sip.grid_data.data_as_df = self.raw_data
        self.endResetModel()

        cell_range = CellRange(
            row_start=0,
            row_end=self.raw_data.shape[0] - 1,
            col_start=0,
            col_end=self.raw_data.shape[1] - 1,
        )

        self._validate_and_auto_update(cell_range, date_rows)

    def _validate_and_auto_update(self, cell_range: CellRange, date_rows: set[int]) -> None:
        def background_task():
            results, empty_rows = self._run_bulk_validators(cell_range)
            auto_updates = self._compute_auto_updates(date_rows) if date_rows else []

            return results, empty_rows, auto_updates

        Worker.start(
            background_task,
            on_result=lambda result: self._apply_validation_and_auto_updates(result, cell_range),
            on_finished=self._check_validation_complete,
            track_in=self._active_workers,
        )

    def _apply_validation_and_auto_updates(self, result: tuple, cell_range: CellRange | None = None) -> None:
        results, empty_rows, auto_updates = result

        self._apply_bulk_results(results, cell_range, empty_rows)

        for dossier_row_pos, col, value in auto_updates:
            self.setData(self.index(dossier_row_pos, col), value)

    def _compute_auto_updates(self, date_rows: set[int]) -> list[tuple[int, int, str]]:
        if ColumnName.TYPE.value not in self.raw_data.columns:
            return []

        if ColumnName.DOSSIER_REF.value not in self.raw_data.columns:
            return []

        type_col = self.raw_data.columns.get_loc(ColumnName.TYPE.value)
        dossier_ref_col = self.raw_data.columns.get_loc(ColumnName.DOSSIER_REF.value)
        opening_col = self.raw_data.columns.get_loc(ColumnName.OPENINGSDATUM.value)
        closing_col = self.raw_data.columns.get_loc(ColumnName.SLUITINGSDATUM.value)

        series = self.sip.series
        series_start = series.valid_from if series else None
        series_end = series.valid_to if series else None

        is_valid = lambda s: (
            _check_format(s) is None
            and _check_series_range(s, series_start, series_end) is None
            and parse_date(s) is not None
        )

        updates: list[tuple[int, int, str]] = []
        processed_refs: set[str] = set()

        for row in date_rows:
            row_type = self.raw_data.iat[row, type_col]

            if row_type != RowType.STUK:
                continue

            dossier_ref = self.raw_data.iat[row, dossier_ref_col]

            if dossier_ref in processed_refs:
                continue

            processed_refs.add(dossier_ref)

            dossier_mask = (self.raw_data.iloc[:, type_col] == RowType.DOSSIER) & (
                self.raw_data.iloc[:, dossier_ref_col] == dossier_ref
            )
            dossier_rows = self.raw_data.index[dossier_mask]

            if len(dossier_rows) == 0:
                continue

            dossier_row_pos = self.raw_data.index.get_loc(dossier_rows[0])

            stuk_mask = (self.raw_data.iloc[:, type_col] == RowType.STUK) & (
                self.raw_data.iloc[:, dossier_ref_col] == dossier_ref
            )

            stuk_openings = [
                d
                for v in self.raw_data.loc[stuk_mask, ColumnName.OPENINGSDATUM.value]
                if is_valid(s := str(v)) and (d := parse_date(s)) is not None
            ]
            stuk_closings = [
                d
                for v in self.raw_data.loc[stuk_mask, ColumnName.SLUITINGSDATUM.value]
                if is_valid(s := str(v)) and (d := parse_date(s)) is not None
            ]

            if stuk_openings:
                min_opening = min(stuk_openings).strftime("%Y-%m-%d")
                current_opening = str(self.raw_data.iat[dossier_row_pos, opening_col])
                current_is_valid = is_valid(current_opening)

                if not current_is_valid or current_opening > min_opening:
                    updates.append((dossier_row_pos, opening_col, min_opening))

            if stuk_closings:
                max_closing = max(stuk_closings).strftime("%Y-%m-%d")
                current_closing = str(self.raw_data.iat[dossier_row_pos, closing_col])
                current_is_valid = is_valid(current_closing)

                if not current_is_valid or current_closing < max_closing:
                    updates.append((dossier_row_pos, closing_col, max_closing))

        return updates

    def _auto_update_dossier_dates(self, index) -> None:
        if ColumnName.TYPE.value not in self.raw_data.columns:
            return

        if ColumnName.DOSSIER_REF.value not in self.raw_data.columns:
            return

        type_col = self.raw_data.columns.get_loc(ColumnName.TYPE.value)
        row_type = self.raw_data.iat[index.row(), type_col]

        if row_type != RowType.STUK:
            return

        dossier_ref_col = self.raw_data.columns.get_loc(ColumnName.DOSSIER_REF.value)
        dossier_ref = self.raw_data.iat[index.row(), dossier_ref_col]

        opening_col = self.raw_data.columns.get_loc(ColumnName.OPENINGSDATUM.value)
        closing_col = self.raw_data.columns.get_loc(ColumnName.SLUITINGSDATUM.value)

        dossier_mask = (self.raw_data.iloc[:, type_col] == RowType.DOSSIER) & (
            self.raw_data.iloc[:, dossier_ref_col] == dossier_ref
        )
        dossier_rows = self.raw_data.index[dossier_mask]

        if len(dossier_rows) == 0:
            return

        dossier_row_pos = self.raw_data.index.get_loc(dossier_rows[0])

        stuk_mask = (self.raw_data.iloc[:, type_col] == RowType.STUK) & (
            self.raw_data.iloc[:, dossier_ref_col] == dossier_ref
        )

        series = self.sip.series
        series_start = series.valid_from if series else None
        series_end = series.valid_to if series else None

        is_valid = lambda s: (
            _check_format(s) is None
            and _check_series_range(s, series_start, series_end) is None
            and parse_date(s) is not None
        )

        stuk_openings = [
            d
            for v in self.raw_data.loc[stuk_mask, ColumnName.OPENINGSDATUM.value]
            if is_valid(s := str(v)) and (d := parse_date(s)) is not None
        ]
        stuk_closings = [
            d
            for v in self.raw_data.loc[stuk_mask, ColumnName.SLUITINGSDATUM.value]
            if is_valid(s := str(v)) and (d := parse_date(s)) is not None
        ]

        dossier_updated = False

        if stuk_openings:
            min_opening = min(stuk_openings).strftime("%Y-%m-%d")
            current_opening = str(self.raw_data.iat[dossier_row_pos, opening_col])
            current_is_valid = is_valid(current_opening)

            should_update = not current_is_valid or current_opening > min_opening

            if should_update:
                self.setData(self.index(dossier_row_pos, opening_col), min_opening)
                dossier_updated = True

        if stuk_closings:
            max_closing = max(stuk_closings).strftime("%Y-%m-%d")
            current_closing = str(self.raw_data.iat[dossier_row_pos, closing_col])
            current_is_valid = is_valid(current_closing)

            should_update = not current_is_valid or current_closing < max_closing

            if should_update:
                self.setData(self.index(dossier_row_pos, closing_col), max_closing)
                dossier_updated = True

        if not dossier_updated:
            self._validate_single_row(dossier_row_pos)
