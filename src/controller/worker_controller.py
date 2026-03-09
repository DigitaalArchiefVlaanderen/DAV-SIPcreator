"""
Controller of background workers
"""
from typing import Callable

from PySide6 import QtCore

from src.utils.base_object import BaseObject
from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.workers.worker import Worker

UI_TEXT = UI_TEXT_ELEMENTS["errors"]


class WorkerController(BaseObject):
    def __init__(self) -> None:
        super().__init__()

        self.active_workers: list[Worker] = []
        self.active_threads: list[QtCore.QThread] = []

    def close_controller(self) -> None:
        for worker in self.active_workers[:]:
            worker.force_stop = True

        for thread in self.active_threads[:]:
            thread.quit()

        for thread in self.active_threads[:]:
            thread.wait()

    def run_thread(self, thread_function: Callable, thread_is_generator: bool) -> Worker:
        if not self.application.configuration.active_environment.has_api_credentials():
            self.application.notify_user_signal.emit(
                UI_TEXT["api"]["missing_credentials_error"]["title"],
                UI_TEXT["api"]["missing_credentials_error"]["text"],
            )

            return

        worker = Worker(function=thread_function, is_generator=thread_is_generator)
        thread = QtCore.QThread()

        worker.moveToThread(thread)
        self.active_threads.append(thread)
        self.active_workers.append(worker)

        thread.started.connect(worker.run)

        worker.finished_signal.connect(thread.quit)
        worker.finished_signal.connect(thread.deleteLater)
        worker.finished_signal.connect(lambda: self.active_threads.remove(thread))
        worker.finished_signal.connect(lambda: self.active_workers.remove(worker))
        worker.stopped_forcibly_signal.connect(thread.quit)
        worker.stopped_forcibly_signal.connect(thread.deleteLater)
        worker.stopped_forcibly_signal.connect(lambda: self.active_threads.remove(thread))
        worker.stopped_forcibly_signal.connect(lambda: self.active_workers.remove(worker))

        thread.start()

        return worker
