from PySide6 import QtGui, QtWidgets

from src.utils.constants import UI_TEXT_ELEMENTS, get_logo
from src.utils.data_objects.sip_status import SIPStatus

UI_TEXT = UI_TEXT_ELEMENTS["migration"]["tab_status_dialog"]


class MigrationTabStatusDialog(QtWidgets.QDialog):
    def __init__(self, series_statuses: dict[str, SIPStatus]):
        super().__init__()

        self.resize(450, 300)
        self.setWindowTitle(UI_TEXT["title"])
        self.setWindowIcon(get_logo())

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        table = QtWidgets.QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels([UI_TEXT["series_column"], UI_TEXT["status_column"]])
        table.setRowCount(len(series_statuses))
        table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setStretchLastSection(True)
        table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)

        for row, (series_name, status) in enumerate(series_statuses.items()):
            name_item = QtWidgets.QTableWidgetItem(series_name)
            table.setItem(row, 0, name_item)

            status_item = QtWidgets.QTableWidgetItem(status.status_label)
            status_item.setForeground(QtGui.QBrush(QtGui.QColor(status.value.split(":")[1].strip().rstrip(";"))))
            table.setItem(row, 1, status_item)

        layout.addWidget(table)

        ok_button = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
        ok_button.accepted.connect(self.accept)
        layout.addWidget(ok_button)
