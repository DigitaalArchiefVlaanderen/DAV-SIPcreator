"""
Controller of background workers
"""
from __future__ import annotations
from typing import Callable, TYPE_CHECKING

from PySide6 import QtCore

from src.utils.constants import PROD_ENVIRONMENT_NAME, TI_ENVIRONMENT_NAME
from src.utils.series import Series
from src.utils.workers.api_worker import APICall, APIWorker, Worker

if TYPE_CHECKING:
    from src.utils.application import Application


class WorkerController(QtCore.QObject):
    series_updated_signal = QtCore.Signal()
    finished_series_retrieval_signal = QtCore.Signal()
    error_signal = QtCore.Signal(Exception)

    def __init__(self, parent: Application) -> None:
        super().__init__(parent)

        self.application = parent

        self.active_workers: list[Worker] = []
        self.active_threads: list[QtCore.QThread] = []

        self.series_retrieval_done = {
            TI_ENVIRONMENT_NAME : False,
            PROD_ENVIRONMENT_NAME : False,
        }

    def close_controller(self) -> None:
        # Ensure clean stopping of workers and threads
        for worker in self.active_workers[:]:
            worker.force_stop = True
        
        for thread in self.active_threads[:]:
            thread.quit()

        for thread in self.active_threads[:]:
            thread.quit()


    # API based threads
    def run_api_thread(self, result_handler: Callable, api_call: APICall, /, *args, **kwargs) -> Worker:
        if not self.application.configuration.active_environment.has_api_credentials():
            return

        worker = APIWorker(api_call, *args, **kwargs)
        thread = QtCore.QThread()

        worker.moveToThread(thread)
        self.active_threads.append(thread)
        self.active_workers.append(worker)

        thread.started.connect(worker.run)

        worker.result_ready.connect(result_handler)
        worker.finished.connect(thread.quit)
        worker.finished.connect(thread.deleteLater)
        worker.finished.connect(lambda: self.active_threads.remove(thread))
        worker.finished.connect(lambda: self.active_workers.remove(worker))

        thread.start()

        return worker

    def ti_series_retrieval_handler(self, series: list[Series], *args) -> None:
        if not isinstance(series, list) or any(not isinstance(s, Series) for s in series):
            raise ValueError(f"Received bad result when expecting to receive list of Series\n\n{type(series)}\n\n{series}")

        self.application.series[TI_ENVIRONMENT_NAME] += series
        self.series_updated_signal.emit()

    def prod_series_retrieval_handler(self, series: list[Series], *args) -> None:
        if not isinstance(series, list) or any(not isinstance(s, Series) for s in series):
            raise ValueError(f"Received bad result when expecting to receive list of Series\n\n{type(series)}\n\n{series}")

        self.application.series[PROD_ENVIRONMENT_NAME] += series
        self.series_updated_signal.emit()

    def series_retrieval_done_handler(self, environment_name: str) -> None:
        self.series_retrieval_done[environment_name] = True

        if self.series_retrieval_done[TI_ENVIRONMENT_NAME] and self.series_retrieval_done[PROD_ENVIRONMENT_NAME]:
            self.finished_series_retrieval_signal.emit()


    def get_all_series(self) -> None:
        ti_environment = [e for e in self.application.configuration.environments if e.name == TI_ENVIRONMENT_NAME][0]
        prod_environment = [e for e in self.application.configuration.environments if e.name == PROD_ENVIRONMENT_NAME][0]

        ti_worker = self.run_api_thread(
            self.ti_series_retrieval_handler,
            APICall.GET_SERIES,

            environment=ti_environment,
        )
        prod_worker = self.run_api_thread(
            self.prod_series_retrieval_handler,
            APICall.GET_SERIES,

            environment=prod_environment,
        )

        ti_worker.finished.connect(lambda: self.series_retrieval_done_handler(environment_name=TI_ENVIRONMENT_NAME))
        prod_worker.finished.connect(lambda: self.series_retrieval_done_handler(environment_name=PROD_ENVIRONMENT_NAME))
