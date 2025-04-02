from datetime import datetime
import re

from PySide6 import QtCore

import sqlite3 as sql

from .tablemodel import TableModel, CellColor
from .state import State


class SQLliteModel(TableModel):
    bad_rows_changed: QtCore.Signal = QtCore.Signal(
        *(int,), arguments=["bad_rows_left"]
    )

    def __init__(
        self,
        table_name: str,
        db_name: str,
        state: State,
        is_main: bool=False,
        series_id: str=None,
        all_series_uris: list[str]=None
    ):
        super().__init__()
        self._table_name = table_name
        self._db_name = db_name
        self.series_id = series_id

        self.state = state

        self.is_main = is_main
        self.all_series_uris = all_series_uris

        # NOTE: keep track of if a change in the data has occurred
        self.has_changed = False

        # Which columns to hide (id for is_main, id/main_id for other, some columns based on role)
        self.hidden_columns = []

        # Dict with key = 0-index, value = column_name
        self.columns: dict[int, str] = dict()

        # Keep track of whether or not we're performing a retrieval
        # Useful for avoiding extra signal emits
        self.performing_retrieval = False

        self.row_count, self.col_count = -1, -1

        self.raw_data: list[list[str]] = []
        self.colors: dict[tuple[int, int], CellColor] = {}
        self.tooltips: dict[tuple[int, int], str] = {}

    @property
    def conn(self):
        return sql.connect(self._db_name)

    # Inherited methods
    def row_is_bad(self, row: int) -> bool:
        # This filter should only apply for non-main tables
        if self.is_main:
            return True

        _id = int(self.raw_data[row][0])

        # Check if there is any value in the matching row where the color is red or yellow
        return any(True for (row_id, _), color in self.colors.items() if row_id == _id and color in (CellColor.RED, CellColor.YELLOW))

    def row_has_no_series(self, row: int) -> bool:
        # This filter should only apply to the main table
        if not self.is_main:
            return True

        uri_col = list(self.columns.values()).index("URI Serieregister")

        if self.get_value(self.index(row, uri_col)) not in self.all_series_uris:
            return True

        series_name_col = list(self.columns.values()).index("series_name")

        if self.get_value(self.index(row, series_name_col)) in ("", None):
            return True

    def get_value(self, index):
        row, col = index.row(), index.column()

        # NOTE: quotes are not allowed for now
        return str(self.raw_data[row][col]).replace('"', "").replace("'", "")
    
    def set_value(self, index, new_value: str):
        self.has_changed = True

        row, col = index.row(), index.column()

        # NOTE: quotes are not allowed for now
        self.raw_data[row][col] = str(new_value).replace('"', "").replace("'", "")

    def calculate_shape(self):
        with self.conn as conn:
            cursor = conn.execute(f"SELECT count() FROM \"{self._table_name}\";")

            self.row_count = cursor.fetchone()[0]

            cursor = conn.execute(f"pragma table_info(\"{self._table_name}\");")

            self.columns = {
                i: column_name
                for i, column_name, *_ in cursor.fetchall()
            }

            self.col_count = len(self.columns)

    def get_data(self) -> list[list[str]]:
        self.performing_retrieval = True

        with self.conn as conn:
            db_data = [
                [v if v is not None else "" for v in r]
                for r in conn.execute(f"SELECT * FROM \"{self._table_name}\";").fetchall()
            ]
            cursor = conn.execute(f"pragma table_info(\"{self._table_name}\");")

            # NOTE: in case we added a new column
            new_columns = {
                i: column_name
                for i, column_name, *_ in cursor.fetchall()
            }

            # NOTE: we are loading db data, but we have more recent local data
            if self.has_changed:
                base_data = db_data
                
                for row_index, row in enumerate(db_data):
                    # NOTE: we can only fill in data for rows we have
                    if row_index >= len(self.raw_data):
                        break
                    
                    for col_index in range(len(row)):
                        # Since new columns might exist now, get the column by name
                        # Which column is the data in (in the db)
                        new_col_name = new_columns[col_index]

                        # Which col index is that in our data?
                        try:
                            old_col_index = list(self.columns.keys())[list(self.columns.values()).index(new_col_name)]
                        except ValueError:
                            # NOTE: this means the column we are looking for, does not exist in the old data
                            continue

                        # Overwrite with data we have now
                        base_data[row_index][col_index] = self.raw_data[row_index][old_col_index]

                self.raw_data = base_data
            else:
                self.raw_data = db_data

            self.row_count = len(self.raw_data)
            self.columns = new_columns
            self.col_count = len(self.columns)

        # NOTE: for the checks, set all the cells
        changed_before = self.has_changed

        # Reset colors and tooltips
        self.colors = {}
        self.tooltips = {}

        self.modelAboutToBeReset.emit()
        for row_index, row in enumerate(self.raw_data):
            # NOTE: just for debugging, won't slow down the process significantly enough to affect anything, might as well leave it
            if row_index % 100 == 0:
                print(f'{f"{self._table_name} - {row_index}":180}|', end="\r")

            for col_index, value in enumerate(row):
                self.setData(self.index(row_index, col_index), value)
        print()

        self.has_changed = changed_before

        self.performing_retrieval = False

        # NOTE: since no signals were being emitted before, emit one now
        self.bad_rows_changed.emit(len(self.colors))
        self.modelReset.emit()

    def save_data(self) -> None:
        with self.conn as conn:
            for row in range(self.row_count):
                main_id = self.raw_data[row][1]
                set_value = ",\n\t".join([f"\"{self.columns[col]}\"='{self.raw_data[row][col]}'" for col in range(2, self.col_count)])

                conn.execute(
                    f"""
                        UPDATE "{self._table_name}"
                        SET {set_value}
                        WHERE main_id={main_id};
                    """
                )

        self.has_changed = False

    def rowCount(self, *index):
        return self.row_count

    def columnCount(self, *index):
        return self.col_count

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return

        row, col = index.row(), index.column()
        _id = int(self.raw_data[row][0])

        if (
            role == QtCore.Qt.ItemDataRole.DisplayRole
            or role == QtCore.Qt.ItemDataRole.EditRole
        ):
            return self.get_value(index)
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            color = self.colors.get((_id, col))

            if color:
                return color.value
            
            # Mark grey if not editable
            if QtCore.Qt.ItemFlag.ItemIsEditable.name not in self.flags(index).name:
                return CellColor.GREY.value

        elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
            tooltip = self.tooltips.get((_id, col))

            if tooltip:
                return tooltip

    def setData(self, index, value: str, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        if role == QtCore.Qt.ItemDataRole.EditRole:
            if not self.is_main and QtCore.Qt.ItemFlag.ItemIsEditable.name not in self.flags(index).name:
                return False

        row, col = index.row(), index.column()
        column = self.columns[col]

        value = str(value).encode(encoding="utf-8", errors="replace").decode("utf-8")

        if role == QtCore.Qt.ItemDataRole.EditRole and self.is_main:
            if column == "URI Serieregister":
                # NOTE: this also checks the series_name
                self.serie_check(row, col, value)

            self.set_value(index, value)
            self.dataChanged.emit(index, index)
            return True

        if role == QtCore.Qt.ItemDataRole.EditRole:
            if column == "Path in SIP":
                self.path_in_sip_check(row, col, value)

                # NOTE: set Type and DossierRef
                self.set_value(
                    self.index(row, col+1),
                    "stuk" if "/" in value else "dossier"
                )
                self.set_value(
                    self.index(row, col+2),
                    value.split("/", 1)[0]
                )
            elif column in ("Openingsdatum", "Sluitingsdatum"):
                self.date_check(row, col, value)

                self.dataChanged.emit(self.index(row, col-1), self.index(row, col+1))
            elif any(c in column for c in ("Origineel Doosnummer", "Legacy locatie ID", "Legacy range", "Verpakkingstype")):
                self.location_check(row, col, value)
            elif column == "Naam":
                self.name_check(row, col, value)
            elif column == "ID_Rijksregisternummer":
                value = self.rrn_check(row, col, value)

            self.set_value(index, value)
            self.dataChanged.emit(index, index)
            return True

        return False

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return list(self.columns.values())[section]

            if orientation == QtCore.Qt.Orientation.Vertical:
                return section

    def flags(self, index):
        if not index.isValid():
            return

        if self.columns[index.column()] in ("Type", "DossierRef", "Analoog?"):
            return (
                QtCore.Qt.ItemFlag.ItemIsSelectable
                | QtCore.Qt.ItemFlag.ItemIsEnabled
            )

        return (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsEditable
        ) if not self.is_main else (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
        )

    # NOTE: utils
    def _mark_cell(self, row: int, col: int, color: CellColor = None, tooltip: str = None) -> None:        
        _id = int(self.raw_data[row][0])

        if not color:
            # Unmark
            if (_id, col) in self.colors:
                del self.colors[(_id, col)]

            if (_id, col) in self.tooltips:
                del self.tooltips[(_id, col)]
        else:
            self.colors[(_id, col)] = color

            if tooltip:
                self.tooltips[(_id, col)] = tooltip

        if not self.performing_retrieval:
            self.bad_rows_changed.emit(len(self.colors))

    # NOTE: Checks
    def path_in_sip_check(self, row: int, col: int, value: str) -> None:
        # NOTE: since this needs to be unique, check duplicates first
        old_value = self.raw_data[row][col]

        old_duplicates = [r for r in range(self.row_count) if self.raw_data[r][col] == old_value and r != row]
        new_duplicates = [r for r in range(self.row_count) if self.raw_data[r][col] == value and r != row]

        # NOTE: check if we introduces new duplication
        if len(new_duplicates) >= 1:
            for r in new_duplicates + [row]:
                self._mark_cell(r, col, CellColor.RED, "Path in SIP moet uniek zijn")

        # NOTE: only check the row if it didn't introduce duplication (otherwise we already marked it)
        rows_to_check = [row] if len(new_duplicates) == 0 else []

        # NOTE: check if we solved some duplication
        if len(old_duplicates) == 1 and old_value != value:
            # NOTE: check this one value too
            rows_to_check.extend(old_duplicates)

        for r in rows_to_check:
            val = self.raw_data[r][col]

            if r == row:
                val = value

            if val == "":
                self._mark_cell(r, col, CellColor.RED, "Path in SIP mag niet leeg zijn")
            elif "/" in val and self.state.configuration.active_type != "onroerend_erfgoed":
                self._mark_cell(r, col, CellColor.RED, "Path in SIP mag geen '/' bevatten")
            else:
                self._mark_cell(r, col)

        if rows_to_check:
            self.dataChanged.emit(
                self.index(min(rows_to_check), 0),
                self.index(max(rows_to_check), self.col_count)
            )

    def serie_check(self, row: int, col: int, value: str) -> None:
        series_name = self.raw_data[row][list(self.columns.values()).index("series_name")]
        uri = value

        if uri == "":
            self._mark_cell(row, col, CellColor.RED, tooltip="Een serie moet nog gelinkt worden")
            self._mark_cell(row, list(self.columns.values()).index("series_name"), CellColor.RED, tooltip="Een serie moet nog gelinkt worden")
        elif uri not in self.all_series_uris:
            self._mark_cell(row, col, CellColor.YELLOW, tooltip="De gegeven uri is niet teruggevonden onder de huidige connectie")
            self._mark_cell(row, list(self.columns.values()).index("series_name"), CellColor.RED, tooltip="Een serie moet nog gelinkt worden")
        else:
            # NOTE: uri found in list
            if series_name == "":
                self._mark_cell(row, list(self.columns.values()).index("series_name"), CellColor.RED, tooltip="Serie ophalen is misgelopen")
            else:
                self._mark_cell(
                    row=row, col=col
                )
                self._mark_cell(
                    row=row, col=list(self.columns.values()).index("series_name")
                )

    def date_check(self, row: int, col: int, value: str, check_other_date_cell=True) -> None:
        columns = list(self.columns.values())
        start_column, end_column = columns.index("Openingsdatum"), columns.index("Sluitingsdatum")
        start_value = value if col == start_column else self.raw_data[row][start_column]
        end_value = value if col == end_column else self.raw_data[row][end_column]

        def _check_other_date_cell() -> None:
            # NOTE: only do this if we still need to
            if check_other_date_cell:
                self.date_check(
                    row,
                    col=start_column if col == end_column else end_column,
                    value=start_value if col == end_column else end_value,
                    check_other_date_cell=False
                )

        # Check empty
        if value == "":
            self._mark_cell(row, col, CellColor.RED, "Datum mag niet leeg zijn")
            
            _check_other_date_cell()
            return

        # Check valid date
        try:
            date = datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            self._mark_cell(row, col, CellColor.RED, "Datum moet in het formaat yyyy-mm-dd zijn, en moet een geldige datum zijn")
            
            _check_other_date_cell()
            return


        if date > datetime.now():
            # NOTE: this might have fixed or caused an issue with the other date-cell
            self._mark_cell(row, col, CellColor.RED, "Datum mag niet in de toekomst zijn")
            
            _check_other_date_cell()
            return

        # Check range
        van_tot = re.match(r".* \(Geldig van (.*?)( t.e.m | tot )(.*?)\)", self._table_name)
        van = re.match(r".* \(Geldig van (.*)\)", self._table_name)
        tot = re.match(r".* \(Geldig tot (.*)\)", self._table_name)

        before = after = None

        if van_tot:
            before = van_tot.group(1)
            after = van_tot.group(3)
        elif van:
            before = van.group(1)
        elif tot:
            after = tot.group(1)

        date_mon_map = {
            "jan.": "01",
            "feb.": "02",
            "mrt.": "03",
            "apr.": "04",
            "mei.": "05",
            "jun.": "06",
            "jul.": "07",
            "aug.": "08",
            "sep.": "09",
            "oct.": "10",
            "nov.": "11",
            "dec.": "12",
        }

        if before is not None and before != "...":
            for k, v in date_mon_map.items():
                before = before.replace(k, v)

            before = datetime.strptime(before, "%d %m %Y")
            
            if date < before:
                self._mark_cell(row, col, CellColor.RED, "Datum mag niet voor de openingsdatum van de serie zijn")
                
                _check_other_date_cell()
                return

        if after is not None and after != "...":
            for k, v in date_mon_map.items():
                after = after.replace(k, v)

            after = datetime.strptime(after, "%d %m %Y")
            
            if date > after:
                self._mark_cell(row, col, CellColor.RED, "Datum mag niet na de sluitingsdatum van de serie zijn")
                
                _check_other_date_cell()
                return

        # If this is the check_other_date_cell run (aka, we are in a repeat run), but we got to this point, we're good
        # Checks from this point on would have marked both cells in the previous iteration
        if not check_other_date_cell:
            self._mark_cell(row, col)
            return

        # Check start vs end in row
        try:
            start_date = datetime.strptime(start_value, "%Y-%m-%d")
            end_date = datetime.strptime(end_value, "%Y-%m-%d")
        except ValueError:
            # The other column is in a bad format
            self._mark_cell(row, col)
            return

        if start_date > end_date:
            self._mark_cell(row, start_column, CellColor.RED, "Openingsdatum mag niet na sluitingsdatum vallen")
            self._mark_cell(row, end_column, CellColor.RED, "Openingsdatum mag niet na sluitingsdatum vallen")
            return
        else:
            self._mark_cell(row, start_column)
            self._mark_cell(row, end_column)

        _check_other_date_cell()

        self.dataChanged.emit(
            self.index(row, 0),
            self.index(row, self.col_count)
        )

    def location_check(self, row: int, col: int, value: str) -> None:
        # NOTE: if all the columns have empty values, mark them all red
        original_cols = ("Origineel Doosnummer", "Legacy locatie ID", "Legacy range", "Verpakkingstype")
        column_names = list(self.columns.values())
        all_duplicate_cols = [c for c in self.columns.values() if any(oc in c for oc in original_cols)]
        duplicate_col_indexes = [column_names.index(c) for c in all_duplicate_cols]

        row_values = self.raw_data[row]

        if all(row_values[c] == "" for c in duplicate_col_indexes if c != col) and value == "":
            self.modelAboutToBeReset.emit()

            for col_index in duplicate_col_indexes:
                self._mark_cell(row, col_index, CellColor.RED, "Een locatie moet ingevuld zijn")

            self.modelReset.emit()
            return
        elif all(row_values[c] == "" for c in duplicate_col_indexes if c != col) and value != "":
            # NOTE: all empty except the current one, unset them all but do not return
            self.modelAboutToBeReset.emit()

            for col_index in duplicate_col_indexes:
                self._mark_cell(row, col_index)
            
            self.modelReset.emit()

        actual_column_name = self.columns[col]
        suffix = ""

        # Check if it is a duplicated column
        if "_" in actual_column_name:
            suffix = "_" + actual_column_name.rsplit("_", 1)[-1]

        # If we have a value in any of the columns, they all need a value
        # These are the 4 columns linked by the suffix number
        cols = [c + suffix for c in original_cols]

        col_indexes = [column_names.index(c) for c in cols]

        # If any has a value, or we're enterying a value now
        should_have_a_value = any(row_values[c] != "" for c in col_indexes if c != col) or value != ""

        for c in col_indexes:
            val = row_values[c]

            if c == col:
                val = value

            if should_have_a_value and val == "":
                self._mark_cell(row, c, CellColor.RED, "De combinatie van de 4 locatie-kolommen moeten een waarde hebben")
            else:
                self._mark_cell(row, c)

    def name_check(self, row: int, col: int, value: str) -> None:
        old_value = self.raw_data[row][col]

        if old_value != "":
            old_duplicates = [r for r in range(self.row_count) if self.raw_data[r][col] == old_value and r != row]

            # NOTE: fixed some duplication
            if len(old_duplicates) == 1:
                self._mark_cell(
                    row=old_duplicates[0],
                    col=col
                )

        if value == "":
            self._mark_cell(row, col, CellColor.RED, "Naam mag niet leeg zijn")
            return
        
        if len(value) > 255:
            self._mark_cell(row, col, CellColor.RED, "Naam mag niet langer zijn dan 255 karakters")
            return

        # NOTE: check for new duplicates
        new_duplicates = [r for r in range(self.row_count) if self.raw_data[r][col] == value if r != row]

        # NOTE: check if we introduces new duplication
        if len(new_duplicates) > 0:
            for r in new_duplicates + [row]:
                self._mark_cell(r, col, CellColor.RED, "Naam veld moet uniek zijn")

            return False

        self._mark_cell(row, col)

    def rrn_check(self, row: int, col: int, value: str) -> str:
        if value == "":
            self._mark_cell(row, col)
            return value

        # NOTE: we allow loose form matching, and will just set it correctly later
        loose_form_match = re.match(r"^\d{11}$", value)
        if loose_form_match:
            value = f"{value[:2]}.{value[2:4]}.{value[4:6]}-{value[6:9]}.{value[9:]}"
            
        strict_form_match = re.match(r"^\d{2}\.\d{2}\.\d{2}-\d{3}\.\d{2}$", value)

        if not strict_form_match:
            self._mark_cell(row, col, CellColor.RED, "Rijksregisternummer moet van vorm xx.xx.xx-xxx.xx zijn, of 11 cijfers na elkaar zijn")
            return value
        
        # NOTE: check if the actual rrn is valid
        calc, control = value[:-2].replace(".", "").replace("-", ""), value[-2:]

        is_valid_check = lambda c: 97 - int(c) % 97 == int(control)

        # NOTE: for people born after 2000, add a 2 to the calc
        calc_before, calc_after = calc, f"2{calc}"

        if not is_valid_check(calc_before) and not is_valid_check(calc_after):
            self._mark_cell(row, col, CellColor.RED, "Ingegeven rijksregisternummer is niet mogelijk")
            return value

        self._mark_cell(row, col)
        return value
