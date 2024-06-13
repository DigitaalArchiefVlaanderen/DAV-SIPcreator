from PySide6 import QtCore

import sqlite3 as sql

class SQLliteModel(QtCore.QAbstractTableModel):
    def __init__(
        self,
        table_name: str,
        db_name: str="main.db",
        is_main: bool=False,
    ):
        super().__init__()
        self._table_name = table_name
        self._db_name = db_name

        # How many columns to skip (id for is_main, id/main_id for other)
        self.columns_to_skip = 1 if is_main else 2
        # self.columns_to_skip = 0

        # Dict with key = 0-index, value = column_name
        self.columns: dict[int, str] = dict()

        self.row_count, self.col_count = -1, -1
        self.calculate_shape()

    @property
    def conn(self):
        return sql.connect(self._db_name)

    def get_value(self, index):
        row, col = index.row(), index.column()

        with self.conn as conn:
            return conn.execute(
                f"SELECT {self.columns[col + self.columns_to_skip]} FROM \"{self._table_name}\" LIMIT 1 OFFSET {row};"
            ).fetchone()[0]

    def set_value(self, index, new_value):
        row, col = index.row(), index.column()

        with self.conn as conn:
            conn.execute(
                f"""
                    UPDATE "{self._table_name}"
                    SET {self.columns[col + self.columns_to_skip]}='{new_value}'
                    WHERE id=(
                        SELECT id
                        FROM {self._table_name}
                        LIMIT 1 OFFSET {row}
                    );
                """
            )

    def calculate_shape(self):
        with self.conn as conn:
            cursor = conn.execute(f"SELECT count() FROM \"{self._table_name}\";")

            self.row_count = cursor.fetchone()[0]

            cursor = conn.execute(f"pragma table_info(\"{self._table_name}\");")

            self.columns = {
                i: column_name
                for i, column_name, *_ in cursor.fetchall()
            }

            self.col_count = len(self.columns) - self.columns_to_skip

    def rowCount(self, *index):
        return self.row_count

    def columnCount(self, *index):
        return self.col_count

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return

        if (
            role == QtCore.Qt.ItemDataRole.DisplayRole
            or role == QtCore.Qt.ItemDataRole.EditRole
        ):
            return self.get_value(index)

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        if role == QtCore.Qt.ItemDataRole.EditRole:
            self.set_value(index, value)

            return True

        return False

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return list(self.columns.values())[section + self.columns_to_skip]

            if orientation == QtCore.Qt.Orientation.Vertical:
                return section

    def flags(self, index):
        return (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsEditable
        )