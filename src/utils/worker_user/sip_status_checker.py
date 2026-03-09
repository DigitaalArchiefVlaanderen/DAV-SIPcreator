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
    edepot_id_resolved_signal = QtCore.Signal(SIP, str)
    status_changed_signal = QtCore.Signal(SIP, SIPStatus)
    sip_rejected_signal = QtCore.Signal(SIP, str)
    error_occurred_signal = QtCore.Signal(Exception)

    def __init__(self):
        super().__init__()

        self.worker: Worker = None

    def run(self, worker_controller: WorkerController) -> None:
        self.worker = worker_controller.run_thread(
            thread_function=self.background_check_all_sips,
            thread_is_generator=True
        )

        if self.worker is None:
            return

        self.worker.result_ready_signal.connect(self._on_result)
        self.worker.error_encountered_signal.connect(self.error_occurred_signal.emit)

    def stop(self) -> None:
        if self.worker is not None:
            self.worker.force_stop = True

    def background_check_all_sips(self) -> Iterator[tuple]:
        while True:
            sips_to_check = self._collect_checkable_sips()

            for sip in sips_to_check:
                try:
                    if sip.edepot_sip_id is None:
                        edepot_id = APIController.get_sip_id(sip)

                        if edepot_id:
                            sip.edepot_sip_id = edepot_id

                            yield "edepot_resolved", sip, edepot_id
                        else:
                            yield None,

                        continue

                    result = APIController.get_sip_status(sip)

                    if result is None:
                        yield None,
                        continue

                    new_status, fail_reason = result

                    if new_status is None or new_status == sip.status:
                        yield None,
                        continue

                    sip.set_status(new_status)

                    yield "status_changed", sip, new_status

                    if new_status == SIPStatus.REJECTED and fail_reason is not None:
                        yield "sip_rejected", sip, fail_reason

                except Exception as e:
                    yield "error", e

            time.sleep(POLL_INTERVAL_SECONDS)

            yield None,

    def _collect_checkable_sips(self) -> list[SIP]:
        result = []

        for sip_type_dict in self.application.sips.values():
            for sips in sip_type_dict.values():
                for sip in sips:
                    if sip.status in CHECKABLE_SIP_STATUSES:
                        result.append(sip)

        return result

    def _on_result(self, result: tuple) -> None:
        if result is None or result[0] is None:
            return

        action = result[0]

        if action == "edepot_resolved":
            _, sip, edepot_id = result

            self.edepot_id_resolved_signal.emit(sip, edepot_id)

        elif action == "status_changed":
            _, sip, new_status = result

            self.status_changed_signal.emit(sip, new_status)

        elif action == "sip_rejected":
            _, sip, fail_reason = result

            self.sip_rejected_signal.emit(sip, fail_reason)

        elif action == "error":
            _, exception = result

            self.error_occurred_signal.emit(exception)
