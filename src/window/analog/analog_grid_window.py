from PySide6 import QtGui

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.analog.sip import AnalogSIP
from src.widget.central_widgets.analog.analog_grid_view import AnalogGridView
from src.widget.dialog.yes_no_dialog import YesNoDialog
from src.window.base_window import Window

UI_TEXT = UI_TEXT_ELEMENTS["analog"]["grid"]


class AnalogGridWindow(Window):
    def __init__(self, sip: AnalogSIP) -> None:
        super().__init__()

        self.sip = sip

        self.setWindowTitle(self.sip.name)
        self.resize(1200, 800)

        self.grid_view = AnalogGridView(sip=self.sip)
        self.setCentralWidget(self.grid_view)

        self.sip.name_changed_signal.connect(lambda: self.setWindowTitle(self.sip.name))
        self.application.application_environment_changed_signal.connect(self.close)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.grid_view.has_unsaved_changes:
            dialog = YesNoDialog(
                title=UI_TEXT["unsaved_changes_dialog"]["title"],
                text=UI_TEXT["unsaved_changes_dialog"]["text"],
            )
            dialog.exec()

            if dialog.result():
                self.grid_view._save_button_clicked(silent=True)

        super().closeEvent(event)
