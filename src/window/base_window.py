"""
Implementation of the base window as well as a main window.
Each window has a title, nav-bar to navigate to configuration, and an information banner at the bottom of the screen.

The window is to be used as the baseline, with a widget set as the central_widget.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6 import QtWidgets, QtCore, QtGui

from src.utils.constants import get_logo
from src.utils.workers.worker import Worker

from src.widget.components.statusbar import Statusbar
from src.widget.components.toolbar import Toolbar

if TYPE_CHECKING:
    from src.utils.application import Application


class BaseWindow(QtWidgets.QMainWindow):
    window_close_signal = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()

        self.setMinimumWidth(900)
        self.setMinimumHeight(600)
        self.setWindowIcon(get_logo())

        self.application: Application = QtWidgets.QApplication.instance()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        self.window_close_signal.emit()
        super().closeEvent(event)


class Window(BaseWindow):
    IS_MAIN = False

    force_stop_worker_signal = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()

        self.toolbar = Toolbar(self)
        self.addToolBar(self.toolbar)

        self.statusbar = Statusbar(self)
        self.setStatusBar(self.statusbar)

        self.application.register_window(self)

        self.worker: Worker = None

    def force_stop_worker_handler(self) -> None:
        if isinstance(self.worker, Worker):
            self.worker.forcibly_stop_signal.emit()

        self.worker = None


class MainWindow(Window):
    IS_MAIN = True

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        super().closeEvent(event)

        event.accept()
        self.application.quit()
