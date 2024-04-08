from PySide6 import QtWidgets, QtGui, QtCore
import pandas as pd
import numpy as np

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

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
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
                is_stuk = self._data.iloc[row]["Type"] == "stuk"

                valid_date = self._date_data_check(value, row, column, is_stuk=is_stuk)

                if valid_date and is_stuk:
                    self._update_dossier_date_range(
                        dossier_ref=self._data.iloc[row]["DossierRef"], column=column
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

                self.setData(index=index, value=value)

    def _proper_date_format(self, date_str: str) -> datetime:
        # Returns the date if valid, otherwise returns None
        # Format needs to be "%Y-%m-%d"
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass

    def _date_invalid_check(self, date: datetime) -> str:
        if date > datetime.now() and date.year != 9999:
            return "Datum mag niet in de toekomst zijn"

        if self.date_start is not None and date < self.date_start:
            return "Datum mag niet voor de start-datum van de serie zijn"

        if self.date_end is not None and date > self.date_end:
            return "Datum mag niet na de eind-datum van de serie zijn"

    def _get_date_values_for_dossier_ref(self, dossier_ref: str, column: str) -> list:
        files = self._data.loc[
            (self._data["Type"] == "stuk") & (self._data["DossierRef"] == dossier_ref)
        ]

        # TODO: find a way to do this vectorized
        return [
            d
            for d in files[column]
            if (date := self._proper_date_format(d)) is not None
            and self._date_invalid_check(date) is None
        ]

    def _update_dossier_date_range(self, dossier_ref: str, column: str) -> None:
        dossier = self._data.loc[
            (self._data["Type"] == "dossier")
            & (self._data["DossierRef"] == dossier_ref)
        ]

        opening_dates = self._get_date_values_for_dossier_ref(
            dossier_ref=dossier_ref, column="Openingsdatum"
        )
        closing_dates = self._get_date_values_for_dossier_ref(
            dossier_ref=dossier_ref, column="Sluitingsdatum"
        )

        row = dossier.index.to_list()[0]
        opening_col = self._data.columns.get_loc("Openingsdatum")
        closing_col = self._data.columns.get_loc("Sluitingsdatum")

        # Only change the values if we have something useful to change it in to
        if column == opening_col and opening_dates:
            new_opening = min(opening_dates)

            # Only change if the openingsdate is actually lower
            if dossier["Openingsdatum"].to_list()[0] < new_opening:
                return

            self.setData(self.index(row, opening_col), value=new_opening)
        elif column == closing_col and closing_dates:
            new_closing = max(closing_dates)

            # Only change if the closingdate is actually higher
            if dossier["Sluitingsdatum"].to_list()[0] > new_closing:
                return

            self.setData(self.index(row, closing_col), value=new_closing)

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
    def _name_data_check(self, value: str, row: int, col: int) -> bool:
        # Return True if cell was ok, otherwise return False
        if value == "" and self._data.iloc[row]["Type"] == "dossier":
            self._mark_name_cell(row=row)
            return False

        self._unmark_bad_cell(row=row, col=col)
        return True

    def _date_data_check(
        self, value: str, row: int, col: int, is_stuk: bool, re_evaluation=False
    ) -> bool:
        # Return True if cell was ok, otherwise return False

        data_row = self._data.iloc[[row]]

        opening_date = data_row["Openingsdatum"].to_list()[0]
        closing_date = data_row["Sluitingsdatum"].to_list()[0]

        opening_col = self._data.columns.get_loc("Openingsdatum")
        closing_col = self._data.columns.get_loc("Sluitingsdatum")

        # If it's an empty value at a "stuk", that's fine
        if is_stuk and value == "":
            self._unmark_bad_cell(row=row, col=col)
            return True

        date = self._proper_date_format(value)

        # Date needs to be in the correct format
        if date is None:
            self._mark_bad_cell(
                row=row, col=col, tooltip="Datum moet in het formaat YYYY-MM-DD zijn"
            )
            return False

        # Date needs to be valid (in past and in series range)
        if (tooltip := self._date_invalid_check(date)) is not None:
            self._mark_bad_cell(row=row, col=col, tooltip=tooltip)
            return False

        # Openingdate cannot be after closingdate
        if opening_date and closing_date and opening_date > closing_date:
            self._mark_date_cell(
                row=row,
                col=opening_col,
                tooltip="De openingsdatum kan niet na de sluitingsdatum zijn",
            )
            self._mark_date_cell(
                row=row,
                col=closing_col,
                tooltip="De sluitingsdatum kan niet voor de openingsdatum zijn",
            )

            return False

        if not is_stuk:
            # The openings and closing dates need to match the files
            dossier = data_row
            dossier_ref = dossier["DossierRef"].to_list()[0]

            opening_dates = self._get_date_values_for_dossier_ref(
                dossier_ref=dossier_ref, column="Openingsdatum"
            )
            closing_dates = self._get_date_values_for_dossier_ref(
                dossier_ref=dossier_ref, column="Sluitingsdatum"
            )

            dossier_opening = dossier["Openingsdatum"].to_list()[0]
            dossier_closing = dossier["Sluitingsdatum"].to_list()[0]

            if (
                col == opening_col
                and opening_dates
                and dossier_opening > min(opening_dates)
            ):
                self._mark_date_cell(
                    row=row,
                    col=col,
                    tooltip="De openingsdatum van het dossier kan niet later zijn dan de openingsdatum van een stuk",
                )
                return False

            elif (
                col == closing_col
                and closing_dates
                and dossier_closing < max(closing_dates)
            ):
                self._mark_date_cell(
                    row=row,
                    col=col,
                    tooltip="De sluitingsdatum van het dossier kan niet vroeger zijn dan de sluitingsdatum van een stuk",
                )
                return False

        # Everything checks out
        self._unmark_bad_cell(row=row, col=col)

        # Re-evaluate if we are unmarking a cell, to make sure the linked cell is proparly adressed
        if not re_evaluation:
            if col == opening_col:
                self._date_data_check(
                    value=value,
                    row=row,
                    col=closing_col,
                    is_stuk=is_stuk,
                    re_evaluation=True,
                )
            elif col == closing_col:
                self._date_data_check(
                    value=value,
                    row=row,
                    col=opening_col,
                    is_stuk=is_stuk,
                    re_evaluation=True,
                )

        # Re-evaluate the dossier_dates
        if not re_evaluation and is_stuk:
            dossier_ref = data_row["DossierRef"].to_list()[0]

            dossier = self._data.loc[
                (self._data["Type"] == "dossier")
                & (self._data["DossierRef"] == dossier_ref)
            ]

            dossier_row = dossier.index.to_list()[0]
            dossier_opening = dossier["Openingsdatum"].to_list()[0]
            dossier_closing = dossier["Sluitingsdatum"].to_list()[0]

            self._date_data_check(
                value=dossier_opening,
                row=dossier_row,
                col=opening_col,
                is_stuk=False,
                re_evaluation=True,
            )
            self._date_data_check(
                value=dossier_closing,
                row=dossier_row,
                col=closing_col,
                is_stuk=False,
                re_evaluation=True,
            )

        # Make sure we update the values again where needed
        if re_evaluation and is_stuk:
            dossier_ref = data_row["DossierRef"].to_list()[0]

            self._update_dossier_date_range(dossier_ref=dossier_ref, column=col)

        return True
