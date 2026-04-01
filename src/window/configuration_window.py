from PySide6 import QtGui

from src.utils.constants import UI_TEXT_ELEMENTS

from src.widget.central_widgets.configuration_widget import ConfigurationWidget
from src.widget.dialog.yes_no_dialog import YesNoDialog

from src.window.base_window import BaseWindow

UI_TEXT = UI_TEXT_ELEMENTS["configuration"]


class ConfigurationWindow(BaseWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(UI_TEXT_ELEMENTS["window_titles"]["configuration"])

        self.setup_ui()

    def setup_ui(self) -> None:
        self.configuration_widget = ConfigurationWidget()
        self.setCentralWidget(self.configuration_widget)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.configuration_widget.has_changes():
            dialog = YesNoDialog(
                title=UI_TEXT["save_on_close_dialog"]["title"],
                text=UI_TEXT["save_on_close_dialog"]["text"],
            )
            dialog.exec()

            if dialog.result():
                self.configuration_widget.save()

        super().closeEvent(event)
