import time
from typing import Iterator

from PySide6 import QtCore

from src.controller.api_controller import APIController
from src.controller.worker_controller import WorkerController

from src.utils.constants import CHECKABLE_SIP_STATUSES, POLL_INTERVAL_SECONDS
from src.utils.data_objects.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.worker_user.worker_user import WorkerUser
from src.utils.workers.worker import Worker


class SIPStatusChecker(WorkerUser):
    status_changed_signal = QtCore.Signal(SIP, SIPStatus)
    sip_rejected_signal = QtCore.Signal(SIP, str)
    error_occurred_signal = QtCore.Signal(Exception)

    def __init__(self):
        super().__init__()

        self.active_workers: dict[SIP, Worker] = {}
        self.worker_controller: WorkerController = None

        self.application.force_stop_series_retrieval_signal.connect(lambda _: self.force_stop_all())

    def _poll_sip_status(self, sip: SIP) -> Iterator[tuple[SIPStatus, str|None]]:
        while sip.status in CHECKABLE_SIP_STATUSES:
            yield APIController.get_sip_status(sip)

            time.sleep(POLL_INTERVAL_SECONDS)

    def check_sip(self, sip: SIP, worker_controller: WorkerController) -> None:
        if sip.edepot_sip_id is None:
            return

        if sip in self.active_workers:
            return

        self.worker_controller = worker_controller

        worker = worker_controller.run_thread(
            thread_function=lambda: self._poll_sip_status(sip),
            thread_is_generator=True
        )

        self.active_workers[sip] = worker

        worker.result_ready_signal.connect(lambda result: self._status_result_handler(sip, result))
        worker.finished_signal.connect(lambda: self.active_workers.pop(sip, None))
        worker.stopped_forcibly_signal.connect(lambda: self.active_workers.pop(sip, None))
        worker.error_encountered_signal.connect(self.error_occurred_signal.emit)

    def force_stop(self, sip: SIP) -> None:
        worker = self.active_workers.get(sip)
        if worker is not None:
            worker.force_stop = True

    def force_stop_all(self) -> None:
        for worker in self.active_workers.values():
            worker.force_stop = True

    def _status_result_handler(self, sip: SIP, result: tuple[SIPStatus, str|None]) -> None:
        new_status, fail_reason = result

        if new_status is None:
            return

        if new_status == sip.status:
            return

        sip.set_status(new_status)
        self.status_changed_signal.emit(sip, new_status)

        if new_status == SIPStatus.REJECTED and fail_reason is not None:
            self.sip_rejected_signal.emit(sip, fail_reason)
