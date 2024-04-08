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
        self._data = data
        self._create_sip_button = create_sip_button
        self.date_start, self.date_end = date_range

        self.colors = dict()

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
            color = self.colors.get((index.row(), index.column()))

            if color:
                return color.value

        elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
            color = self.colors.get((index.row(), index.column()))

            if color:
                # NOTE: "Naam"
                if index.column() == 4:
                    return "Een dossier moet verplicht een naam hebben"

                # NOTE: "Openingsdatum" en "Sluitingsdatum"
                elif index.column() in (8, 9):
                    return "Datum moet in formaat YYYY-MM-DD zijn, en is verplicht voor dossiers"

    def get_data(self):
        return self._data

    def name_data_check(self, value: str, row: int, col: int) -> None:
        # If invalid, set red
        if value == "" and self._data.iloc[row]["Type"] == "dossier":
            self.colors[(row, col)] = Color.RED
        elif (row, col) in self.colors:
            del self.colors[(row, col)]

    def _date_invalid_check(self, date: datetime) -> bool:
        if date > datetime.now() and date.year != 9999:
            return True

        if self.date_start is not None and date < self.date_start:
            return True

        if self.date_end is not None and date > self.date_end:
            return True

        return False

    def date_data_check(self, value: str, row: int, col: int) -> None:
        # Returns True in case we need to update the UI
        invalid = False

        # Try to get the date from the string
        try:
            date = datetime.strptime(value, "%Y-%m-%d")

            if self._date_invalid_check(date):
                invalid = True
        except ValueError:
            invalid = True

        # If it's an empty value at a "stuk", that's fine
        if self._data.iloc[row]["Type"] == "stuk" and value == "":
            invalid = False

        # Invalid, set to red if needed
        if invalid:
            self.colors[(row, col)] = Color.RED

        # Valid
        elif (row, col) in self.colors:
            del self.colors[(row, col)]

    def setData(self, index, value, role):
        if role == QtCore.Qt.ItemDataRole.EditRole:
            row, column = index.row(), index.column()

            self._data.iloc[row, column] = value

            if column in (4, 8, 9):
                # NOTE: "Naam"
                if column == 4:
                    self.name_data_check(value, row, column)

                # NOTE: "Openingsdatum" and "Sluitingsdatum"
                else:
                    self.date_data_check(value, row, column)

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

    def is_data_valid(self):
        # NOTE: we are using the colors dict to see if anything is marked invalid
        return not self.colors

    def get_invalid_name_rows(self) -> pd.DataFrame:
        return self._data.loc[
            (self._data["Type"] == "dossier") & (self._data["Naam"] == "")
        ]

    def get_invalid_opening_date_rows(self) -> pd.DataFrame:
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

        self._data["date_invalid_temp"] = self._data["Openingsdatum"].map(
            date_invalid_map
        )

        invalid_data = self._data.loc[
            ((self._data["Type"] == "dossier") & (self._data["Openingsdatum"] == ""))
            | (self._data["date_invalid_temp"])
        ].drop(["date_invalid_temp"], axis=1)
        self._data.drop(["date_invalid_temp"], axis=1, inplace=True)

        return invalid_data

    def get_invalid_closing_date_rows(self) -> pd.DataFrame:
        def date_invalid_map(value: str) -> bool:
            try:
                date = datetime.strptime(value, "%Y-%m-%d")

                if self._date_invalid_check(date):
                    return True
            except ValueError:
                return value != ""

            return False

        self._data["date_invalid_temp"] = self._data["Sluitingsdatum"].map(
            date_invalid_map
        )

        invalid_data = self._data.loc[
            ((self._data["Type"] == "dossier") & (self._data["Sluitingsdatum"] == ""))
            | (self._data["date_invalid_temp"])
        ].drop(["date_invalid_temp"], axis=1)
        self._data.drop(["date_invalid_temp"], axis=1, inplace=True)

        return invalid_data

    def sort(self, col, order):
        self.layoutAboutToBeChanged.emit()
        self._data = self._data.sort_values(
            self._data.columns[col], ascending=order == QtCore.Qt.AscendingOrder
        )
        self.layoutChanged.emit()
