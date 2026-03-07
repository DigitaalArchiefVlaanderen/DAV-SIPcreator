"""
Toolbar containing one single action, the configuration.
"""
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6 import QtWidgets, QtGui, QtCore

from src.utils.constants import UI_TEXT_ELEMENTS

from src.widget.central_widgets.configuration_widget import ConfigurationWidget

if TYPE_CHECKING:
    from src.utils.application import Application


class Toolbar(QtWidgets.QToolBar):
    def __init__(self, parent: QtWidgets.QMainWindow):
        super().__init__(parent)
        
        self.application: Application = QtWidgets.QApplication.instance()

        configuration_action = QtGui.QAction(UI_TEXT_ELEMENTS["toolbar"]["configuration_button"], self)
        self.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.PreventContextMenu)
        self.addAction(configuration_action)

        configuration_button = self.widgetForAction(configuration_action)
        configuration_button.setStyleSheet("border: 1px solid black")

        configuration_action.triggered.connect(self.configuration_clicked)

        # NOTE: prevent circular import
        from src.window.base_window import BaseWindow

        self.configuration_window = BaseWindow()
        self.configuration_window.setWindowTitle(UI_TEXT_ELEMENTS["window_titles"]["configuration"])
        self.configuration_window.resize(900, 600)

    def configuration_clicked(self):
        # Redo the setup to reload in case changes were made
        self.configuration_widget = ConfigurationWidget()
        self.configuration_widget.save_button_clicked_signal.connect(self.configuration_window.close)
        self.configuration_window.setCentralWidget(self.configuration_widget)

        self.configuration_widget.setup_ui()
        self.configuration_window.show()

