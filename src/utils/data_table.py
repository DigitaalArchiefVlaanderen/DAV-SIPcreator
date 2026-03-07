from enum import Enum

from pandas import DataFrame
from PySide6 import QtCore, QtGui


from src.utils.base_object import ApplicationMixin
from src.utils.data_objects.sip import SIP



class CellColor(Enum):
    RED = QtGui.QBrush(QtGui.QColor(255, 0, 0))
    YELLOW = QtGui.QBrush(QtGui.QColor(255, 255, 0))
    GREY = QtGui.QBrush(QtGui.QColor(230, 230, 230))


class DataTable(QtCore.QAbstractTableModel, ApplicationMixin):
    known_column_names: list[str] = [
        "Path in SIP",
        "Type",
        "DossierRef",
        "Analoog?",
        "Naam",
        "Beschrijving",
        "Dossiercode_bron",
        "Stukreferentie_Bron",
        "Openingsdatum",
        "Sluitingsdatum",
        "ID_BIS-rijksregisternummer",
        "ID_Rijksregisternummer",
        "ID_Naam",
        "KBO_nummer",
        "OVO_code",
        "Organisatienaam",
        "Trefwoorden_vrij",
        "Opmerkingen",
        "Auteur",
        "Taal",
        "ID Beschrijving",
        "ID Verpakking",
        "Origineel Doosnummer",
        "Legacy locatie ID",
        "Legacy range",
        "Verpakkingstype"
    ]

    def __init__(self, sip: SIP) -> None:
        super().__init__()

        self.sip = sip
        self.raw_data: DataFrame = self.sip.grid_data.data_as_df

        self.markings: dict[tuple[int, int], tuple[CellColor, str]] = {}

    def data_index(self, index) -> tuple[int, int]:
        return self.raw_data.index[index.row()], index.column()

    def rowCount(self) -> int:
        return self.raw_data.shape[0]

    def columnCount(self) -> int:
        return self.raw_data.shape[1]
    
    # Getting of data or cell formatting based on index and role
    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole) -> str | QtGui.QBrush | None:
        if not index.isValid():
            return

        if role in (QtCore.Qt.ItemDataRole.DisplayRole, QtCore.Qt.ItemDataRole.EditRole):
            return self.raw_data.iloc[index.row(), index.column()]

        marking = self.markings.get(self.data_index(index))

        if not marking:
            return

        color, tooltip = marking

        if role == QtCore.Qt.ItemDataRole.BackgroundRole and color:
            return color.value

        if role == QtCore.Qt.ItemDataRole.ToolTipRole and tooltip:
            return tooltip

    def headerData(self, section, orientation, role):
        # section is the index of the column/row.
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            if orientation == QtCore.Qt.Orientation.Horizontal:
                return str(self.raw_data.columns[section])

            if orientation == QtCore.Qt.Orientation.Vertical:
                return str(self.raw_data.index[section])

    def flags(self, index):
        marking = self.markings.get(self.data_index(index))

        if marking and marking[0] in (CellColor.YELLOW, CellColor.GREY):
            return QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEnabled

        return (
            QtCore.Qt.ItemFlag.ItemIsSelectable
            | QtCore.Qt.ItemFlag.ItemIsEnabled
            | QtCore.Qt.ItemFlag.ItemIsEditable
        )


    def disable_column(self, column_name: str, tooltip: str="") -> "DataTable":
        self.markings.update(
            {
                (row, self.raw_data.columns.get_loc(column_name)): (CellColor.GREY, tooltip)
                for row in self.raw_data.index
            }
        )

        return self

    def check_entered_value(self, index, value: str) -> str | None:
        """
        The value should be checked based on index.
        The new value to be put at that index should be returned, or None if the value is not valid.
        """
        raise NotImplementedError("Method not implemented")


    def setData(self, index, value: str, role=QtCore.Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        if role != QtCore.Qt.ItemDataRole.EditRole:
            return False

        value = str(value).encode(encoding="utf-8", errors="replace").decode("utf-8")
        if (new_value := self.check_entered_value(index, value)):
            self.raw_data.iat[index.row(), index.column()] = new_value

        self.dataChanged.emit(index, index)

        return True


    def unmark_cell(self, index) -> None:
        if self.data_index(index) in self.markings:
            del self.markings[self.data_index(index)]

    def mark_cell(self, index, warning: bool=False, tooltip: str="") -> None:
        marking = self.markings.get(self.data_index(index))
        
        color = CellColor.YELLOW if warning else CellColor.RED

        if marking:
            old_color, old_tooltip = marking

            color = color or old_color
            tooltip = tooltip or old_tooltip

        self.markings[self.data_index(index)] = (color, tooltip)


    @property
    def has_bad_rows(self) -> bool:
        return any(
            marking[0] == CellColor.RED
            for marking in self.markings.values()
        )
    
    @property
    def bad_rows(self) -> list[int]:
        return list(
            set(
                row
                for (row, _), marking in self.markings.items()
                if marking[0] == CellColor.RED
            )
        )

