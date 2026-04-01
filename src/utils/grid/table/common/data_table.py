from enum import Enum

from pandas import DataFrame
from PySide6 import QtCore, QtGui

from src.utils.base_object import ApplicationMixin
from src.utils.constants import ColumnName
from src.utils.data_objects.sip import SIP


class CellColor(Enum):
    RED = QtGui.QBrush(QtGui.QColor(255, 0, 0))
    YELLOW = QtGui.QBrush(QtGui.QColor(255, 255, 0))
    GREY = QtGui.QBrush(QtGui.QColor(230, 230, 230))


class MarkingSource(Enum):
    CELL = "cell"
    WIDE = "wide"


class DataTable(QtCore.QAbstractTableModel, ApplicationMixin):
    def __init__(self, sip: SIP, editable: bool = True) -> None:
        super().__init__()

        self.sip = sip
        self.raw_data: DataFrame = self.sip.grid_data.data_as_df
        self.editable = editable

        self.markings: dict[tuple[int, int, MarkingSource], tuple[CellColor, str]] = {}
        self.should_filter_name_column: bool = False

    def data_index(self, index) -> tuple[int, int]:
        return self.raw_data.index[index.row()], index.column()

    def rowCount(self, parent=None) -> int:
        return self.raw_data.shape[0]

    def columnCount(self, parent=None) -> int:
        return self.raw_data.shape[1]

    # Getting of data or cell formatting based on index and role
    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole) -> str | QtGui.QBrush | None:
        if not index.isValid():
            return

        if role in (QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole):
            value = self.raw_data.iloc[index.row(), index.column()]

            if (
                self.should_filter_name_column
                and ColumnName.NAAM.value in self.raw_data.columns
                and index.column() == self.raw_data.columns.get_loc(ColumnName.NAAM.value)
            ):
                value, *_ = value.rsplit(".", 1)

            return value

        marking = self._resolve_marking(index)

        if not marking:
            if not self.editable and role == QtCore.Qt.ItemDataRole.BackgroundRole:
                return CellColor.GREY.value

            return

        color, tooltip = marking

        if role == QtCore.Qt.ItemDataRole.BackgroundRole and color:
            return color.value

        if role == QtCore.Qt.ItemDataRole.ToolTipRole and tooltip:
            return tooltip

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return str(self.raw_data.columns[section])

            if orientation == QtCore.Qt.Orientation.Vertical:
                return str(self.raw_data.index[section])

    def _resolve_marking(self, index) -> tuple[CellColor, str] | None:
        row, col = self.data_index(index)
        wide = self.markings.get((row, col, MarkingSource.WIDE))

        if wide:
            return wide

        return self.markings.get((row, col, MarkingSource.CELL))

    def flags(self, index):
        base_flags = QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled

        if not self.editable:
            return base_flags

        marking = self._resolve_marking(index)

        if marking and marking[0] in (CellColor.YELLOW, CellColor.GREY):
            return base_flags

        return base_flags | QtCore.Qt.ItemFlag.ItemIsEditable

    def disable_column(self, column_name: str, tooltip: str = "") -> "DataTable":
        col = self.raw_data.columns.get_loc(column_name)

        self.markings.update({(row, col, MarkingSource.CELL): (CellColor.GREY, tooltip) for row in self.raw_data.index})

        return self

    def unmark_cell(self, index, source: MarkingSource = MarkingSource.CELL) -> None:
        row, col = self.data_index(index)
        key = (row, col, source)

        if key in self.markings:
            del self.markings[key]

    def mark_cell(
        self, index, source: MarkingSource = MarkingSource.CELL, warning: bool = False, tooltip: str = ""
    ) -> None:
        row, col = self.data_index(index)
        color = CellColor.YELLOW if warning else CellColor.RED

        self.markings[(row, col, source)] = (color, tooltip)

    def shift_markings_for_insert(self, insert_col: int) -> None:
        updated: dict[tuple[int, int, MarkingSource], tuple[CellColor, str]] = {}

        for (row, col, source), value in self.markings.items():
            if col >= insert_col:
                updated[(row, col + 1, source)] = value
            else:
                updated[(row, col, source)] = value

        self.markings = updated

    def filter_name_column(self, active: bool) -> None:
        self.should_filter_name_column = active

        if ColumnName.NAAM.value not in self.raw_data.columns:
            return

        name_column = self.raw_data.columns.get_loc(ColumnName.NAAM.value)

        self.dataChanged.emit(
            self.index(0, name_column),
            self.index(self.rowCount() - 1, name_column),
        )

    @property
    def has_bad_rows(self) -> bool:
        return any(marking[0] == CellColor.RED for marking in self.markings.values())

    @property
    def bad_rows(self) -> list[int]:
        return list(set(row for (row, _, __), marking in self.markings.items() if marking[0] == CellColor.RED))
