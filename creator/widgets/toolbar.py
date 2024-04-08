from PySide6 import QtWidgets, QtGui

from ..windows.configuration_view import ConfigurationWidget


class Toolbar(QtWidgets.QToolBar):
    def __init__(self):
        super().__init__()

        configuration_action = QtGui.QAction("Configuratie", self)
        configuration_action.triggered.connect(self.configuration_clicked)
        configuration_action.setCheckable(False)
        self.addAction(configuration_action)

        configuration_button = self.widgetForAction(configuration_action)
        configuration_button.setStyleSheet("border: 1px solid black")

        self.configuration_view = ConfigurationWidget()
        self.configuration_view.setup_ui()

    def configuration_clicked(self):
        # Redo the setup to reload in case changes were made
        self.configuration_view.setup_ui()
        self.configuration_view.show()
