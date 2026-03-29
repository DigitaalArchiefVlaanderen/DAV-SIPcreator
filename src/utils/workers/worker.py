"""
Base class of a background worker
"""
from typing import Callable

from PySide6 import QtCore


class Worker(QtCore.QObject):
    # NOTE: in the case of a generator, this will be triggered often
    result_ready_signal = QtCore.Signal(object)

    # NOTE: this allows us to grab the results before destroying the worker
    about_to_finish_signal = QtCore.Signal()
    finished_signal = QtCore.Signal()

    forcibly_stop_signal = QtCore.Signal()

    stopped_forcibly_signal = QtCore.Signal()
    error_encountered_signal = QtCore.Signal(Exception)

    def __init__(self, function: Callable, is_generator: bool) -> None:
        super().__init__()

        self.function = function
        self.is_generator = is_generator

        self.force_stop = False

        self.forcibly_stop_signal.connect(self.set_force_stop)

    @staticmethod
    def start(
        function: Callable,
        *,
        is_generator: bool = False,
        on_result: Callable | None = None,
        on_error: Callable | None = None,
        on_finished: Callable | None = None,
        track_in: list | None = None,
    ) -> "Worker":
        worker = Worker(function=function, is_generator=is_generator)
        thread = QtCore.QThread()

        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        if on_result is not None:
            worker.result_ready_signal.connect(on_result)

        if on_error is not None:
            worker.error_encountered_signal.connect(on_error)

        worker.finished_signal.connect(thread.quit)
        worker.stopped_forcibly_signal.connect(thread.quit)
        thread.finished.connect(thread.deleteLater)

        if track_in is not None:
            track_in.append((worker, thread))

            def _remove():
                if (worker, thread) in track_in:
                    track_in.remove((worker, thread))

            worker.finished_signal.connect(_remove)
            worker.stopped_forcibly_signal.connect(_remove)

        if on_finished is not None:
            worker.finished_signal.connect(on_finished)

        thread.start()

        return worker

    def set_force_stop(self):
        self.force_stop = True

    def run(self) -> None:
        try:
            if self.is_generator:
                for result in self.function():
                    if self.force_stop:
                        self.about_to_finish_signal.emit()
                        self.stopped_forcibly_signal.emit()
                        return

                    self.result_ready_signal.emit(result)
            else:
                result = self.function()

                if self.force_stop:
                    self.about_to_finish_signal.emit()
                    self.stopped_forcibly_signal.emit()
                    return

                self.result_ready_signal.emit(result)
        except Exception as e:
            self.error_encountered_signal.emit(e)

        self.about_to_finish_signal.emit()
        self.finished_signal.emit()
