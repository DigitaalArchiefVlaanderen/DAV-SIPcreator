from PySide6 import QtGui

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.sip import SIP
from src.widget.central_widgets.digital.digital_grid_view import DigitalGridView
from src.widget.dialog.yes_no_dialog import YesNoDialog
from src.window.base_window import Window

UI_TEXT = UI_TEXT_ELEMENTS["digital"]["grid"]


class GridWindow(Window):
    def __init__(self, sip: SIP) -> None:
        super().__init__()

        self.sip = sip

        self.setWindowTitle(self.sip.name)
        self.resize(1200, 800)

        self.sip.name_changed_signal.connect(lambda: self.setWindowTitle(self.sip.name))

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        grid_view = self.centralWidget()

        if isinstance(grid_view, DigitalGridView) and grid_view.has_unsaved_changes:
            dialog = YesNoDialog(
                title=UI_TEXT["unsaved_changes_dialog"]["title"],
                text=UI_TEXT["unsaved_changes_dialog"]["text"],
            )
            dialog.exec()

            if dialog.result():
                grid_view._save_button_clicked()

        super().closeEvent(event)
