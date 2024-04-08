from PySide6 import QtWidgets, QtGui, QtCore
import pandas as pd

from datetime import datetime
from enum import Enum
import math


class Color(Enum):
    RED = QtGui.QBrush(QtGui.QColor(255, 0, 0))


class PandasModel(QtCore.QAbstractTableModel):
    def __init__(self, data, create_sip_button, date_range):
        super().__init__()
        self._data = data.fillna("").astype(str).convert_dtypes()
        self._create_sip_button = create_sip_button
        self.date_start, self.date_end = date_range

        self.colors = dict()
        self.tooltips = dict()

        # NOTE: we basically take all the existing data
        # And act as if we just entered it
        # We do this so the checks will be run on the data automatically
        self._trigger_fill_data()

    def rowCount(self, *index):
        return self._data.shape[0]

    def columnCount(self, *index):
        return self._data.shape[1]

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return

        if (
            role == QtCore.Qt.ItemDataRole.DisplayRole
            or role == QtCore.Qt.ItemDataRole.EditRole
        ):
            value = self._data.iloc[index.row(), index.column()]

            return str(value)

        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            color = self.colors.get((self._data.index[index.row()], index.column()))

            if color:
                return color.value

        elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
            tooltip = self.tooltips.get((self._data.index[index.row()], index.column()))

            if tooltip:
                return tooltip

    def setData(self, index, value, role):
        if not index.isValid():
            return

        if role == QtCore.Qt.ItemDataRole.EditRole:
            row, column = index.row(), index.column()

            self._data.iloc[row, column] = value

            # NOTE: "Naam"
            if column == self._data.columns.get_loc("Naam"):
                self._name_data_check(value, row, column)

            # NOTE: "Openingsdatum" and "Sluitingsdatum"
            elif column in (
                self._data.columns.get_loc("Openingsdatum"),
                self._data.columns.get_loc("Sluitingsdatum"),
            ):
                self._date_data_check(
                    value, row, column, is_stuk=self._data.iloc[row]["Type"] == "stuk"
                )

            if self.is_data_valid():
                self._create_sip_button.setEnabled(True)
            else:
                self._create_sip_button.setEnabled(False)

            return True

        return False

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return str(self._data.columns[section])

            if orientation == QtCore.Qt.Orientation.Vertical:
                return str(self._data.index[section])

    def flags(self, index):
        if index.column() < 3:
            return QtCore.Qt.ItemFlag.ItemIsSelectable

        return (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            # | QtCore.Qt.ItemFlag.ItemsetEnabled
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsEditable
        )

    def sort(self, col, order):
        self.layoutAboutToBeChanged.emit()
        self._data = self._data.sort_values(
            self._data.columns[col], ascending=order == QtCore.Qt.AscendingOrder
        )
        self.layoutChanged.emit()

    def get_data(self):
        return self._data

    def is_data_valid(self):
        # NOTE: we are using the colors dict to see if anything is marked invalid
        return not self.colors

    # Utils
    def _trigger_fill_data(self) -> None:
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                index = self.index(r, c)
                value = self._data.iloc[index.row(), index.column()]

                self.setData(
                    index=index, value=value, role=QtCore.Qt.ItemDataRole.EditRole
                )

    def _date_invalid_check(self, date: datetime) -> str:
        if date > datetime.now() and date.year != 9999:
            return "Datum mag niet in de toekomst zijn"

        if self.date_start is not None and date < self.date_start:
            return "Datum mag niet voor de start-datum van de serie zijn"

        if self.date_end is not None and date > self.date_end:
            return "Datum mag niet na de eind-datum van de serie zijn"

    # Marking and unmarking of cells
    def _mark_bad_cell(
        self, row: int, col: int, color: Color = Color.RED, tooltip: str = None
    ) -> None:
        self.colors[(row, col)] = color

        if tooltip is not None:
            self.tooltips[(row, col)] = tooltip

    def _unmark_bad_cell(self, row: int, col: int) -> None:
        if (row, col) in self.colors:
            del self.colors[(row, col)]

        if (row, col) in self.tooltips:
            del self.tooltips[(row, col)]

    def _mark_name_cell(self, row: int) -> None:
        col = self._data.columns.get_loc("Naam")

        self._mark_bad_cell(
            row=row, col=col, tooltip="Een dossier moet verplicht een naam hebben"
        )

    def _mark_date_cell(self, row: int, col: int, tooltip: str) -> None:
        self._mark_bad_cell(row=row, col=col, tooltip=tooltip)

    # Checks
    def _name_data_check(self, value: str, row: int, col: int) -> None:
        if value == "" and self._data.iloc[row]["Type"] == "dossier":
            self._mark_name_cell(row=row)
        else:
            self._unmark_bad_cell(row=row, col=col)

    def _date_data_check(self, value: str, row: int, col: int, is_stuk: bool):
        # If it's an empty value at a "stuk", that's fine
        if is_stuk and value == "":
            self._unmark_bad_cell(row=row, col=col)
            return

        # Try to get the date from the string
        try:
            date = datetime.strptime(value, "%Y-%m-%d")

            if (tooltip := self._date_invalid_check(date)) is not None:
                self._mark_bad_cell(row=row, col=col, tooltip=tooltip)
                return

        except ValueError:
            self._mark_bad_cell(
                row=row, col=col, tooltip="Datum moet in het formaat YYYY-MM-DD zijn"
            )
            return

        # Everything checks out
        self._unmark_bad_cell(row=row, col=col)

    # Large scale checks
    def _get_invalid_name_rows(self) -> pd.DataFrame:
        return self._data.loc[
            (self._data["Type"] == "dossier") & (self._data["Naam"] == "")
        ]

    def _get_invalid_date_rows(self, column: str) -> pd.DataFrame:
        def date_invalid_map(value: str) -> bool:
            if isinstance(value, float) and math.isnan(value):
                return False

            try:
                date = datetime.strptime(value, "%Y-%m-%d")

                if self._date_invalid_check(date):
                    return True
            except ValueError:
                return value != ""

            return False

        self._data["date_invalid_temp"] = self._data[column].map(date_invalid_map)

        invalid_data = self._data.loc[
            ((self._data["Type"] == "dossier") & (self._data[column] == ""))
            | (self._data["date_invalid_temp"])
        ].drop(["date_invalid_temp"], axis=1)
        self._data.drop(["date_invalid_temp"], axis=1, inplace=True)

        return invalid_data

    def _get_invalid_opening_date_rows(self) -> pd.DataFrame:
        return self._get_invalid_date_rows("Openingsdatum")

    def _get_invalid_closing_date_rows(self) -> pd.DataFrame:
        return self._get_invalid_date_rows("Sluitingsdatum")

    def mark_invalid_rows(self):
        for index in self.get_invalid_name_rows().index:
            # Column 4 is "Naam"
            self.colors[(index, 4)] = Color.RED

        for index in self.get_invalid_opening_date_rows().index:
            # Column 8 is "Openingsdatum"
            self.colors[(index, 8)] = Color.RED

        for index in self.get_invalid_closing_date_rows().index:
            # Column 9 is "Sluitingsdatum"
            self.colors[(index, 9)] = Color.RED
