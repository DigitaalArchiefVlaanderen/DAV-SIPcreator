"""
Controller of background workers
"""
from typing import Callable

from src.utils.base_object import BaseObject
from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.workers.worker import Worker

UI_TEXT = UI_TEXT_ELEMENTS["errors"]


class WorkerController(BaseObject):
    def __init__(self) -> None:
        super().__init__()

        self.active_pairs: list[tuple[Worker, ...]] = []
        self.credentials_warning_shown = False

    def close_controller(self) -> None:
        for worker, _ in self.active_pairs[:]:
            worker.force_stop = True

        for _, thread in self.active_pairs[:]:
            thread.quit()

        for _, thread in self.active_pairs[:]:
            thread.wait()

    def run_thread(self, thread_function: Callable, thread_is_generator: bool) -> Worker:
        if not self.application.configuration.active_environment.has_api_credentials():
            if not self.credentials_warning_shown:
                self.credentials_warning_shown = True

                self.application.notify_user_signal.emit(
                    UI_TEXT["api"]["missing_credentials_error"]["title"],
                    UI_TEXT["api"]["missing_credentials_error"]["text"],
                )

            return

        return Worker.start(
            function=thread_function,
            is_generator=thread_is_generator,
            track_in=self.active_pairs,
        )
