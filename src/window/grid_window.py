from PySide6 import QtCore

from src.utils.data_objects.sip import SIP

from src.window.base_window import Window


class GridWindow(Window):
    def __init__(self, sip: SIP) -> None:
        super().__init__()

        self.sip = sip

        self.setWindowTitle(self.sip.name)
        self.resize(1200, 800)

        self.sip.name_changed_signal.connect(lambda: self.setWindowTitle(self.sip.name))
