from PySide6 import QtWidgets


from src.utils.data_objects.sip import SIP
from src.utils.base_object import ApplicationMixin


class GridWidget(QtWidgets.QTableView, ApplicationMixin):
    def __init__(self, sip: SIP) -> None:
        super().__init__()

        self.sip = sip

        self.setSortingEnabled(True)
        
        # NOTE: seems to be the only way to access the select-all corner button
        self.corner: QtWidgets.QPushButton = self.findChild(QtWidgets.QAbstractButton)


    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout(self)
        self.setLayout(self.grid_layout)

        
