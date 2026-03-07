from typing import Iterator

from PySide6 import QtCore

from src.utils.data_objects.sip import SIP
from src.utils.pyside_helper import Helper
from src.utils.worker_user.worker_user import WorkerUser
from src.utils.workers.worker import Worker


class SIPRetriever(WorkerUser):
    sip_loaded_signal = QtCore.Signal(SIP)
    error_occurred_signal = QtCore.Signal(Exception)

    def __init__(self):
        super().__init__()

        self.worker: Worker = None

    def run(self) -> None:
        self.worker = self.application.worker_controller.run_thread(
            thread_function=self._load_sips,
            thread_is_generator=True
        )

        if self.worker is None:
            return

        self.worker.error_encountered_signal.connect(self.error_occurred_signal.emit)

    def _load_sips(self) -> Iterator[None]:
        pending_series_info: list[tuple[SIP, str, str, str]] = []

        for sip, series_id, series_name in self.application.sip_db_controller.g_read_all_sip_dbs():
            self.application.add_sip(sip)
            self.sip_loaded_signal.emit(sip)
            pending_series_info.append((sip, sip.environment.name, series_id, series_name))
            yield

        Helper().wait_for_series_loaded(warn=False)

        for sip, env_name, series_id, series_name in pending_series_info:
            try:
                sip.set_series(
                    self.application.get_series_by_id_or_name(
                        env_name, series_id, series_name
                    )
                )
            except Exception:
                pass
