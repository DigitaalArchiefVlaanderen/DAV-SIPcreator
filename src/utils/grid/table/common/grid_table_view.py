import csv
import io

from PySide6 import QtCore, QtGui, QtWidgets

from src.utils.base_object import ApplicationMixin
from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.grid.table.common.proxy_model import SortFilterProxyModel

BULK_PASTE_THRESHOLD = 1000
GRID_TABLE_TEXT = UI_TEXT_ELEMENTS["grid_table"]


class GridTableView(QtWidgets.QTableView, ApplicationMixin):
    def __init__(self) -> None:
        super().__init__()

        self.setSortingEnabled(True)
        self._saved_row = -1
        self._saved_col = -1

    def reset(self) -> None:
        """Preserve cursor position across model resets."""
        cur = self.currentIndex()

        if cur.isValid():
            self._saved_row = cur.row()
            self._saved_col = cur.column()

        super().reset()

        proxy = self.model(proxy=True)

        if (
            proxy is not None
            and self._saved_row >= 0
            and self._saved_row < proxy.rowCount()
            and self._saved_col < proxy.columnCount()
        ):
            self.setCurrentIndex(proxy.index(self._saved_row, self._saved_col))

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
        copy_text = (
            "\n".join(
                "\t".join(self._quote_cell(self.model(proxy=True).index(row, col).data()) for col in columns)
                for row, columns in rows.items()
            )
            + "\n"
        )

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

        changes = [(index, "") for index in indexes if self._is_cell_editable(index)]

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
        changes = [(index, value) for index in indexes if self._is_cell_editable(index)]

        self._apply_bulk_changes(changes)

    def _paste_grid(self, clipboard_text: str, indexes: list[QtCore.QModelIndex]) -> None:
        reader = csv.reader(io.StringIO(clipboard_text[:-1]), delimiter="\t")
        parsed_rows = list(reader)

        if not parsed_rows:
            return

        init_index = indexes[0]
        proxy = self.model(proxy=True)
        source_model = self.model()

        visible_rows = [r for r in range(proxy.rowCount()) if not self.isRowHidden(r)]

        try:
            init_visible_row = visible_rows.index(init_index.row())
        except ValueError:
            return

        if init_index.column() + len(parsed_rows[0]) > proxy.columnCount():
            return

        usable_rows = visible_rows[init_visible_row : init_visible_row + len(parsed_rows)]
        can_expand = hasattr(source_model, "set_bulk_data")
        extra_rows_needed = len(parsed_rows) - len(usable_rows)

        if extra_rows_needed > 0 and not can_expand:
            return

        self.setUpdatesEnabled(False)

        if extra_rows_needed > 0 and hasattr(source_model, "_insert_empty_rows"):
            source_model._insert_empty_rows(extra_rows_needed)

            for i in range(extra_rows_needed):
                usable_rows.append(proxy.rowCount() - extra_rows_needed + i)

        is_proxied = isinstance(proxy, QtCore.QSortFilterProxyModel)
        changes: list[tuple[QtCore.QModelIndex, str]] = []

        for paste_offset, col_contents in enumerate(parsed_rows):
            row = usable_rows[paste_offset]

            for col_offset, col_content in enumerate(col_contents):
                index = proxy.index(row, init_index.column() + col_offset)

                if self._is_cell_editable(index):
                    source_index = proxy.mapToSource(index) if is_proxied else index
                    changes.append((source_index, col_content))

        if len(changes) >= BULK_PASTE_THRESHOLD:
            self.application.notify_user_signal.emit(
                GRID_TABLE_TEXT["bulk_paste_warning"]["title"],
                GRID_TABLE_TEXT["bulk_paste_warning"]["text"].format(count=len(changes)),
            )

        if hasattr(source_model, "set_bulk_data"):
            source_model.set_bulk_data(changes)
        else:
            for index, value in changes:
                source_model.setData(index, value, QtCore.Qt.ItemDataRole.EditRole)

        self.setUpdatesEnabled(True)

    def delete_content(self, indexes: list[QtCore.QModelIndex]) -> None:
        changes = [(index, "") for index in indexes if self._is_cell_editable(index)]

        self._apply_bulk_changes(changes)

    def _apply_bulk_changes(self, changes: list[tuple[QtCore.QModelIndex, str]]) -> None:
        if not changes:
            return

        self.model()
        proxy = self.model(proxy=True)

        if isinstance(proxy, QtCore.QSortFilterProxyModel):
            changes = [(proxy.mapToSource(index), value) for index, value in changes]

        self._apply_bulk_changes_direct(changes)

    def _apply_bulk_changes_direct(self, changes: list[tuple[QtCore.QModelIndex, str]]) -> None:
        if not changes:
            return

        source_model = self.model()

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
