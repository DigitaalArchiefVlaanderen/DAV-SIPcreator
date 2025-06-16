from PySide6 import QtCore
import pandas as pd
import os
import re

from datetime import datetime

from .tablemodel import TableModel, CellColor


class PandasModel(TableModel):
    bad_rows_changed: QtCore.Signal = QtCore.Signal(
        *(int, bool), arguments=["row", "is_bad"]
    )

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

        self.columns_to_disable: list[int] = [i for i, c in enumerate(self._data.columns) if c in ("Path in SIP", "Type", "DossierRef", "Analoog?")]

        self.should_filter_name_column = False

        # NOTE: we basically take all the existing data
        # And act as if we just entered it
        # We do this so the checks will be run on the data automatically
        self._trigger_fill_data()

    # Inherited methods
    def row_is_dossier(self, row: int) -> bool:
        return self._data.iloc[row]["Type"] == "dossier"

    def row_is_bad(self, row: int) -> bool:
        _id = self._data.index[row]

        return any(True for (row_id, _), color in self.colors.items() if row_id == _id and color in (CellColor.RED, CellColor.YELLOW))

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

            # Mark grey if not editable
            if QtCore.Qt.ItemFlag.ItemIsEditable.name not in self.flags(index).name:
                return CellColor.GREY.value

        elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
            tooltip = self.tooltips.get((data_row, col))

            if tooltip:
                return tooltip

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        if role == QtCore.Qt.ItemDataRole.EditRole:
            if QtCore.Qt.ItemFlag.ItemIsEditable.name not in self.flags(index).name:
                return False

        row, column = index.row(), index.column()
        old_value = self._data.iloc[row, column]

        if old_value == value:
            return False

        # Do not allow editing of warning rows
        if self.colors.get((self._data.index[row], column)) == CellColor.YELLOW:
            return False

        value = str(value).encode(encoding="utf-8", errors="replace").decode("utf-8")

        if role == QtCore.Qt.ItemDataRole.EditRole:
            self._data.iloc[row, column] = value

            # NOTE: "Naam"
            if column == self._data.columns.get_loc("Naam"):
                self._name_data_check(value, old_value, row, column)

            # NOTE: "Openingsdatum" and "Sluitingsdatum"
            elif column in (
                self._data.columns.get_loc("Openingsdatum"),
                self._data.columns.get_loc("Sluitingsdatum"),
            ):
                is_stuk = self._data.iloc[row]["Type"] == "stuk"

                self._date_data_check(row=row, is_stuk=is_stuk)
            elif column == self._data.columns.get_loc("ID_Rijksregisternummer"):
                new_value = self._rrn_check(value, row, column)

                if new_value != value:
                    return self.setData(index, new_value, role)
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
        if index.column() in self.columns_to_disable:
            return (
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )

        if (
            self.colors.get((self._data.index[index.row()], index.column()))
            == CellColor.YELLOW
        ):
            return (
                QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled
            )

        return (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsEditable
        )

    def get_data(self) -> pd.DataFrame:
        return self._data

    def get_bad_rows(self) -> set:
        return set(
            row
            for (row, _), color in self.colors.items()
            if color in (CellColor.RED, CellColor.YELLOW)
        )

    def is_data_valid(self):
        # NOTE: we are using the colors dict to see if anything is marked invalid
        return not any(c == CellColor.RED for c in self.colors.values())

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
        self.colors = dict()
        self.tooltips = dict()
        
        # Warning rows
        self._check_empty_rows()

        self._vectorized_name_data_check()
        self._vectorized_date_data_check()

        # NOTE: I do not want to write vectorized rrn checks
        rrn_col = self._data.columns.get_loc("ID_Rijksregisternummer")
        for r in range(self.rowCount()):
            data_row = self._data.index[r]

            if (data_row, rrn_col) in self.colors:
                continue

            self._rrn_check(
                value=self._data.iloc[r, rrn_col],
                row=r,
                col=rrn_col,
            )

    def _proper_date_format(self, date_str: str) -> datetime:
        # Returns the date if valid, otherwise returns None
        # Format needs to be "%Y-%m-%d"
        try:
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            pass

    def _date_invalid_check(self, date: datetime) -> str:
        if date is None:
            return

        if date > datetime.now() and date.year != 9999:
            return "Datum mag niet in de toekomst zijn"

        if self.date_start is not None and date < self.date_start:
            return "Datum moet binnen de serie-datumrange vallen"

        if self.date_end is not None and date > self.date_end:
            return "Datum moet binnen de serie-datumrange vallen"
        
    def _rrn_check(self, value: str, row: int, col: int) -> str:
        if value == "":
            self._unmark_bad_cell(row, col)
            return value

        # NOTE: we allow loose form matching, and will just set it correctly later
        loose_form_match = re.match(r"^\d{11}$", value)
        if loose_form_match:
            value = f"{value[:2]}.{value[2:4]}.{value[4:6]}-{value[6:9]}.{value[9:]}"
            
        strict_form_match = re.match(r"^\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2}$", value)

        if not strict_form_match:
            self._mark_bad_cell(row, col, CellColor.RED, "Rijksregisternummer moet van vorm xx.xx.xx-xxx.xx zijn, of 11 cijfers na elkaar zijn")
            return value
        
        # NOTE: check if the actual rrn is valid
        calc, control = value[:-2].replace(".", "").replace("-", ""), value[-2:]

        is_valid_check = lambda c: 97 - int(c) % 97 == int(control)

        # NOTE: for people born after 2000, add a 2 to the calc
        calc_before, calc_after = calc, f"2{calc}"

        if not is_valid_check(calc_before) and not is_valid_check(calc_after):
            self._mark_bad_cell(row, col, CellColor.RED, "Ingegeven rijksregisternummer is niet mogelijk")
            return value

        self._unmark_bad_cell(row, col)
        return value

    def _get_date_values_for_dossier_ref(self, dossier_ref: str, column: str) -> list[str]:
        files = self._data.loc[
            (self._data["Type"] == "stuk") & (self._data["DossierRef"] == dossier_ref)
        ]

        return [
            d
            for d in files[column]
            if (date := self._proper_date_format(d)) is not None
            and self._date_invalid_check(date) is None
        ]

    def _update_dossier_date_range(self, dossier_ref: str) -> None:
        def _opening():
            # Only change the values if we have something useful to change it in to
            if opening_dates:
                new_opening = min(opening_dates)

                current_value = dossier.iloc[0]["Openingsdatum"]
                current_date = self._proper_date_format(current_value)

                # If valid date
                if current_date is not None and not self._date_invalid_check(current_date):
                    # Only change if the openingsdate is actually lower
                    if current_value <= new_opening:
                        return

                self._data.iloc[row, opening_col] = new_opening
                index = self.index(row, opening_col)
                self.dataChanged.emit(index, index)

        def _closing():
            # Only change the values if we have something useful to change it in to
            if closing_dates:
                new_closing = max(closing_dates)

                current_value = dossier.iloc[0]["Sluitingsdatum"]
                current_date = self._proper_date_format(current_value)

                # If valid date
                if current_date is not None and not self._date_invalid_check(current_date):
                    # Only change if the closingdate is actually higher
                    if current_value >= new_closing:
                        return

                self._data.iloc[row, closing_col] = new_closing
                index = self.index(row, closing_col)
                self.dataChanged.emit(index, index)

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
        
        _opening()
        _closing()

    # Marking and unmarking of cells
    def _mark_bad_cell(
        self, row: int, col: int, color: CellColor = CellColor.RED, tooltip: str = None
    ) -> None:
        data_row = self._data.index[row]

        self.colors[(data_row, col)] = color

        if tooltip is not None:
            self.tooltips[(data_row, col)] = tooltip

        if color == CellColor.RED:
            self.bad_rows_changed.emit(row, True)

    def _mark_warning_row(
        self, row: int, color: CellColor = CellColor.YELLOW, tooltip: str = None
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

    def _mark_name_cell(self, row: int, tooltip: str) -> None:
        col = self._data.columns.get_loc("Naam")

        self._mark_bad_cell(
            row=row, col=col, tooltip=tooltip
        )

    def _mark_date_cell(self, row: int, col: int, tooltip: str) -> None:
        self._mark_bad_cell(row=row, col=col, tooltip=tooltip)

    # Checks
    def _name_data_check(self, value: str, old_value: str, row: int, col: int) -> bool:
        # Return True if cell was ok, otherwise return False
        # NOTE: check for old duplicates no longer being duplicates
        if old_value != "" and len((rows := self._data.index[(self._data.Type == "dossier") & (self._data.Naam == old_value)].tolist())) == 1:
            # NOTE: this will only be one row, but this is okay
            for r in rows:
                self._unmark_bad_cell(
                    row=r,
                    col=col
                )

        if value == "" and self._data.iloc[row]["Type"] == "dossier":
            self._mark_name_cell(row=row, tooltip="Een dossier moet verplicht een naam hebben")
            return False
        
        if len(value) > 255:
            self._mark_bad_cell(
                row=row, col=col, tooltip="Naam mag niet langer zijn dan 255 karakters"
            )
            return False

        # NOTE: check for new duplication
        if value != "" and len((rows := self._data.index[(self._data.Type == "dossier") & (self._data.Naam == value)].tolist())) > 1:
            for r in rows:
                self._mark_bad_cell(
                    row=r,
                    col=col,
                    tooltip="Naam veld moet uniek zijn"
                )

            return False

        self._unmark_bad_cell(row=row, col=col)
        return True

    def _individual_date_cell_checks(self, row: int, col: int, is_stuk: bool, value: str, date: datetime, tooltip: str) -> bool:
        # Returns if the value was ok or not
        if is_stuk and (value == "" or value is None):
            self._unmark_bad_cell(
                row=row,
                col=col
            )
            return True
        
        if date is None:
            self._mark_bad_cell(
                row=row,
                col=col,
                tooltip="Datum moet in het formaat YYYY-MM-DD en geldig zijn"
            )
            return False
        
        if tooltip is not None:
            self._mark_bad_cell(
                row=row,
                col=col,
                tooltip=tooltip
            )
            return False
        
        self._unmark_bad_cell(
            row=row,
            col=col
        )
        return True

    def _date_data_check(
        self, row: int, is_stuk: bool
    ) -> None:
        data_row = self._data.iloc[[row]]
        dossier_ref = data_row["DossierRef"].to_list()[0]

        # NOTE: if we have multiple, we only take the first (not optimal but fine)
        dossier_data_row = self._data.loc[
            (self._data["Type"] == "dossier")
            & (self._data["DossierRef"] == dossier_ref)
        ]
        dossier_row = dossier_data_row.index.to_list()[0]
        
        opening_col = self._data.columns.get_loc("Openingsdatum")
        closing_col = self._data.columns.get_loc("Sluitingsdatum")

        opening_date_value = data_row["Openingsdatum"].to_list()[0]
        closing_date_value = data_row["Sluitingsdatum"].to_list()[0]

        opening_date, closing_date = self._proper_date_format(opening_date_value), self._proper_date_format(closing_date_value)
        opening_tooltip, closing_tooltip = self._date_invalid_check(opening_date), self._date_invalid_check(closing_date)
        
        # NOTE: we start by individually checking opening, then closing
        is_opening_value_ok = self._individual_date_cell_checks(
            row=row,
            col=opening_col,
            is_stuk=is_stuk,
            value=opening_date_value,
            date=opening_date,
            tooltip=opening_tooltip
        )
        is_closing_value_ok = self._individual_date_cell_checks(
            row=row,
            col=closing_col,
            is_stuk=is_stuk,
            value=closing_date_value,
            date=closing_date,
            tooltip=closing_tooltip
        )

        # NOTE: do this check first, so bad order can still be displayed properly if needed
        # Check if the order is correct
        if opening_date is not None and closing_date is not None and opening_date > closing_date:
            if is_opening_value_ok:
                self._mark_bad_cell(
                    row=row,
                    col=opening_col,
                    tooltip="Openingsdatum kan niet na de sluitingsdatum zijn"
                )
            if is_closing_value_ok:
                self._mark_bad_cell(
                    row=row,
                    col=closing_col,
                    tooltip="Sluitingsdatum kan niet voor de openingsdatum zijn"
                )
            return
        
        # If we found an issue already, stop here
        if not is_opening_value_ok or not is_closing_value_ok:
            return

        # Dossier specific checks
        opening_date_values = self._get_date_values_for_dossier_ref(dossier_ref=dossier_ref, column="Openingsdatum")
        closing_date_values = self._get_date_values_for_dossier_ref(dossier_ref=dossier_ref, column="Sluitingsdatum")

        min_opening_date_value = None if not opening_date_values else min(opening_date_values)
        max_closing_date_value = None if not closing_date_values else max(closing_date_values)

        if not is_stuk:
            # NOTE: if we have no values to compare to, that's also okay
            # Check if the values are still ok given the values we just entered for this dossier
            if opening_date_values and opening_date_value > min_opening_date_value:
                self._mark_bad_cell(
                    row=dossier_row,
                    col=opening_col,
                    tooltip="De openingsdatum van het dossier kan niet later zijn dan de openingsdatum van een stuk"
                )
            if closing_date_values and closing_date_value < max_closing_date_value:
                self._mark_bad_cell(
                    row=dossier_row,
                    col=closing_col,
                    tooltip="De sluitingsdatum van het dossier kan niet vroeger zijn dan de sluitingsdatum van een stuk"
                )

            return
        
        # Stuk specific actions (update values of dossier if needed)
        if opening_date_values:
            dossier_opening_date_value = dossier_data_row["Openingsdatum"].to_list()[0]

            if dossier_opening_date_value > min_opening_date_value:
                self.setData(
                    self.index(
                        dossier_row,
                        opening_col,
                    ),
                    min_opening_date_value
                )
        if closing_date_values:
            dossier_closing_date_value = dossier_data_row["Sluitingsdatum"].to_list()[0]

            if dossier_closing_date_value < max_closing_date_value:
                self.setData(
                    self.index(
                        dossier_row,
                        closing_col
                    ),
                    max_closing_date_value
                )

    # Vectorized checks
    def _vectorized_name_data_check(self) -> None:
        # Empty name for dossiers
        mask = self._data.loc[self._data.Type == "dossier"].Naam.apply(
            lambda n: n == ""
        )
        empty_rows = self._data.loc[self._data.Type == "dossier"].Naam[mask]

        for row, _ in empty_rows.items():
            self._mark_name_cell(row=row, tooltip="Een dossier moet verplicht een naam hebben")

        # Duplicate names
        mask = self._data.loc[(self._data.Type == "dossier") & (self._data.Naam != "")].Naam.duplicated(keep=False)
        duplicate_rows = self._data.loc[(self._data.Type == "dossier") & (self._data.Naam != "")].Naam[mask]

        for row, _ in duplicate_rows.items():
            self._mark_name_cell(row=row, tooltip="Naam veld moet uniek zijn")

        # Max length 255
        long_rows = self._data[self._data.Naam.str.len() > 255].Naam

        for row, _ in long_rows.items():
            self._mark_name_cell(row=row, tooltip="Naam mag niet langer zijn dan 255 karakters")

    def _vectorized_date_data_check(self) -> None:
        opening_col, closing_col = self._data.columns.get_loc(
            "Openingsdatum"
        ), self._data.columns.get_loc("Sluitingsdatum")

        df = self._data[["Openingsdatum", "Sluitingsdatum", "Type"]]

        # Empty date
        empty_dossier_date_mask = df.loc[df.Type == "dossier"].apply(lambda n: n == "")

        # Date mapping
        opening_date_mapping = pd.to_datetime(
            df[~((df.Openingsdatum == "") & (df.Sluitingsdatum == ""))].Openingsdatum,
            format="%Y-%m-%d",
            errors="coerce",
        )
        closing_date_mapping = pd.to_datetime(
            df[~((df.Openingsdatum == "") & (df.Sluitingsdatum == ""))].Sluitingsdatum,
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

        for row, is_bad in bad_opening_format_mask.items():
            if not is_bad:
                continue

            self._mark_bad_cell(
                row=row,
                col=opening_col,
                tooltip="Openingsdatum moet in het formaat YYYY-MM-DD zijn",
            )
        for row, is_bad in bad_closing_format_mask.items():
            if not is_bad:
                continue

            self._mark_bad_cell(
                row=row,
                col=closing_col,
                tooltip="Sluitingsdatum moet in het formaat YYYY-MM-DD zijn",
            )

        for row, is_bad in opening_future_mask.items():
            if not is_bad:
                continue

            self._mark_bad_cell(
                row=row,
                col=opening_col,
                tooltip="Datum mag niet in de toekomst zijn",
            )
        for row, is_bad in closing_future_mask.items():
            if not is_bad:
                continue

            self._mark_bad_cell(
                row=row,
                col=closing_col,
                tooltip="Datum mag niet in de toekomst zijn",
            )

        if opening_before_start_range_mask is not None:
            for row, is_bad in opening_before_start_range_mask.items():
                if not is_bad:
                    continue

                self._mark_bad_cell(
                    row=row,
                    col=opening_col,
                    tooltip="Datum moet binnen de serie-datumrange vallen",
                )
        if opening_after_end_range_mask is not None:
            for row, is_bad in opening_after_end_range_mask.items():
                if not is_bad:
                    continue

                self._mark_bad_cell(
                    row=row,
                    col=opening_col,
                    tooltip="Datum moet binnen de serie-datumrange vallen",
                )
        if closing_before_start_range_mask is not None:
            for row, is_bad in closing_before_start_range_mask.items():
                if not is_bad:
                    continue

                self._mark_bad_cell(
                    row=row,
                    col=closing_col,
                    tooltip="Datum moet binnen de serie-datumrange vallen",
                )
        if closing_after_end_range_mask is not None:
            for row, is_bad in closing_after_end_range_mask.items():
                if not is_bad:
                    continue

                self._mark_bad_cell(
                    row=row,
                    col=closing_col,
                    tooltip="Datum moet binnen de serie-datumrange vallen",
                )

        for row, is_bad in closing_before_opening_mask.items():
            if not is_bad:
                continue

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

        self.modelAboutToBeReset.emit()
        self.dataChanged.emit(
            self.index(0, name_column),
            self.index(self.rowCount(), name_column),
        )
        self.modelReset.emit()
