"""
Background worker for API calls
"""
from enum import Enum
from typing import Callable
from functools import partial

from PySide6 import QtCore

from src.controller.api_controller import APIController

from src.utils.workers.worker import Worker


# NOTE: if we do not use partial, it seems that it silently does not add the key-value pair
class APICall(Enum):
    GET_SERIES = partial(APIController.get_series)


class APIWorker(Worker):
    result_ready = QtCore.Signal(object)

    def __init__(self, api_call: APICall, /, *args, **kwargs) -> None:
        super().__init__()

        self.api_call = api_call
        self.args = args
        self.kwargs = kwargs
        
        if not self.api_call in APICall:
            raise ValueError()

    def run(self) -> None:
        print("Started running APIWorker thread for", self.api_call.name)

        try:
            self.api_call_function: Callable = self.api_call.value

            for result in self.api_call_function(*self.args, **self.kwargs):
                if self.force_stop:
                    break

                self.result_ready.emit(result)
        finally:
            print("Finished running APIWorker thread for", self.api_call.name)
            self.finished.emit()
