from src.utils.data_objects.sip import SIP

from src.window.base_window import Window


class GridWindow(Window):
    def __init__(self, sip: SIP) -> None:
        self.sip = sip
        
        self.setup_ui()

    def setup_ui(self) -> None:
        self.setWindowTitle(self.sip.name)

