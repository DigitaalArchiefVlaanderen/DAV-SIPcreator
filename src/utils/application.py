"""
Implementation of the main application
"""
import requests
from typing import Callable

from PySide6 import QtWidgets, QtCore

from src.controller.config_controller import ConfigController
from src.controller.main_db_controller import MainDBController
from src.controller.digital.sip_db_controller import DigitalSIPDBController
from src.controller.worker_controller import WorkerController
from src.controller.window_controller import WindowController

from src.utils.constants import UI_TEXT_ELEMENTS, TI_ENVIRONMENT_NAME, PROD_ENVIRONMENT_NAME
from src.utils.data_objects.configuration import Configuration
from src.utils.data_objects.series import Series
from src.utils.data_objects.sip import SIP
from src.utils.pyside_helper import Helper
from src.utils.worker_user.series_retriever import SeriesRetriever
from src.utils.worker_user.digital.sip_retriever import DigitalSIPRetriever
from src.utils.workers.worker import Worker

from src.widget.dialog.warning_dialog import WarningDialog

from src.window.base_window import Window

from creator.application import BestandsControleLijstController


# NOTE: if you're wondering why this even exists
# Let's say you have an exception that we already expect, so we catch it
# In catching it, we warn the user using application.warn_user
# But we still want execution to stop, without returning
# This is in case where we are deep into code, or need a return value normally
# Raising this will stop execution, but also cause no noticable change for the user
class IgnorableException(Exception):
    pass

UI_ERROR_TEXT = UI_TEXT_ELEMENTS["errors"]


class Application(QtWidgets.QApplication):
    application_type_changed_signal = QtCore.Signal()
    application_role_changed_signal = QtCore.Signal()
    application_environment_changed_signal = QtCore.Signal()

    series_updated_signal = QtCore.Signal()
    force_stop_series_retrieval_signal = QtCore.Signal(str, arguments=["environment_name"])

    digital_sip_loaded_signal = QtCore.Signal(object)

    work_in_progress_signal = QtCore.Signal((Window, str), arguments=["window", "description"])
    work_ended_signal = QtCore.Signal(Window)

    notify_user_signal = QtCore.Signal((str, str), arguments=["title", "text"])

    def __init__(self) -> None:
        super().__init__()

        self.configuration: Configuration = ConfigController.get_configuration()

        # Keep a reference to the windows
        self.windows: list[Window] = []

        self.__series: dict[str, list[Series]] = {
            e.name: []
            for e
            in self.configuration.environments
        }

        self.main_db_controller = MainDBController()
        self.digital_sip_db_controller = DigitalSIPDBController()
        self.worker_controller = WorkerController()
        self.series_retriever = SeriesRetriever()
        self.digital_sip_retriever = DigitalSIPRetriever()
        self.window_controller = WindowController()

        self.sips: dict[type[SIP], dict[str, list[SIP]]] = {}

        self.dialogs: list[QtWidgets.QDialog] = []

        self.setup_signals()
        self.series_retrieval_busy = False

        # NOTE: these things need to happen at startup
        self.configuration.create_locations()
        self.get_series()
        self.load_sips()

        # self.reset_bestandscontrole_location()

    # NOTE: some parts of the code need access to the dict, even if it's empty
    # shhhh don't tell anyone
    def sneaky_series(self) -> dict[str, list[Series]]:
        return self.__series

    @property
    def series(self) -> dict[str, list[Series]]:
        Helper().wait_for_series_loaded(warn=False)
        return self.__series

    def clear_series(self, environment_name: str) -> None:
        self.__series[environment_name] = []

    def add_series(self, environment_name: str, series: list[Series]) -> None:
        self.__series[environment_name] += series
        self.series_updated_signal.emit()

    def setup_signals(self) -> None:
        self.aboutToQuit.connect(self.configuration.save)
        self.aboutToQuit.connect(self.digital_sip_db_controller.persist_all_sips)
        self.aboutToQuit.connect(self.worker_controller.close_controller)

        self.series_retriever.error_occurred_signal.connect(self.error_handler)

        self.window_controller.open_digital_grid_signal.connect(
            self.window_controller.sip_creator_window.digital_widget.open_grid_handler
        )

        self.work_in_progress_signal.connect(self.start_work_handler)
        self.work_ended_signal.connect(self.stop_work_handler)

        self.notify_user_signal.connect(lambda title, text: self.warn_user(title, text))


    # Utils
    def register_window(self, window: Window) -> None:
        self.windows.append(window)
        window.window_about_to_close_signal.connect(lambda: self.windows.remove(window))

        if window.IS_MAIN:
            self.series_updated_signal.connect(
                lambda: window.statusbar.set_left_text(
                    UI_TEXT_ELEMENTS["toolbar_info"]["series_retrieval_in_progress"]["left_text"].format(
                        ti_env_name=TI_ENVIRONMENT_NAME,
                        ti_amount_of_series=len(self.sneaky_series()[TI_ENVIRONMENT_NAME]),
                        prod_env_name=PROD_ENVIRONMENT_NAME,
                        prod_amount_of_series=len(self.sneaky_series()[PROD_ENVIRONMENT_NAME])
                    )
                )
            )

            self.series_retriever.finished_signal.connect(
                lambda: window.statusbar.set_left_text(
                    UI_TEXT_ELEMENTS["toolbar_info"]["series_retrieval_done"]["left_text"].format(
                        ti_env_name=TI_ENVIRONMENT_NAME,
                        ti_amount_of_series=len(self.sneaky_series()[TI_ENVIRONMENT_NAME]),
                        prod_env_name=PROD_ENVIRONMENT_NAME,
                        prod_amount_of_series=len(self.sneaky_series()[PROD_ENVIRONMENT_NAME])
                    )
                )
            )

    def get_series(self) -> None:
        self.series_retriever.run(worker_controller=self.worker_controller)

    def load_sips(self) -> None:
        self.digital_sip_retriever.digital_sip_loaded_signal.connect(self.digital_sip_loaded_signal.emit)
        self.digital_sip_retriever.error_occurred_signal.connect(self.error_handler)
        self.digital_sip_retriever.run()

    def add_sip(self, sip: SIP) -> None:
        sip.moveToThread(self.thread())

        sip_type = type(sip)

        if sip_type not in self.sips:
            self.sips[sip_type] = {}

        env_name = sip.environment.name
        self.sips[sip_type].setdefault(env_name, []).append(sip)

    def get_sips(self, sip_type: type[SIP], environment_name: str = None) -> list[SIP]:
        env = environment_name or self.configuration.active_environment_name

        return self.sips.get(sip_type, {}).get(env, [])

    def get_series_by_id_or_name(self, environment_name: str, series_id: str, series_name: str, warn: bool = True) -> Series | None:
        for series in self.series[environment_name]:
            if series._id == series_id:
                return series

            if series.get_full_name() == series_name:
                return series

            elif series.name == series_name:
                return series

        if warn:
            self.notify_user_signal.emit(
                UI_ERROR_TEXT["series"]["series_not_found_error"]["title"],
                UI_ERROR_TEXT["series"]["series_not_found_error"]["text"].format(
                    series_id=series_id,
                    series_name=series_name,
                    environment_name=environment_name
                )
            )

        return None

    def warn_user(self, title: str, text: str) -> None:
        d = WarningDialog(
            title=title,
            text=text
        )

        self.dialogs.append(d)
        d.finished.connect(lambda: self.dialogs.remove(d))

        d.open()

    # Task
    def start_task(self, window: Window, description: str, function: Callable, is_generator: bool) -> Worker:
        self.work_in_progress_signal.emit(window, description)
        window.worker = self.worker_controller.run_thread(
            thread_function=function,
            thread_is_generator=is_generator
        )
        window.worker.about_to_finish_signal.connect(
            lambda: self.work_ended_signal.emit(window)
        )

        return window.worker


    # Handlers
    def error_handler(self, exception: Exception) -> None:
        if isinstance(exception, IgnorableException):
            return

        # NOTE: this refers to a dict in the UI_TEXT_ELEMENTS for one specific error
        # We will later use this to get title/text
        error_mapping = {
            requests.exceptions.Timeout: UI_ERROR_TEXT["api"]["Timeout"],
            requests.exceptions.HTTPError: UI_ERROR_TEXT["api"]["HTTPError"],
            requests.exceptions.RequestException: UI_ERROR_TEXT["api"]["APIError"]
        }

        title_and_text = error_mapping.get(exception)

        if title_and_text is None:
            title = UI_ERROR_TEXT["unexpected_error"]["title"]
            text = UI_ERROR_TEXT["unexpected_error"]["text"].format(exception_name=type(exception).__name__, exception=exception)
        else:
            title = title_and_text["title"]
            text = title_and_text["text"]

        self.notify_user_signal.emit(
            title,
            text
        )

    def start_work_handler(self, window: Window, description: str) -> None:
        if window not in self.windows:
            raise ValueError("Tried to access a window that does not seem to exist? How did you manage that?")

        window.statusbar.set_right_text(description)

    def stop_work_handler(self, window: Window) -> None:
        # NOTE: this can happen sometimes if an action was queued, then immediately closing the window
        if window not in self.windows:
            return

        window.statusbar.set_right_text("")

    def reset_bestandscontrole_location(self) -> None:
        controle_list_path = self.configuration.misc.bestandscontrole_lijst_location

        if controle_list_path == self.bestands_controle_lijst_controller.controle_list_path:
            return

        self.bestands_controle_lijst_controller = BestandsControleLijstController(controle_list_path=controle_list_path)

