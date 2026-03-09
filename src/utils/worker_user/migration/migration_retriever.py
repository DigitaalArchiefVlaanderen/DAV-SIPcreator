from typing import Iterator

from PySide6 import QtCore

from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.worker_user.worker_user import WorkerUser
from src.utils.workers.worker import Worker


class MigrationRetriever(WorkerUser):
    migration_sip_loaded_signal = QtCore.Signal(MigrationSIP)
    error_occurred_signal = QtCore.Signal(Exception)

    def __init__(self):
        super().__init__()

        self.worker: Worker = None

    def run(self) -> None:
        self.worker = self.application.worker_controller.run_thread(
            thread_function=self.background_load_migration_sips,
            thread_is_generator=True
        )

        if self.worker is None:
            return

        self.worker.error_encountered_signal.connect(self.error_occurred_signal.emit)

    def background_load_migration_sips(self) -> Iterator[None]:
        db_controller = self.application.migration_sip_db_controller

        for sip in db_controller.g_read_all_sip_dbs():
            series_statuses = db_controller.read_series_statuses(sip.db_name)

            for table_name, (status_name, edepot_id) in series_statuses.items():
                try:
                    sip.series_statuses[table_name] = SIPStatus[status_name]
                except KeyError:
                    sip.series_statuses[table_name] = SIPStatus.IN_PROGRESS

            sip.derive_overall_status()

            self.application.add_sip(sip)

            self.migration_sip_loaded_signal.emit(sip)

            yield
