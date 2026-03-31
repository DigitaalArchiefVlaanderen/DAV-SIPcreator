"""
Toolbar containing one single action, the configuration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtCore, QtGui, QtWidgets

from src.utils.constants import UI_TEXT_ELEMENTS

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

    def configuration_clicked(self):
        from src.window.configuration_window import ConfigurationWindow

        self.configuration_window = ConfigurationWindow()
        self.configuration_window.resize(900, 600)
        self.configuration_window.show()
