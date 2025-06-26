from datetime import datetime
import re
from functools import partial

from PySide6 import QtCore

from creator.utils.tablemodel import TableModel, CellColor
from creator.utils.analoog.list_item import ListItem


class ListTableModel(TableModel):
    """
    Abstract implementation of holding data in a 2D-list
    """
    bad_rows_changed: QtCore.Signal = QtCore.Signal(
        *(bool,), arguments=["is_data_valid"]
    )

    def __init__(self, list_item: ListItem):
        super().__init__()

        self.columns = {i: c for i, c in enumerate(list_item.grid.columns)}
        self.raw_data = list_item.grid.data

        self.series = list_item.grid.series

        self.colors: dict[tuple[int, int], CellColor] = dict()
        self.tooltips: dict[tuple[int, int], str] = dict()

        self.has_changed = False
        self.manual_entry = True

    def first_open(self) -> None:
        self.colors = dict()
        self.tooltips = dict()

        # Run the data through all the checks
        for row, values in enumerate(self.raw_data):
            for col, value in enumerate(values):
                self.run_checks(row, col, value)

    # Inherited methods
    def row_is_bad(self, row: int) -> bool:
        # NOTE: empty row is not a bad thing
        if all(v == "" for v in self.raw_data[row][1:]):
            return False

        # Check if there is any value in the matching row where the color is red or yellow
        return any(True for (row_id, _), color in self.colors.items() if row_id == row and color in (CellColor.RED, CellColor.YELLOW))

    # Table methods
    def get_value(self, index):
        row, col = index.row(), index.column()

        # NOTE: quotes are not allowed for now
        return str(self.raw_data[row][col]).replace('"', "").replace("'", "")

    def paste_data(self, start_index: QtCore.QModelIndex, visible_rows: list[int], copy_text: str) -> None:
        # NOTE: start the pasting at the start_index
        # Continuing as long as there is data, also making sure to only paste on visible rows
        row_contents = copy_text[:-1].split("\n")

        start_row, start_col = start_index.row(), start_index.column()

        # First we need to know how many rows we can already paste
        existing_rows = len(visible_rows) - visible_rows.index(start_row)

        # Next we need to determine how many more rows we need to fit the data
        extra_rows_needed = len(row_contents) - existing_rows

        # Now we actually create the rows, making sure to add an empty one at the bottom
        # NOTE: we'll need this later
        row_count_before_adding = self.rowCount()
        self.insert_rows(extra_rows_needed + 1)

        # Which rows did we actually want to add data to now
        rows_to_add_to = visible_rows[visible_rows.index(start_row):] + [
            i + row_count_before_adding for i in range(extra_rows_needed)
        ]

        # Now actually set the values
        for row, row_content in zip(rows_to_add_to, row_contents):
            col_contents = row_content.split("\t")

            for relative_col, value in enumerate(col_contents):
                self.raw_data[row][relative_col + start_col] = value
        
        # Also run the checks (on row level)
        for row, row_content in zip(rows_to_add_to, row_contents):
            for col, value in enumerate(self.raw_data[row][1:], start=1):
                self.run_checks(row, col, value)

    def insert_rows(self, count: int) -> None:
        last_row = self.raw_data[self.rowCount() - 1]
        last_id = int(last_row[0])

        parent = QtCore.QModelIndex()
        self.beginInsertRows(parent, self.rowCount(), self.rowCount() + count - 1)

        for _ in range(count):
            new_row = [""] * len(last_row)
            last_id += 1
            new_row[0] = str(last_id)

            self.raw_data.append(new_row)

        self.insertRows(self.rowCount(), count, parent)

        self.endInsertRows()

        for c, value in enumerate(new_row[1:], start=1):
            self.run_checks(self.rowCount()-1, c, value)

    def set_value(self, index, new_value: str):
        self.has_changed = True

        row, col = index.row(), index.column()

        # NOTE: quotes are not allowed for now
        self.raw_data[row][col] = str(new_value).replace('"', "").replace("'", "")

        # NOTE: if we entered data in the final row, add a new row
        if self.manual_entry and row + 1 == self.rowCount():
            QtCore.QTimer.singleShot(0, partial(self.insert_rows, 1))

    def rowCount(self, *index):
        return len(self.raw_data)

    def columnCount(self, *index):
        return len(self.columns)

    def data(self, index: QtCore.QModelIndex, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return

        row, col = index.row(), index.column()

        if (
            role == QtCore.Qt.ItemDataRole.DisplayRole
            or role == QtCore.Qt.ItemDataRole.EditRole
        ):
            return self.get_value(index)
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            color = self.colors.get((row, col))

            if color:
                return color.value
            
            # Mark grey if not editable
            if QtCore.Qt.ItemFlag.ItemIsEditable.name not in self.flags(index).name:
                return CellColor.GREY.value

        elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
            tooltip = self.tooltips.get((row, col))

            if tooltip:
                return tooltip

    def run_checks(self, row: int, col: int, value: str) -> str:
        column = self.columns[col]

        value = str(value).encode(encoding="utf-8", errors="replace").decode("utf-8")

        if column == "Path in SIP":
            self.path_in_sip_check(row, col, value)

            old_manual_entry = self.manual_entry
            self.manual_entry = False
            if value != "":
                # NOTE: set Type, DossierRef and 'Analoog?'
                self.set_value(
                    self.index(row, col+1),
                    "stuk" if "/" in value else "dossier"
                )
                self.set_value(
                    self.index(row, col+2),
                    value.split("/", 1)[0]
                )
                self.set_value(
                    self.index(row, col+3),
                    "ja"
                )
            else:
                # NOTE: clear Type, DossierRef and 'Analoog?'
                self.set_value(
                    self.index(row, col+1),
                    ""
                )
                self.set_value(
                    self.index(row, col+2),
                    ""
                )
                self.set_value(
                    self.index(row, col+3),
                    ""
                )
            self.manual_entry = old_manual_entry
        elif column in ("Openingsdatum", "Sluitingsdatum"):
            self.date_check(row, col, value)

            self.dataChanged.emit(self.index(row, col-1), self.index(row, col+1))
        elif column in ("ID beschrijving", "ID verpakking"):
            self.location_check(row, col, value)
        elif column == "Naam":
            self.name_check(row, col, value)
        elif column == "ID_Rijksregisternummer":
            value = self.rrn_check(row, col, value)

        return value

    def setData(self, index: QtCore.QModelIndex, value: str, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        if role == QtCore.Qt.ItemDataRole.EditRole:
            if QtCore.Qt.ItemFlag.ItemIsEditable.name not in self.flags(index).name:
                return False

        if role == QtCore.Qt.ItemDataRole.EditRole:
            value = self.run_checks(index.row(), index.column(), value)
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
            return QtCore.Qt.ItemFlag.NoItemFlags

        if self.columns[index.column()] in ("Type", "DossierRef", "Analoog?"):
            return (
                QtCore.Qt.ItemFlag.ItemIsSelectable
                | QtCore.Qt.ItemFlag.ItemIsEnabled
            )

        return (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsEditable
        )

    # NOTE: utils
    def _mark_cell(self, row: int, col: int, color: CellColor = None, tooltip: str = None) -> None:        
        if not color:
            # Unmark
            if (row, col) in self.colors:
                del self.colors[(row, col)]

            if (row, col) in self.tooltips:
                del self.tooltips[(row, col)]
        else:
            self.colors[(row, col)] = color

            if tooltip:
                self.tooltips[(row, col)] = tooltip

        self.bad_rows_changed.emit(self.is_data_valid())

    # NOTE: Checks
    def path_in_sip_check(self, row: int, col: int, value: str) -> None:
        # NOTE: since this needs to be unique, check duplicates first
        old_value = self.raw_data[row][col]

        old_duplicates = [r for r in range(self.rowCount()) if self.raw_data[r][col] == old_value and r != row]
        new_duplicates = [r for r in range(self.rowCount()) if self.raw_data[r][col] == value and r != row]

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
            elif "/" in val:
                self._mark_cell(r, col, CellColor.RED, "Path in SIP mag geen '/' bevatten")
            else:
                self._mark_cell(r, col)

        if rows_to_check:
            self.dataChanged.emit(
                self.index(min(rows_to_check), 0),
                self.index(max(rows_to_check), self.columnCount())
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
        if self.series.valid_from is not None:
            if date < self.series.valid_from:
                self._mark_cell(row, col, CellColor.RED, "Datum mag niet voor de openingsdatum van de serie zijn")
                
                _check_other_date_cell()
                return

        if self.series.valid_to is not None:
            if date > self.series.valid_to:
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
            self.index(row, self.columnCount())
        )

    def name_check(self, row: int, col: int, value: str) -> None:
        old_value = self.raw_data[row][col]

        if old_value != "":
            old_duplicates = [r for r in range(self.rowCount()) if self.raw_data[r][col] == old_value and r != row]

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
        new_duplicates = [r for r in range(self.rowCount()) if self.raw_data[r][col] == value if r != row]

        # NOTE: check if we introduces new duplication
        if len(new_duplicates) > 0:
            for r in new_duplicates + [row]:
                self._mark_cell(r, col, CellColor.RED, "Naam veld moet uniek zijn")

            return False

        self._mark_cell(row, col)

    def location_check(self, row: int, col: int, value: str) -> None:
        column = self.columns[col]

        if value == "":
            self._mark_cell(row, col, CellColor.RED, tooltip=f"{column} moet een waarde hebben")
        else:
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

    # NOTE: global check
    def is_data_valid(self) -> bool:
        # Checks if the data is fine to be made into a SIP
        # If any faults are found in a non-empty row, we can't make a SIP
        for (row, _), color in self.colors.items():
            if color == CellColor.RED:
                # Row being empty is ok
                if all(v == "" for v in self.raw_data[row][1:]):
                    continue

                # Row has data, and an issue
                return False

        for row in self.raw_data:
            # There needs to be at least one valid row (and no invalid ones)
            if any(v != "" for v in row[1:]):
                return True
            
        # No rows have any data without being invalid
        return False
