from PySide6 import QtGui, QtCore
import pandas as pd
import os

from datetime import datetime
from enum import Enum


class Color(Enum):
    RED = QtGui.QBrush(QtGui.QColor(255, 0, 0))
    YELLOW = QtGui.QBrush(QtGui.QColor(255, 255, 0))
    GREY = QtGui.QBrush(QtGui.QColor(230, 230, 230))


class PandasModel(QtCore.QAbstractTableModel):
    bad_rows_changed: QtCore.Signal = QtCore.Signal(
        *(int, bool), arguments=["row", "is_bad"]
    )
    sort_triggered: QtCore.Signal = QtCore.Signal()

    def __init__(
        self,
        data: pd.DataFrame,
        create_sip_button,
        date_range: tuple,
        sip_folder_structure: dict,
    ):
        super().__init__()
        self._data = data.fillna("").astype(str).convert_dtypes()
        self._create_sip_button = create_sip_button
        self.date_start, self.date_end = date_range
        self.sip_folder_structure = sip_folder_structure

        self.colors = dict()
        self.tooltips = dict()

        self.should_filter_name_column = False

        # Warning rows
        self._check_empty_rows()

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

        row, col = index.row(), index.column()
        data_row = self._data.index[row]
        value = self._data.iloc[index.row(), index.column()]

        if (
            role == QtCore.Qt.ItemDataRole.DisplayRole
            or role == QtCore.Qt.ItemDataRole.EditRole
        ):
            # If the filter is active, and we are on the name column, filter the name
            if (
                self.should_filter_name_column
                and self._data.columns.get_loc("Naam") == col
            ):
                value, *_ = value.rsplit(".", 1)

            return value

        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            color = self.colors.get((data_row, col))

            if color:
                return color.value

            # Mark first 3 columns as grey, only if no other color is assigned
            if col < 3:
                return Color.GREY.value

        elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
            tooltip = self.tooltips.get((data_row, col))

            if tooltip:
                return tooltip

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        row, column = index.row(), index.column()

        # Do not allow editing of warning rows
        if self.colors.get((self._data.index[row], column)) == Color.YELLOW:
            return False

        if role == QtCore.Qt.ItemDataRole.EditRole:
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
            return (
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )

        if (
            self.colors.get((self._data.index[index.row()], index.column()))
            == Color.YELLOW
        ):
            return (
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )

        return (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsEditable
        )

    def sort(self, col, order):
        self.layoutAboutToBeChanged.emit()
        self._data = self._data.sort_values(
            self._data.columns[col], ascending=order == QtCore.Qt.AscendingOrder
        )
        self.layoutChanged.emit()
        self.sort_triggered.emit()

    def get_data(self):
        return self._data

    def get_bad_rows(self) -> set:
        return set(
            row
            for (row, _), color in self.colors.items()
            if color in (Color.RED, Color.YELLOW)
        )

    def is_data_valid(self):
        # NOTE: we are using the colors dict to see if anything is marked invalid
        return not any(c == Color.RED for c in self.colors.values())

    # Utils
    def _check_empty_rows(self) -> None:
        # Mark rows with "Type" == "geen" as empty
        empty_rows = self._data.loc[self._data["Type"] == "geen"]

        for row, row_values in empty_rows.iterrows():
            path_in_sip = row_values["Path in SIP"]
            real_path = [
                p["path"]
                for p in self.sip_folder_structure.values()
                if p["Path in SIP"] == path_in_sip
            ][0]

            is_dossier = not "/" in path_in_sip

            if is_dossier:
                self._mark_warning_row(
                    row, tooltip="Lege dossiers worden niet meegenomen in de SIP"
                )
                continue

            if os.path.isdir(real_path):
                self._mark_warning_row(
                    row, tooltip="Lege folders worden niet meegenomen in de SIP"
                )
                continue

            if os.path.isfile(real_path):
                self._mark_warning_row(
                    row, tooltip="Lege stukken worden niet meegenomen in de SIP"
                )
                continue

            self._mark_warning_row(
                row,
                tooltip="Onbekend probleem met rij, deze wordt niet meegenomen in de SIP",
            )

    def _trigger_fill_data(self) -> None:
        self._vectorized_name_data_check()
        self._vectorized_date_data_check()

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
            return "Datum moet binnen de serie-datumrange vallen"

        if self.date_end is not None and date > self.date_end:
            return "Datum moet binnen de serie-datumrange vallen"

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
        data_row = self._data.index[row]

        self.colors[(data_row, col)] = color

        if tooltip is not None:
            self.tooltips[(data_row, col)] = tooltip

        if color == Color.RED:
            self.bad_rows_changed.emit(row, True)

    def _mark_warning_row(
        self, row: int, color: Color = Color.YELLOW, tooltip: str = None
    ) -> None:
        for c in range(self.columnCount()):
            self._mark_bad_cell(row=row, col=c, color=color, tooltip=tooltip)

    def _unmark_bad_cell(self, row: int, col: int) -> None:
        data_row = self._data.index[row]

        if (data_row, col) in self.colors:
            del self.colors[(data_row, col)]

            # We have cleared the row
            if data_row not in self.get_bad_rows():
                self.bad_rows_changed.emit(row, False)

        if (data_row, col) in self.tooltips:
            del self.tooltips[(data_row, col)]

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
                tooltip="Openingsdatum kan niet na de sluitingsdatum zijn",
            )
            self._mark_date_cell(
                row=row,
                col=closing_col,
                tooltip="Sluitingsdatum kan niet voor de openingsdatum zijn",
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
                    value=closing_date,
                    row=row,
                    col=closing_col,
                    is_stuk=is_stuk,
                    re_evaluation=True,
                )
            elif col == closing_col:
                self._date_data_check(
                    value=opening_date,
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

            self._update_dossier_date_range(dossier_ref=dossier_ref, column=col)

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

        return True

    # Vectorized checks
    def _vectorized_name_data_check(self) -> None:
        mask = self._data.loc[self._data.Type == "dossier"].Naam.apply(
            lambda n: n == ""
        )
        bad_rows = self._data.loc[self._data.Type == "dossier"].Naam[mask]

        for row, _ in bad_rows.items():
            self._mark_name_cell(row=row)

    def _vectorized_date_data_check(self) -> None:
        opening_col, closing_col = self._data.columns.get_loc(
            "Openingsdatum"
        ), self._data.columns.get_loc("Sluitingsdatum")

        df = self._data[["Openingsdatum", "Sluitingsdatum", "Type"]]

        # Empty date
        empty_dossier_date_mask = df.loc[df.Type == "dossier"].apply(lambda n: n == "")

        # Date mapping
        non_empty_date_mask = df.apply(lambda n: n != "")
        non_empty_opening = df.Openingsdatum[non_empty_date_mask.Openingsdatum]
        non_empty_closing = df.Sluitingsdatum[non_empty_date_mask.Sluitingsdatum]

        opening_date_mapping = pd.to_datetime(
            non_empty_opening,
            format="%Y-%m-%d",
            errors="coerce",
        )
        closing_date_mapping = pd.to_datetime(
            non_empty_closing,
            format="%Y-%m-%d",
            errors="coerce",
        )

        # Bad format date
        bad_opening_format_mask = opening_date_mapping.isnull()
        bad_closing_format_mask = closing_date_mapping.isnull()

        # Date in future
        today = datetime.today()

        opening_future_mask = opening_date_mapping > today
        closing_future_mask = closing_date_mapping > today

        # Between series range
        opening_before_start_range_mask = (
            opening_date_mapping < self.date_start
            if self.date_start is not None
            else None
        )
        closing_before_start_range_mask = (
            closing_date_mapping < self.date_start
            if self.date_start is not None
            else None
        )
        opening_after_end_range_mask = (
            opening_date_mapping > self.date_end if self.date_end is not None else None
        )
        closing_after_end_range_mask = (
            closing_date_mapping > self.date_end if self.date_end is not None else None
        )

        # Closing before opening
        closing_before_opening_mask = closing_date_mapping < opening_date_mapping

        # Apply all mappings
        for row, _ in (
            df.loc[df.Type == "dossier"]
            .Openingsdatum[empty_dossier_date_mask.Openingsdatum]
            .items()
        ):
            self._mark_bad_cell(
                row=row,
                col=opening_col,
                tooltip="Openingsdatum mag niet leeg zijn voor dossiers",
            )
        for row, _ in (
            df.loc[df.Type == "dossier"]
            .Sluitingsdatum[empty_dossier_date_mask.Sluitingsdatum]
            .items()
        ):
            self._mark_bad_cell(
                row=row,
                col=closing_col,
                tooltip="Sluitingsdatum mag niet leeg zijn voor dossiers",
            )

        for row, _ in non_empty_opening[bad_opening_format_mask].items():
            self._mark_bad_cell(
                row=row,
                col=opening_col,
                tooltip="Openingsdatum moet in het formaat YYYY-MM-DD zijn",
            )
        for row, _ in non_empty_closing[bad_closing_format_mask].items():
            self._mark_bad_cell(
                row=row,
                col=closing_col,
                tooltip="Sluitingsdatum moet in het formaat YYYY-MM-DD zijn",
            )

        for row, _ in non_empty_opening[opening_future_mask].items():
            self._mark_bad_cell(
                row=row,
                col=opening_col,
                tooltip="Datum mag niet in de toekomst zijn",
            )
        for row, _ in non_empty_closing[closing_future_mask].items():
            self._mark_bad_cell(
                row=row,
                col=closing_col,
                tooltip="Datum mag niet in de toekomst zijn",
            )

        if opening_before_start_range_mask is not None:
            for row, _ in non_empty_opening[opening_before_start_range_mask].items():
                self._mark_bad_cell(
                    row=row,
                    col=opening_col,
                    tooltip="Datum moet binnen de serie-datumrange vallen",
                )
        if opening_after_end_range_mask is not None:
            for row, _ in non_empty_opening[opening_after_end_range_mask].items():
                self._mark_bad_cell(
                    row=row,
                    col=opening_col,
                    tooltip="Datum moet binnen de serie-datumrange vallen",
                )
        if closing_before_start_range_mask is not None:
            for row, _ in non_empty_closing[closing_before_start_range_mask].items():
                self._mark_bad_cell(
                    row=row,
                    col=closing_col,
                    tooltip="Datum moet binnen de serie-datumrange vallen",
                )
        if closing_after_end_range_mask is not None:
            for row, _ in non_empty_closing[closing_after_end_range_mask].items():
                self._mark_bad_cell(
                    row=row,
                    col=closing_col,
                    tooltip="Datum moet binnen de serie-datumrange vallen",
                )

        for row, _ in non_empty_opening[closing_before_opening_mask].items():
            self._mark_date_cell(
                row=row,
                col=opening_col,
                tooltip="Openingsdatum kan niet na de sluitingsdatum zijn",
            )
            self._mark_date_cell(
                row=row,
                col=closing_col,
                tooltip="Sluitingsdatum kan niet voor de openingsdatum zijn",
            )

    # Filters
    def filter_name_column(self, active: bool) -> None:
        # We just set the value here, the filtering happens when showing data
        self.should_filter_name_column = active

        name_column = self._data.columns.get_loc("Naam")

        self.dataChanged.emit(
            self.index(0, name_column),
            self.index(self.rowCount(), name_column),
        )
