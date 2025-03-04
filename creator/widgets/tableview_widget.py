from PySide6 import QtWidgets, QtCore, QtGui


from ..utils.path_loader import resource_path


class TableView(QtWidgets.QTableView):
    def __init__(self, editable=True):
        super().__init__()

        self.editable = editable

        self.setSortingEnabled(True)

        self.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))

        # NOTE: seems to be the only way to access the select-all corner button
        self.corner: QtWidgets.QPushButton = self.findChild(QtWidgets.QAbstractButton)

    def copy_content(self, indexes: list):
        # Single cell copy
        if len(indexes) == 1:
            QtWidgets.QApplication.clipboard().setText(self.model().data(indexes[0]))
            return

        # Dictionary with key being the row, value being a list of columns
        rows = {}

        for index in indexes:
            rows[index.row()] = rows.get(index.row(), []) + [index.column()]

        copy_rows = []

        for row, columns in rows.items():
            copy_rows.append("\t".join(
                    [self.model().index(row, col).data() for col in columns]
                )
            )

        # NOTE: excel complicates matters, they add a trailing '\n' character
        # This however means we need to do the same, and expect this
        copy_text = "\n".join(copy_rows) + "\n"

        QtWidgets.QApplication.clipboard().setText(copy_text)

    def cut_content(self, indexes: list):
        # Single cell cut
        if len(indexes) == 1:
            index = indexes[0]
            QtWidgets.QApplication.clipboard().setText(self.model().data(index))
            self.model().setData(index=index, value="", role=QtCore.Qt.ItemDataRole.EditRole)
            self.model().dataChanged.emit(index, index)
            return

        # Dictionary with key being the row, value being a list of columns
        rows = {}

        for index in indexes:
            rows[index.row()] = rows.get(index.row(), []) + [index.column()]

        cut_rows = []
        for row, columns in rows.items():
            cut_rows.append("\t".join(
                    [self.model().index(row, col).data() for col in columns]
                )
            )

        # NOTE: excel complicates matters, they add a trailing '\n' character
        # This however means we need to do the same, and expect this
        cut_text = "\n".join(cut_rows) + "\n"

        QtWidgets.QApplication.clipboard().setText(cut_text)

        # Make sure to set the values to empty
        for index in indexes:
            self.model().setData(index=index, value="", role=QtCore.Qt.ItemDataRole.EditRole)
            self.model().dataChanged.emit(index, index)

    def paste_content(self, indexes: list):
        if not self.editable:
            return

        copy_text = QtWidgets.QApplication.clipboard().text()

        if copy_text == "":
            return

        if "\n" in copy_text or "\t" in copy_text:
            self.paste_grid_content(copy_text, indexes)
        else:
            # Remove "-marks and remove \n
            copy_text = copy_text.strip('"')

            self.paste_grid_value(copy_text, indexes)

    def paste_grid_value(self, copy_text: str, indexes: list[QtCore.QModelIndex]):
        for index in indexes:
            self.model().setData(
                index,
                copy_text,
                QtCore.Qt.ItemDataRole.EditRole,
            )

        # NOTE: update all rows (not just the cells we updated, since some of the cells might be linked)
        self.model().dataChanged.emit(
            self.model().index(index.row(), 0),
            self.model().index(index.row(), self.model().columnCount())
        )

    def paste_grid_content(self, copy_text: str, indexes: list):
        # NOTE: excel complicates matters, they add a trailing '\n' character
        # This however means we need to do the same, and expect this
        # We need to make sure we catch it here
        row_contents = copy_text[:-1].split("\n")

        init_index = indexes[0]

        visible_rows = [
            r for r in range(self.model().rowCount()) if not self.isRowHidden(r)
        ]

        # Find the index of the row we have selected in our visible rows
        for init_visible_row, r in enumerate(visible_rows):
            if r == init_index.row():
                break
        else:
            return

        usable_rows = visible_rows[
            init_visible_row : init_visible_row + len(row_contents)
        ]

        # Make sure we do not paste outside the window
        if len(usable_rows) != len(row_contents):
            return
        elif (
            init_index.column() + len(row_contents[0].split("\t"))
            > self.model().columnCount()
        ):
            return

        for row, row_content in zip(usable_rows, row_contents):
            col_contents = row_content.split("\t")

            for col, col_content in enumerate(col_contents):
                index = self.model().index(row, init_index.column() + col)

                self.model().setData(
                    index,
                    col_content,
                    QtCore.Qt.ItemDataRole.EditRole,
                )

        # NOTE: update all rows (not just the cells we updated, since some of the cells might be linked)
        self.model().dataChanged.emit(
            self.model().index(min(usable_rows), 0),
            self.model().index(max(usable_rows), self.model().columnCount())
        )

    def _filter_indexes(self, *filters: tuple[str]) -> list[QtCore.QModelIndex]:
        filtered_indexes = []

        for index in self.selectedIndexes():
            flags = self.model().flags(index).name

            if all(f in flags for f in filters):
                filtered_indexes.append(index)

        return filtered_indexes

    def keyPressEvent(self, event):
        if not (indexes := self.selectedIndexes()):
            super().keyPressEvent(event)

        # COPY
        if event.matches(QtGui.QKeySequence.Copy):
            indexes = self._filter_indexes("ItemIsSelectable")

            if len(indexes) == 0:
                return

            self.copy_content(indexes)

        # DELETE
        elif event.key() == QtCore.Qt.Key_Delete:
            if not self.editable:
                return

            for index in indexes:
                self.model().setData(index, "", QtCore.Qt.ItemDataRole.EditRole)

            # NOTE: update all rows (not just the cells we updated, since some of the cells might be linked)
            self.model().dataChanged.emit(
                self.model().index(indexes[0].row(), 0),
                self.model().index(indexes[-1].row(), self.model().columnCount())
            )

        # PASTE
        elif event.matches(QtGui.QKeySequence.Paste):
            self.paste_content(indexes)

        elif event.matches(QtGui.QKeySequence.Cut):
            indexes = self._filter_indexes("ItemIsSelectable")

            if len(indexes) == 0:
                return

            self.cut_content(indexes)

        # OVERFLOW
        else:
            super().keyPressEvent(event)

    def commitData(self, editor):
        super().commitData(editor)

        value = self.model().data(self.currentIndex(), QtCore.Qt.EditRole)

        # Single cell
        if len(self.selectedIndexes()) == 1:
            return

        for index in self.selectedIndexes():
            self.model().setData(
                index,
                value,
                QtCore.Qt.ItemDataRole.EditRole,
            )

            # NOTE: update all rows (not just the cells we updated, since some of the cells might be linked)
            self.model().dataChanged.emit(
                self.model().index(index.row(), 0),
                self.model().index(index.row(), self.model().columnCount())
            )


    # Overwrites
    def model(self, proxy=False) -> QtCore.QAbstractTableModel:
        model: QtCore.QAbstractTableModel = super().model()

        if isinstance(model, QtCore.QSortFilterProxyModel):
            if proxy:
                return model

            return model.sourceModel()
        
        return model
