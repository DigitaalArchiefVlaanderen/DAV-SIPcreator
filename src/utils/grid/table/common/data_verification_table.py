from PySide6 import QtCore

from src.utils.constants import ColumnName
from src.utils.data_objects.sip import SIP
from src.utils.grid.checks import BaseCheck, CellRange, BulkResult, RRNCheck, NameCheck, DateCheck
from src.utils.grid.checks.common.date_check import parse_date, _check_format, _check_series_range
from src.utils.grid.table.common.data_table import DataTable, MarkingSource
from src.utils.workers.worker import Worker

DATE_COLUMNS = {ColumnName.OPENINGSDATUM.value, ColumnName.SLUITINGSDATUM.value}


class CommonDataVerificationTable(DataTable):
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
            if self.raw_data.iat[row, type_col] == "geen"
        }

    def _run_bulk_validators(self, cell_range: CellRange) -> list[BulkResult]:
        results: list[BulkResult] = []
        empty_rows = self._get_empty_rows(cell_range)

        for column_name, check in self.COLUMN_VALIDATORS.items():
            if column_name.value not in self.raw_data.columns:
                continue

            col = self.raw_data.columns.get_loc(column_name.value)
            results.extend(
                r for r in check.check_bulk(self.raw_data, col, cell_range)
                if r[0] not in empty_rows
            )

        return results

    def _apply_bulk_results(self, results: list[BulkResult]) -> None:
        min_row = float("inf")
        max_row = 0
        min_col = float("inf")
        max_col = 0

        for row, col, value, cell_tooltip, wide_tooltip in results:
            self.raw_data.iat[row, col] = value
            index = self.index(row, col)

            self.unmark_cell(index, MarkingSource.CELL)
            self.unmark_cell(index, MarkingSource.WIDE)

            if cell_tooltip:
                self.mark_cell(index, source=MarkingSource.CELL, tooltip=cell_tooltip)

            if wide_tooltip:
                self.mark_cell(index, source=MarkingSource.WIDE, tooltip=wide_tooltip)

            min_row = min(min_row, row)
            max_row = max(max_row, row)
            min_col = min(min_col, col)
            max_col = max(max_col, col)

        if results:
            self.dataChanged.emit(
                self.index(min_row, min_col),
                self.index(max_row, max_col),
            )

    def validate_all(self) -> None:
        if not self.raw_data.shape[0]:
            return

        self.validate_range(CellRange(
            row_start=0,
            row_end=self.raw_data.shape[0] - 1,
            col_start=0,
            col_end=self.raw_data.shape[1] - 1,
        ))

    def validate_range(self, cell_range: CellRange) -> None:
        worker = Worker(
            function=lambda: self._run_bulk_validators(cell_range),
            is_generator=False,
        )
        thread = QtCore.QThread()

        worker.moveToThread(thread)
        self._active_workers.append((worker, thread))

        thread.started.connect(worker.run)
        worker.result_ready_signal.connect(self._apply_bulk_results)

        worker.finished_signal.connect(thread.quit)
        worker.finished_signal.connect(thread.deleteLater)
        worker.finished_signal.connect(lambda: self._on_worker_finished(worker, thread))

        thread.start()

    def _on_worker_finished(self, worker: Worker, thread: QtCore.QThread) -> None:
        self._active_workers.remove((worker, thread))

        if not self._active_workers:
            self.validation_finished_signal.emit()

    def _validate_single_row(self, row: int) -> None:
        self.validate_range(CellRange(
            row_start=row,
            row_end=row,
            col_start=0,
            col_end=self.raw_data.shape[1] - 1,
        ))

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

        min_row = float("inf")
        max_row = 0
        min_col = float("inf")
        max_col = 0
        date_rows: set[int] = set()

        for index, value in changes:
            value = self._sanitize_value(value)

            self.raw_data.iat[index.row(), index.column()] = value

            min_row = min(min_row, index.row())
            max_row = max(max_row, index.row())
            min_col = min(min_col, index.column())
            max_col = max(max_col, index.column())

            if self.raw_data.columns[index.column()] in DATE_COLUMNS:
                date_rows.add(index.row())

        self.dataChanged.emit(
            self.index(min_row, min_col),
            self.index(max_row, max_col),
        )

        cell_range = CellRange(
            row_start=min_row,
            row_end=max_row,
            col_start=0,
            col_end=self.raw_data.shape[1] - 1,
        )

        self._validate_and_auto_update(cell_range, date_rows)

    def _validate_and_auto_update(self, cell_range: CellRange, date_rows: set[int]) -> None:
        def background_task():
            results = self._run_bulk_validators(cell_range)
            auto_updates = self._compute_auto_updates(date_rows) if date_rows else []

            return results, auto_updates

        worker = Worker(
            function=background_task,
            is_generator=False,
        )
        thread = QtCore.QThread()

        worker.moveToThread(thread)
        self._active_workers.append((worker, thread))

        thread.started.connect(worker.run)
        worker.result_ready_signal.connect(self._apply_validation_and_auto_updates)

        worker.finished_signal.connect(thread.quit)
        worker.finished_signal.connect(thread.deleteLater)
        worker.finished_signal.connect(lambda: self._on_worker_finished(worker, thread))

        thread.start()

    def _apply_validation_and_auto_updates(self, result: tuple) -> None:
        results, auto_updates = result

        self._apply_bulk_results(results)

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

            if row_type != "stuk":
                continue

            dossier_ref = self.raw_data.iat[row, dossier_ref_col]

            if dossier_ref in processed_refs:
                continue

            processed_refs.add(dossier_ref)

            dossier_mask = (
                (self.raw_data.iloc[:, type_col] == "dossier")
                & (self.raw_data.iloc[:, dossier_ref_col] == dossier_ref)
            )
            dossier_rows = self.raw_data.index[dossier_mask]

            if len(dossier_rows) == 0:
                continue

            dossier_row_pos = self.raw_data.index.get_loc(dossier_rows[0])

            stuk_mask = (
                (self.raw_data.iloc[:, type_col] == "stuk")
                & (self.raw_data.iloc[:, dossier_ref_col] == dossier_ref)
            )

            stuk_openings = [
                d for v in self.raw_data.loc[stuk_mask, ColumnName.OPENINGSDATUM.value]
                if is_valid(s := str(v)) and (d := parse_date(s)) is not None
            ]
            stuk_closings = [
                d for v in self.raw_data.loc[stuk_mask, ColumnName.SLUITINGSDATUM.value]
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

        if row_type != "stuk":
            return

        dossier_ref_col = self.raw_data.columns.get_loc(ColumnName.DOSSIER_REF.value)
        dossier_ref = self.raw_data.iat[index.row(), dossier_ref_col]

        opening_col = self.raw_data.columns.get_loc(ColumnName.OPENINGSDATUM.value)
        closing_col = self.raw_data.columns.get_loc(ColumnName.SLUITINGSDATUM.value)

        dossier_mask = (
            (self.raw_data.iloc[:, type_col] == "dossier")
            & (self.raw_data.iloc[:, dossier_ref_col] == dossier_ref)
        )
        dossier_rows = self.raw_data.index[dossier_mask]

        if len(dossier_rows) == 0:
            return

        dossier_row_pos = self.raw_data.index.get_loc(dossier_rows[0])

        stuk_mask = (
            (self.raw_data.iloc[:, type_col] == "stuk")
            & (self.raw_data.iloc[:, dossier_ref_col] == dossier_ref)
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
            d for v in self.raw_data.loc[stuk_mask, ColumnName.OPENINGSDATUM.value]
            if is_valid(s := str(v)) and (d := parse_date(s)) is not None
        ]
        stuk_closings = [
            d for v in self.raw_data.loc[stuk_mask, ColumnName.SLUITINGSDATUM.value]
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
