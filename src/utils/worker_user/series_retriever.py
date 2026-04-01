"""
This class uses workers to retrieve series in the background.
It contains handlers and the main call to start the worker.
"""

from PySide6 import QtCore

from src.controller.api_controller import APIController
from src.controller.worker_controller import WorkerController

from src.utils.constants import PROD_ENVIRONMENT_NAME, TI_ENVIRONMENT_NAME
from src.utils.data_objects.series import Series
from src.utils.worker_user.worker_user import WorkerUser
from src.utils.workers.worker import Worker


class SeriesRetriever(WorkerUser):
    finished_signal = QtCore.Signal()
    error_occurred_signal = QtCore.Signal(Exception)

    def __init__(self):
        super().__init__()

        self._retrieval_done: dict[str, bool] = {}

        self.application.force_stop_series_retrieval_signal.connect(self.force_stop_handler)

        self.ti_worker: Worker = None
        self.prod_worker: Worker = None

    def run(self, worker_controller: WorkerController) -> None:
        self._retrieval_done = {
            TI_ENVIRONMENT_NAME: False,
            PROD_ENVIRONMENT_NAME: False,
        }
        self.application.series_retrieval_busy = True

        self.ti_worker = self.run_environment_series(worker_controller, TI_ENVIRONMENT_NAME)
        self.prod_worker = self.run_environment_series(worker_controller, PROD_ENVIRONMENT_NAME)

        # NOTE: means they did not run
        if self.ti_worker is None:
            self.series_retrieval_done_handler(TI_ENVIRONMENT_NAME)
        if self.prod_worker is None:
            self.series_retrieval_done_handler(PROD_ENVIRONMENT_NAME)

    def run_environment_series(self, worker_controller: WorkerController, environment_name: str) -> Worker:
        # NOTE: only run if we have to
        if self.application.sneaky_series()[environment_name]:
            return

        environment = self.application.configuration.get_environment(environment_name)

        # TODO: proper error
        if not environment.has_api_credentials():
            return

        worker = worker_controller.run_thread(
            thread_function=lambda: APIController.get_series(environment=environment), thread_is_generator=True
        )

        if worker is None:
            return

        worker.result_ready_signal.connect(
            lambda series: self.new_series_ready_handler(series=series, environment_name=environment_name)
        )
        worker.about_to_finish_signal.connect(
            lambda: self.series_retrieval_done_handler(environment_name=environment_name)
        )
        worker.error_encountered_signal.connect(self.error_occurred_signal.emit)

        return worker

    # Handlers
    def new_series_ready_handler(self, series: list[Series], environment_name: str) -> None:
        self.application.add_series(environment_name=environment_name, series=series)

    def series_retrieval_done_handler(self, environment_name: str) -> None:
        self._retrieval_done[environment_name] = True

        if all(self._retrieval_done.values()):
            self.application.series_retrieval_busy = False
            self.finished_signal.emit()

    def force_stop_handler(self, environment_name: str) -> None:
        worker: Worker = None

        match environment_name:
            case e if e == TI_ENVIRONMENT_NAME:
                worker = self.ti_worker
            case e if e == PROD_ENVIRONMENT_NAME:
                worker = self.prod_worker

        if worker is not None:
            self._retrieval_done[environment_name] = True
            worker.force_stop = True
