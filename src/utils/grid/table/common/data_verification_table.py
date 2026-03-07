from typing import Iterator

from PySide6 import QtCore

from src.utils.constants import ColumnName
from src.utils.data_objects.sip import SIP
from src.utils.grid.table.common.data_table import DataTable, MarkingSource
from src.utils.grid.checks import BaseCheck, CellIssue, RRNCheck
from src.utils.workers.worker import Worker

ValidationResult = tuple[
    QtCore.QModelIndex,
    str,
    list[CellIssue],
    MarkingSource
]


class CommonDataVerificationTable(DataTable):
    COLUMN_VALIDATORS: dict[ColumnName, BaseCheck] = {
        ColumnName.ID_RIJKSREGISTERNUMMER: RRNCheck(),
    }

    def __init__(self, sip: SIP) -> None:
        super().__init__(sip)

        self._active_workers: list[tuple[Worker, QtCore.QThread]] = []

    def _sanitize_value(self, value: str) -> str:
        return str(value).encode(encoding="utf-8", errors="replace").decode("utf-8")

    def _run_validators(self, index: QtCore.QModelIndex, value: str) -> Iterator[ValidationResult]:
        column_name = self.raw_data.columns[index.column()]
        column = ColumnName(column_name) if column_name in ColumnName else None
        check = self.COLUMN_VALIDATORS.get(column) if column else None

        if check is None:
            return

        wide_issues = check.check_wide(self.raw_data, index, value)
        yield (index, value, wide_issues, MarkingSource.WIDE)

        if any(i == index for i, _ in wide_issues):
            return

        cell_result = check.check_cell(index, value)

        if isinstance(cell_result, tuple):
            yield (index, value, [cell_result], MarkingSource.CELL)
            return

        value = cell_result
        yield (index, value, [], MarkingSource.CELL)

    def _apply_validation_result(self, result: ValidationResult) -> None:
        index, value, issues, source = result

        self.unmark_cell(index, source)

        if issues:
            for issue_index, tooltip in issues:
                self.mark_cell(issue_index, source=source, tooltip=tooltip)

        self.raw_data.iat[index.row(), index.column()] = value
        self.dataChanged.emit(index, index)

    def _validate_in_background(self, index: QtCore.QModelIndex, value: str) -> None:
        worker = Worker(
            function=lambda: self._run_validators(index, value),
            is_generator=True,
        )
        thread = QtCore.QThread()

        worker.moveToThread(thread)
        self._active_workers.append((worker, thread))

        thread.started.connect(worker.run)
        worker.result_ready_signal.connect(self._apply_validation_result)

        worker.finished_signal.connect(thread.quit)
        worker.finished_signal.connect(thread.deleteLater)
        worker.finished_signal.connect(lambda: self._active_workers.remove((worker, thread)))

        thread.start()

    def setData(self, index, value: str, role=QtCore.Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role != QtCore.Qt.ItemDataRole.EditRole:
            return False

        value = self._sanitize_value(value)

        self.raw_data.iat[index.row(), index.column()] = value
        self.dataChanged.emit(index, index)

        self._validate_in_background(index, value)

        return True
