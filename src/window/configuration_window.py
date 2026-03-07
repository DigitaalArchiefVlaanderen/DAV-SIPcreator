from src.utils.constants import UI_TEXT_ELEMENTS

from src.widget.central_widgets.configuration_widget import ConfigurationWidget

from src.window.base_window import BaseWindow


class ConfigurationWindow(BaseWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(UI_TEXT_ELEMENTS["window_titles"]["configuration"])

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.configuration_widget = ConfigurationWidget()
        self.setCentralWidget(self.configuration_widget)

    def setup_signals(self) -> None:
        self.configuration_widget.save_button_clicked_signal.connect(self.close)
