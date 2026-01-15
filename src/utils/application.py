"""
Implementation of the main application
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6 import QtWidgets, QtCore

from src.controller.config_controller import ConfigController
from src.controller.worker_controller import WorkerController

from src.utils.configuration import Configuration

from src.widget.dialog.warning_dialog import WarningDialog

from src.utils import constants


from creator.controllers.config_controller import ConfigController as OldConfigController
from creator.controllers.db_controller import DBController
from creator.utils.state import State
from creator.application import SIPStatusThread, BestandsControleLijstController

if TYPE_CHECKING:
    import requests

    from src.window.base_window import Window


class Application(QtWidgets.QApplication):
    # TODO: temp
    type_changed = QtCore.Signal()

    application_type_changed_signal = QtCore.Signal()
    application_environment_changed_signal = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()

        # Keep a reference to the windows
        self.windows: list[Window] = []

        self.series = {
            e.name: []
            for e
            in self.configuration.environments
        }

        self.worker_controller = WorkerController(self)
        self.worker_controller.error_signal.connect(self.error_handler)

        self.aboutToQuit.connect(self.worker_controller.close_controller)
        
        # TODO: temporary
        self.type_changed.connect(self.application_type_changed_signal.emit)
        self.config_controller = OldConfigController(constants.CONFIGURATION_PATH)

        self.db_controller = DBController("sqlite.db")
        self.state = State(
            configuration_callback=self.config_controller.get_configuration,
            db_controller=self.db_controller,
        )
        self.state.set_series(self.series[self.configuration.active_environment_name])
        self.application_environment_changed_signal.connect(lambda: self.state.set_series(self.series[self.configuration.active_environment_name]))

        self.db_controller.set_application()

        self.sip_status_thread = SIPStatusThread(self.state)
        
        controle_list_path = self.state.configuration.misc.bestandscontrole_lijst_location
        self.bestands_controle_lijst_controller = BestandsControleLijstController(controle_list_path=controle_list_path)

    @property
    def configuration(self) -> Configuration:
        return ConfigController.get_configuration()

    def register_window(self, window: Window) -> None:
        self.windows.append(window)
        window.window_close_signal.connect(lambda: self.windows.remove(window))

        set_statusbar_text = lambda finished: window.statusbar.set_left_text(f"series ==> {constants.TI_ENVIRONMENT_NAME}: {len(self.series[constants.TI_ENVIRONMENT_NAME])} | {constants.PROD_ENVIRONMENT_NAME}: {len(self.series[constants.PROD_ENVIRONMENT_NAME])} {'...' if not finished else ''}")

        self.worker_controller.series_updated_signal.connect(lambda: set_statusbar_text(finished=False))
        self.worker_controller.finished_series_retrieval_signal.connect(lambda: set_statusbar_text(finished=True))

        set_statusbar_text(finished=False)

    def warn_user(self, title: str, text: str) -> None:
        WarningDialog(
            title=title,
            text=text,
        ).exec()

    def error_handler(self, exception: Exception) -> None:
        title = constants.UI_TEXT_ELEMENTS["errors"]["unexpected_error"]
        text = str(exception)

        if isinstance(exception, requests.exceptions.Timeout):
            title = "Timeout"
            text = constants.UI_TEXT_ELEMENTS["api"][title]

        elif isinstance(exception, requests.exceptions.HTTPError):
            title = "HTTPError"
            text = constants.UI_TEXT_ELEMENTS["api"][title]

        elif isinstance(exception, requests.exceptions.RequestException):
            title = "Fout"
            text = constants.UI_TEXT_ELEMENTS["api"][title]

        self.warn_user(
            title=title,
            text=text,
        )

    # TODO: temp
    def reset_bestandscontrole_location(self) -> None:
        controle_list_path = self.state.configuration.misc.bestandscontrole_lijst_location

        if controle_list_path == self.bestands_controle_lijst_controller.controle_list_path:
            return

        self.bestands_controle_lijst_controller = BestandsControleLijstController(controle_list_path=controle_list_path)

