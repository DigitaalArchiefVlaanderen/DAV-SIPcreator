from collections.abc import Iterator

from PySide6 import QtCore

from src.utils.worker_user.worker_user import WorkerUser
from src.utils.workers.worker import Worker


class BaseRetriever(WorkerUser):
    error_occurred_signal = QtCore.Signal(Exception)

    def __init__(self):
        super().__init__()

        self.worker: Worker = None

    def run(self) -> None:
        self.worker = self.application.worker_controller.run_thread(
            thread_function=self._load_sips, thread_is_generator=True
        )

        if self.worker is None:
            return

        self.worker.error_encountered_signal.connect(self.error_occurred_signal.emit)

    def _load_sips(self) -> Iterator[None]:
        raise NotImplementedError
