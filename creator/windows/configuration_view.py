from PySide6 import QtWidgets, QtCore, QtGui

import json


from ..application import Application
from ..controllers.config_controller import ConfigController

from ..utils.path_loader import resource_path

from ..widgets.configuration_tab_widget import (
    MiscConfigurationTab,
    ConnectionConfigurationTab,
)


class ConfigurationWidget(QtWidgets.QMainWindow):
    closed: QtCore.Signal = QtCore.Signal()

    def __init__(self):
        super().__init__()

        self.application: Application = QtWidgets.QApplication.instance()
        self.config_controller: ConfigController = self.application.config_controller

        self.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))

        self.tabs = {}

    def setup_ui(self):
        self.resize(800, 600)
        self.setWindowTitle("Configuratie")

        configuration = self.config_controller.get_configuration()

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        vertical_layout = QtWidgets.QVBoxLayout()
        central_widget.setLayout(vertical_layout)

        tab_widget = QtWidgets.QTabWidget()
        vertical_layout.addWidget(tab_widget)

        self.tabs["misc"] = MiscConfigurationTab(configuration.misc)
        tab_widget.addTab(self.tabs["misc"], "misc")

        for environment in configuration.environments:
            self.tabs[environment.name] = ConnectionConfigurationTab(environment)

            tab_widget.addTab(self.tabs[environment.name], environment.name)

        save_button = QtWidgets.QPushButton(text="Opslaan")
        save_button.clicked.connect(self.save_button_clicked)
        vertical_layout.addWidget(save_button)

    def _write_configuration(self, configuration: dict):
        with open(self.config_controller.configuration_path, "w", encoding="utf-8") as f:
            json.dump(configuration, f, indent=4)

            return configuration

    def save_button_clicked(self):
        configuration = {
            environment: tab.get_tab_info() for environment, tab in self.tabs.items()
        }

        type_changed = False

        if self.tabs["misc"].get_tab_info()["Type SIPs"] != self.application.state.configuration.active_type:
            type_changed = True

        self._write_configuration(configuration)
        self.config_controller.get_configuration().create_locations()

        if type_changed:
            self.application.type_changed.emit()

        self.close()
        self.closed.emit()
