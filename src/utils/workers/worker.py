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

    def set_force_stop(self):
        self.force_stop = True

    def run(self) -> None:
        try:
            if self.is_generator:
                for result in self.function():
                    if self.force_stop:
                        self.stopped_forcibly_signal.emit()
                        return

                    self.result_ready_signal.emit(result)
            else:
                result = self.function()

                if self.force_stop:
                    self.stopped_forcibly_signal.emit()
                    return

                self.result_ready_signal.emit(result)
        except Exception as e:
            self.error_encountered_signal.emit(e)

        self.about_to_finish_signal.emit()
        self.finished_signal.emit()
