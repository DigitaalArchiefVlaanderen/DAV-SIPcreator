from PySide6 import QtWidgets, QtGui

from creator.application import Application

from creator.widgets.main_widgets.main_widget import MainWidget
from creator.widgets.toolbar import Toolbar
from creator.widgets.warning_dialog import WarningDialog

from creator.utils.state import State
from creator.utils.sip_status import SIPStatus
from creator.utils.path_loader import resource_path


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self.central_widget: MainWidget = None

        self.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))

        # Toolbar
        self.toolbar = Toolbar()
        self.addToolBar(self.toolbar)

    def closeEvent(self, event):
        # If the main window dies, kill the whole application
        if any(
            s.status == SIPStatus.UPLOADING
            for s in self.application.db_controller.read_sips()
        ):
            WarningDialog(
                title="Upload bezig",
                text="Waarschuwing, een upload is momenteel bezig, de applicatie kan niet gesloten worden.",
            ).exec()

            event.ignore()
            return

        event.accept()
        self.application.quit()
