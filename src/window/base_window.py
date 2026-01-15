"""
Implementation of the base window as well as a main window.
Each window has a title, nav-bar to navigate to configuration, and an information banner at the bottom of the screen.

The window is to be used as the baseline, with a widget set as the central_widget.
"""
from PySide6 import QtWidgets, QtCore, QtGui

from src.utils.application import Application
from src.utils.constants import get_logo

from src.widget.statusbar import Statusbar
from src.widget.toolbar import Toolbar

from creator.widgets.main_widgets.main_widget import MainWidget


class Window(QtWidgets.QMainWindow):
    window_close_signal = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()

        self.resize(800, 600)
        self.setWindowIcon(get_logo())

        self.toolbar = Toolbar(self)
        self.addToolBar(self.toolbar)

        self.statusbar = Statusbar(self)
        self.setStatusBar(self.statusbar)

        self.application: Application = QtWidgets.QApplication.instance()

        # TODO: temp
        self.central_widget: MainWidget = None

        self.toolbar.configuration_changed.connect(self.application.application_environment_changed_signal.emit)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.window_close_signal.emit()
        super().closeEvent(event)

class MainWindow(Window):
    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        super().closeEvent(event)

        event.accept()
        self.application.quit()
