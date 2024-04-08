from PySide6 import QtWidgets, QtCore, QtGui


class TableView(QtWidgets.QTableView):
    GRID_COPY_FLAG = "GRID_COPY"

    def __init__(self):
        super().__init__()

        self.setSortingEnabled(True)

    def copy_content(self):
        index_range = self.selectionModel().selection().first()

        # Single cell copy
        if (
            index_range.bottom() == index_range.top()
            and index_range.left() == index_range.right()
        ):
            QtWidgets.QApplication.clipboard().setText(
                self.model().index(index_range.top(), index_range.left()).data()
            )
            return

        copy_text = TableView.GRID_COPY_FLAG

        for row in range(index_range.top(), index_range.bottom() + 1):
            row_contents = []

            for col in range(index_range.left(), index_range.right() + 1):
                row_contents.append(self.model().index(row, col).data())

            copy_text += "\t".join(row_contents)
            copy_text += "\n"

        QtWidgets.QApplication.clipboard().setText(copy_text)

    def paste_content(self):
        copy_text = QtWidgets.QApplication.clipboard().text()

        if copy_text == "":
            return

        if copy_text.startswith(TableView.GRID_COPY_FLAG):
            self.paste_grid_content(copy_text[len(TableView.GRID_COPY_FLAG) :])
        else:
            self.paste_grid_value(copy_text)

    def paste_grid_value(self, copy_text: str):
        index_range = self.selectionModel().selection().first()

        for row in range(index_range.top(), index_range.bottom() + 1):
            for col in range(index_range.left(), index_range.right() + 1):
                self.model().setData(
                    self.model().index(row, col),
                    copy_text,
                    QtCore.Qt.ItemDataRole.EditRole,
                )

        self.model().dataChanged.emit(
            self.model().index(index_range.top(), index_range.left()),
            self.model().index(index_range.bottom(), index_range.right()),
        )

    def paste_grid_content(self, copy_text: str):
        row_contents = copy_text.split("\n")[:-1]

        init_index = self.selectedIndexes()[0]
        init_row, init_col = init_index.row(), init_index.column()

        # Make sure we do not paste outside the window
        if init_row + len(row_contents) > self.model().rowCount():
            return
        elif init_col + len(row_contents[0].split("\t")) > self.model().columnCount():
            return

        for row, row_content in enumerate(row_contents):
            col_contents = row_content.split("\t")

            for col, col_content in enumerate(col_contents):
                self.model().setData(
                    self.model().index(init_row + row, init_col + col),
                    col_content,
                    QtCore.Qt.ItemDataRole.EditRole,
                )

        self.model().dataChanged.emit(
            init_index,
            self.model().index(
                init_row + len(row_contents),
                init_col + len(row_contents[0].split("\t")),
            ),
        )

    def keyPressEvent(self, event):
        if not (indexes := self.selectedIndexes()):
            super().keyPressEvent(event)

        # DELETE
        if event.key() == QtCore.Qt.Key_Delete:
            for index in indexes:
                self.model().setData(index, "", QtCore.Qt.ItemDataRole.EditRole)

            self.model().dataChanged.emit(indexes[0], indexes[-1])

        # COPY
        elif event.matches(QtGui.QKeySequence.Copy):
            self.copy_content()

        # PASTE
        elif event.matches(QtGui.QKeySequence.Paste):
            self.paste_content()

        # OVERFLOW
        else:
            super().keyPressEvent(event)

    def commitData(self, editor):
        super().commitData(editor)

        value = self.model().data(self.currentIndex(), QtCore.Qt.EditRole)

        index_range = self.selectionModel().selection().first()

        # Single cell
        if (
            index_range.bottom() == index_range.top()
            and index_range.left() == index_range.right()
        ):
            return

        for row in range(index_range.top(), index_range.bottom() + 1):
            for col in range(index_range.left(), index_range.right() + 1):
                self.model().setData(
                    self.model().index(row, col),
                    value,
                    QtCore.Qt.ItemDataRole.EditRole,
                )

        self.model().dataChanged.emit(
            self.model().index(index_range.top(), index_range.left()),
            self.model().index(index_range.bottom(), index_range.right()),
        )
