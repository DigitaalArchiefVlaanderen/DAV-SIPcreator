from PySide6 import QtWidgets

import os
import json

from ..utils.path import is_path_exists_or_creatable
from ..widgets.configuration_tab_widget import (
    MiscConfigurationTab,
    ConnectionConfigurationTab,
)


class ConfigurationWidget(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.configuration_path = "configuration.json"
        self.tabs = {}

    def setup_ui(self):
        self.resize(800, 600)
        self.setWindowTitle("Configuratie")

        configuration = self.get_configuration()

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        vertical_layout = QtWidgets.QVBoxLayout()
        central_widget.setLayout(vertical_layout)

        tab_widget = QtWidgets.QTabWidget()
        vertical_layout.addWidget(tab_widget)

        environments = list(configuration.keys())
        environments.remove("misc")

        for environment, values in configuration.items():
            if environment == "misc":
                self.tabs[environment] = MiscConfigurationTab(values)
            else:
                self.tabs[environment] = ConnectionConfigurationTab(values)

            tab_widget.addTab(self.tabs[environment], environment)

        save_button = QtWidgets.QPushButton(text="Opslaan")
        save_button.clicked.connect(self.save_button_clicked)
        vertical_layout.addWidget(save_button)

    def get_configuration(self):
        if not os.path.exists(self.configuration_path):
            return self._get_default_configuration()

        with open(self.configuration_path, "r", encoding="utf-8") as f:
            configuration = json.load(f)

            if not self._verify_configuration(configuration):
                # NOTE: something in the config is bad
                return self._get_default_configuration()

            return configuration

    def _verify_configuration(self, configuration: dict) -> bool:
        """Verifies the integrity of the configuration"""
        if "misc" not in configuration:
            return False

        for environment, values in configuration.items():
            if not isinstance(values, dict):
                return False

            # NOTE: misc needs a few things
            if environment == "misc":
                if (
                    not "SIP Creator opslag locatie" in values
                    or not "Omgevingen" in values
                ):
                    return False

                if not is_path_exists_or_creatable(
                    values["SIP Creator opslag locatie"]
                ):
                    return False

                if not isinstance(values["Omgevingen"], dict):
                    return False

                active_envs = 0

                for env_active in values["Omgevingen"].values():
                    if not isinstance(env_active, bool):
                        return False

                    if env_active:
                        active_envs += 1

                if active_envs != 1:
                    return False

                continue

            # NOTE: connection details need both API and FTPS for their environment
            if not "API" in values or not "FTPS" in values:
                return False

            # NOTE: make sure the right fields are present
            if any(
                argument not in values["API"]
                for argument in (
                    "url",
                    "username",
                    "password",
                    "client_id",
                    "client_secret",
                )
            ) or any(
                argument not in values["FTPS"]
                for argument in (
                    "url",
                    "username",
                    "password",
                    "port",
                )
            ):
                return False

        return True

    def _get_default_configuration(self):
        return {
            "ti": {
                "API": {
                    "url": "https://digitaalarchief-ti.vlaanderen.be",
                    "username": "",
                    "password": "",
                    "client_id": "",
                    "client_secret": "",
                },
                "FTPS": {
                    "url": "ingest.digitaalarchief-ti.vlaanderen.be",
                    "username": "",
                    "password": "",
                    "port": "21",
                },
            },
            "prod": {
                "API": {
                    "url": "",
                    "username": "",
                    "password": "",
                    "client_id": "",
                    "client_secret": "",
                },
                "FTPS": {
                    "url": "ingest.digitaalarchief.vlaanderen.be",
                    "username": "",
                    "password": "",
                    "port": "21",
                },
            },
            "misc": {
                "SIP Creator opslag locatie": os.path.join(os.getcwd(), "SIP_Creator"),
                "Omgevingen": {
                    "ti": False,
                    "prod": True,
                },
            },
        }

    def _write_configuration(self, configuration: dict):
        with open(self.configuration_path, "w", encoding="utf-8") as f:
            json.dump(configuration, f, indent=4)

            return configuration

    def save_button_clicked(self):
        configuration = {
            environment: tab.get_tab_info() for environment, tab in self.tabs.items()
        }

        self._write_configuration(configuration)

        self.close()
