from enum import Enum

from PySide6 import QtCore, QtGui


class CellColor(Enum):
    RED = QtGui.QBrush(QtGui.QColor(255, 0, 0))
    YELLOW = QtGui.QBrush(QtGui.QColor(255, 255, 0))
    GREY = QtGui.QBrush(QtGui.QColor(230, 230, 230))


class TableModel(QtCore.QAbstractTableModel):
    def row_is_dossier(self, row: int) -> bool:
        raise NotImplementedError("Method not implemented")

    def row_is_bad(self, row: int) -> bool:
        raise NotImplementedError("Method not implemented")

    def row_has_no_series(self, row: int) -> bool:
        raise NotImplementedError("Method not implemented")    
