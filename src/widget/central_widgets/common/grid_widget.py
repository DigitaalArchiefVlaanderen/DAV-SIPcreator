from PySide6 import QtWidgets


from src.utils.data_objects.sip import SIP

from src.widget.central_widgets.central_widget import CentralWidget


class GridWidget(CentralWidget):
    def __init__(self, sip: SIP) -> None:
        super().__init__()

        self.sip = sip
    
    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout(self)
        self.setLayout(self.grid_layout)
