import csv
import io

from PySide6 import QtWidgets, QtCore, QtGui

from src.utils.base_object import ApplicationMixin
from src.utils.grid.table.common.proxy_model import SortFilterProxyModel


class GridTableView(QtWidgets.QTableView, ApplicationMixin):
    def __init__(self) -> None:
        super().__init__()

        self.setSortingEnabled(True)

    def reset_sorting(self) -> None:
        proxy = self.model(proxy=True)

        if isinstance(proxy, SortFilterProxyModel):
            proxy.reset_sorting()
        else:
            self.horizontalHeader().setSortIndicator(-1, QtCore.Qt.SortOrder.AscendingOrder)

    @staticmethod
    def _quote_cell(value: str) -> str:
        # NOTE: Excel wraps values in quotes if they contain tabs, newlines, or quotes
        if "\t" in value or "\n" in value or '"' in value:
            return '"' + value.replace('"', '""') + '"'

        return value

    @staticmethod
    def _unquote_cell(value: str) -> str:
        # NOTE: Excel wraps values in quotes if they contain tabs, newlines, or quotes
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1].replace('""', '"')

        return value

    def _is_cell_editable(self, index: QtCore.QModelIndex) -> bool:
        return bool(self.model(proxy=True).flags(index) & QtCore.Qt.ItemFlag.ItemIsEditable)

    def copy_content(self, indexes: list[QtCore.QModelIndex]) -> None:
        if len(indexes) == 1:
            QtWidgets.QApplication.clipboard().setText(self._quote_cell(indexes[0].data()))
            return

        rows: dict[int, list[int]] = {}

        for index in indexes:
            rows.setdefault(index.row(), []).append(index.column())

        # NOTE: Excel uses tab-separated columns, newline-separated rows, with a trailing newline
        copy_text = "\n".join(
            "\t".join(self._quote_cell(self.model(proxy=True).index(row, col).data()) for col in columns)
            for row, columns in rows.items()
        ) + "\n"

        QtWidgets.QApplication.clipboard().setText(copy_text)

    def cut_content(self, indexes: list[QtCore.QModelIndex]) -> None:
        if len(indexes) == 1:
            index = indexes[0]

            if not self._is_cell_editable(index):
                return

            QtWidgets.QApplication.clipboard().setText(self._quote_cell(index.data()))
            self._apply_bulk_changes([(index, "")])

            return

        rows: dict[int, list[int]] = {}

        for index in indexes:
            rows.setdefault(index.row(), []).append(index.column())

        cut_rows = []

        for row, columns in rows.items():
            row_data = []

            for col in columns:
                index = self.model(proxy=True).index(row, col)
                row_data.append(self._quote_cell(index.data()) if self._is_cell_editable(index) else "")

            cut_rows.append("\t".join(row_data))

        QtWidgets.QApplication.clipboard().setText("\n".join(cut_rows) + "\n")

        changes = [
            (index, "")
            for index in indexes
            if self._is_cell_editable(index)
        ]

        self._apply_bulk_changes(changes)

    def paste_content(self, indexes: list[QtCore.QModelIndex]) -> None:
        clipboard_text = QtWidgets.QApplication.clipboard().text()

        if not clipboard_text:
            return

        if "\n" in clipboard_text or "\t" in clipboard_text:
            self._paste_grid(clipboard_text, indexes)
        else:
            # NOTE: Excel wraps single-cell values in quotes if they contain special characters
            self._paste_value(self._unquote_cell(clipboard_text), indexes)

    def _paste_value(self, value: str, indexes: list[QtCore.QModelIndex]) -> None:
        changes = [
            (index, value)
            for index in indexes
            if self._is_cell_editable(index)
        ]

        self._apply_bulk_changes(changes)

    def _paste_grid(self, clipboard_text: str, indexes: list[QtCore.QModelIndex]) -> None:
        reader = csv.reader(io.StringIO(clipboard_text[:-1]), delimiter="\t")
        parsed_rows = list(reader)

        if not parsed_rows:
            return

        init_index = indexes[0]
        proxy = self.model(proxy=True)

        visible_rows = [r for r in range(proxy.rowCount()) if not self.isRowHidden(r)]

        try:
            init_visible_row = visible_rows.index(init_index.row())
        except ValueError:
            return

        usable_rows = visible_rows[init_visible_row:init_visible_row + len(parsed_rows)]

        if init_index.column() + len(parsed_rows[0]) > proxy.columnCount():
            return

        if len(usable_rows) != len(parsed_rows):
            return

        changes: list[tuple[QtCore.QModelIndex, str]] = []

        for row, col_contents in zip(usable_rows, parsed_rows):
            for col_offset, col_content in enumerate(col_contents):
                index = proxy.index(row, init_index.column() + col_offset)

                if self._is_cell_editable(index):
                    changes.append((index, col_content))

        self._apply_bulk_changes(changes)

    def delete_content(self, indexes: list[QtCore.QModelIndex]) -> None:
        changes = [
            (index, "")
            for index in indexes
            if self._is_cell_editable(index)
        ]

        self._apply_bulk_changes(changes)

    def _apply_bulk_changes(self, changes: list[tuple[QtCore.QModelIndex, str]]) -> None:
        if not changes:
            return

        source_model = self.model()
        proxy = self.model(proxy=True)

        if isinstance(proxy, QtCore.QSortFilterProxyModel):
            changes = [
                (proxy.mapToSource(index), value)
                for index, value in changes
            ]

        self.setUpdatesEnabled(False)

        if hasattr(source_model, "set_bulk_data"):
            source_model.set_bulk_data(changes)
        else:
            for index, value in changes:
                source_model.setData(index, value, QtCore.Qt.ItemDataRole.EditRole)

        self.setUpdatesEnabled(True)

    def keyPressEvent(self, event) -> None:
        indexes = self.selectedIndexes()

        if not indexes:
            super().keyPressEvent(event)
            return

        if event.matches(QtGui.QKeySequence.StandardKey.Copy):
            self.copy_content(indexes)

        elif event.matches(QtGui.QKeySequence.StandardKey.Cut):
            self.cut_content(indexes)

        elif event.matches(QtGui.QKeySequence.StandardKey.Paste):
            self.paste_content(indexes)

        elif event.key() == QtCore.Qt.Key.Key_Delete:
            self.delete_content(indexes)

        else:
            super().keyPressEvent(event)

    def commitData(self, editor) -> None:
        super().commitData(editor)

        value = self.model(proxy=True).data(self.currentIndex(), QtCore.Qt.ItemDataRole.EditRole)

        if len(self.selectedIndexes()) == 1:
            return

        for index in self.selectedIndexes():
            self.model(proxy=True).setData(index, value, QtCore.Qt.ItemDataRole.EditRole)

    def model(self, proxy=False) -> QtCore.QAbstractTableModel:
        model: QtCore.QAbstractTableModel = super().model()

        if isinstance(model, QtCore.QSortFilterProxyModel):
            if proxy:
                return model

            return model.sourceModel()

        return model
