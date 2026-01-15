"""
Toolbar containing one single action, the configuration.
"""
from PySide6 import QtWidgets, QtGui, QtCore

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.application import Application

from creator.windows.configuration_view import ConfigurationWidget


class Toolbar(QtWidgets.QToolBar):
    # TODO: temp
    configuration_changed = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QMainWindow):
        super().__init__(parent)

        configuration_action = QtGui.QAction(UI_TEXT_ELEMENTS["toolbar"]["configuration_button"], self)
        configuration_action.setCheckable(False)
        self.addAction(configuration_action)

        configuration_button = self.widgetForAction(configuration_action)
        configuration_button.setStyleSheet("border: 1px solid black")

        # TODO: temp
        self.application: Application = QtWidgets.QApplication.instance()

        configuration_action.triggered.connect(self.configuration_clicked)

        self.configuration_view = ConfigurationWidget()
        self.configuration_view.closed.connect(self.configuration_changed.emit)
        self.configuration_changed.connect(self.application.reset_bestandscontrole_location)

    def configuration_clicked(self):
        # Redo the setup to reload in case changes were made
        self.configuration_view.setup_ui()
        self.configuration_view.show()

