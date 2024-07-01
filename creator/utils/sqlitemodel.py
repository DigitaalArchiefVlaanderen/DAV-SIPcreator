from enum import Enum

from PySide6 import QtCore, QtGui

import sqlite3 as sql


class Color(Enum):
    RED = QtGui.QBrush(QtGui.QColor(255, 0, 0))
    YELLOW = QtGui.QBrush(QtGui.QColor(255, 255, 0))
    GREY = QtGui.QBrush(QtGui.QColor(230, 230, 230))


class SQLliteModel(QtCore.QAbstractTableModel):
    bad_rows_changed: QtCore.Signal = QtCore.Signal(
        *(int,), arguments=["bad_rows_left"]
    )

    def __init__(
        self,
        table_name: str,
        db_name: str,
        is_main: bool=False,
    ):
        super().__init__()
        self._table_name = table_name
        self._db_name = db_name

        self.is_main = is_main

        # NOTE: keep track of if a change in the data has occurred
        self.has_changed = False

        # Which columns to hide (id for is_main, id/main_id for other, some columns based on role)
        self.hidden_columns = []

        # Dict with key = 0-index, value = column_name
        self.columns: dict[int, str] = dict()

        self.row_count, self.col_count = -1, -1

        self._data: list[list[str]] = []
        self.colors: dict[tuple[int, int], Color] = {}
        self.tooltips: dict[tuple[int, int], str] = {}

        self.get_data()

        # self.calculate_shape()

    @property
    def conn(self):
        return sql.connect(self._db_name)

    def get_value(self, index):
        row, col = index.row(), index.column()

        # NOTE: quotes are not allowed for now
        return self._data[row][col].replace('"', "").replace("'", "")
    
    def set_value(self, index, new_value: str):
        self.has_changed = True

        row, col = index.row(), index.column()

        # NOTE: quotes are not allowed for now
        self._data[row][col] = str(new_value).replace('"', "").replace("'", "")

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
        with self.conn as conn:
            db_data = [
                [v if v is not None else "" for v in r]
                for r in conn.execute(f"SELECT * FROM \"{self._table_name}\";").fetchall()
            ]

            if self.has_changed:
                # NOTE: treat db_data as the base, overwrite with items from current data where needed
                new_data = db_data
                
                for row_index, row in enumerate(db_data):
                    if row_index >= len(self._data):
                        break
                    
                    for col_index in range(len(row)):
                        if col_index >= len(self._data[row_index]):
                            break

                        # Overwrite with data we have now
                        new_data[row_index][col_index] = self._data[row_index][col_index]

                self._data = new_data
            else:
                self._data = db_data

            self.row_count = len(self._data)

            cursor = conn.execute(f"pragma table_info(\"{self._table_name}\");")

            self.columns = {
                i: column_name
                for i, column_name, *_ in cursor.fetchall()
            }

            self.col_count = len(self.columns)

        # NOTE: for the checks, set all the cells
        for row_index, row in enumerate(self._data):
            for col_index, value in enumerate(row):
                self.setData(self.index(row_index, col_index), value)

        # NOTE: not very good to use this method for retrieval and getting
        return self._data

    def save_data(self) -> None:
        with self.conn as conn:
            for row in range(self.row_count):
                main_id = self._data[row][1]
                set_value = ",\n\t".join([f"\"{self.columns[col]}\"='{self._data[row][col]}'" for col in range(2, self.col_count)])

                conn.execute(
                    f"""
                        UPDATE "{self._table_name}"
                        SET {set_value}
                        WHERE main_id={main_id};
                    """
                )

    def rowCount(self, *index):
        return self.row_count

    def columnCount(self, *index):
        return self.col_count

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return

        row, col = index.row(), index.column()
        _id = self._data[row][0]

        if (
            role == QtCore.Qt.ItemDataRole.DisplayRole
            or role == QtCore.Qt.ItemDataRole.EditRole
        ):
            return self.get_value(index)
        elif role == QtCore.Qt.ItemDataRole.BackgroundRole:
            color = self.colors.get((_id, col))

            if color:
                return color.value
        elif role == QtCore.Qt.ItemDataRole.ToolTipRole:
            tooltip = self.tooltips.get((_id, col))

            if tooltip:
                return tooltip

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        row, col = index.row(), index.column()

        if role == QtCore.Qt.ItemDataRole.EditRole:
            self.set_value(index, value)

            if self.columns[col] == "Path in SIP":
                self.path_in_sip_check(row, col, value)

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
        return (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsEditable
        ) if not self.is_main else (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
        )

    def sort(self, col: int, order: QtCore.Qt.SortOrder) -> None:
        self.layoutAboutToBeChanged.emit()

        self._data.sort(
            key=lambda row: row[col],
            reverse=order is QtCore.Qt.SortOrder.DescendingOrder
        )

        self.layoutChanged.emit()

    def _mark_cell(self, row: int, col: int, color: Color = None, tooltip: str = None) -> None:        
        _id = self._data[row][0]

        if not color:
            # Unmark
            if (_id, col) in self.colors:
                del self.colors[(_id, col)]

            if (_id, col) in self.tooltips:
                del self.tooltips[(_id, col)]
        else:
            self.colors.setdefault((_id, col), color)

            if tooltip:
                self.tooltips.setdefault((_id, col), tooltip)

        self.bad_rows_changed.emit(len(self.colors))

    # NOTE: Checks
    def path_in_sip_check(self, row: int, col: int, value: str) -> None:
        if value == "":
            self._mark_cell(row, col, Color.RED, "Path in SIP mag niet leeg zijn")
        elif "/" in value:
            self._mark_cell(row, col, Color.RED, "Path in SIP mag geen '/' bevatten")
        else:
            self._mark_cell(row, col)
