"""
Controller of background workers
"""
from typing import Callable

from src.utils.base_object import BaseObject
from src.utils.workers.worker import Worker


class WorkerController(BaseObject):
    def __init__(self) -> None:
        super().__init__()

        self.active_pairs: list[tuple[Worker, ...]] = []

    def close_controller(self) -> None:
        for worker, _ in self.active_pairs[:]:
            worker.force_stop = True

        for _, thread in self.active_pairs[:]:
            thread.quit()

        for _, thread in self.active_pairs[:]:
            thread.wait()

    def run_thread(self, thread_function: Callable, thread_is_generator: bool) -> Worker:
        return Worker.start(
            function=thread_function,
            is_generator=thread_is_generator,
            track_in=self.active_pairs,
        )
