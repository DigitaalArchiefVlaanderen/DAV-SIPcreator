from PySide6 import QtWidgets, QtCore, QtGui

from src.utils.base_object import ApplicationMixin


class Table(QtWidgets.QTableView, ApplicationMixin):
    def __init__(self) -> None:
        super().__init__()

        self.is_editable = True

        self.setSortingEnabled(True)
        
        # NOTE: seems to be the only way to access the select-all corner button
        self.corner: QtWidgets.QPushButton = self.findChild(QtWidgets.QAbstractButton)

    def model(self, proxy=False) -> QtCore.QAbstractTableModel:
        model: QtCore.QAbstractTableModel = super().model()

        if isinstance(model, QtCore.QSortFilterProxyModel):
            if proxy:
                return model

            return model.sourceModel()
        
        return model

