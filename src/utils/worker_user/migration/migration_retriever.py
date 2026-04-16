from collections.abc import Iterator

from PySide6 import QtCore

from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.worker_user.base_retriever import BaseRetriever


class MigrationRetriever(BaseRetriever):
    migration_sip_loaded_signal = QtCore.Signal(MigrationSIP)

    def _load_sips(self) -> Iterator[None]:
        db_controller = self.application.migration_sip_db_controller

        for sip in db_controller.g_read_all_sip_dbs():
            series_statuses = db_controller.read_series_statuses(sip.db_name)
            tables = db_controller.read_tables(sip.db_name)

            for table_name, (status_name, edepot_id) in series_statuses.items():
                try:
                    sip.series_statuses[table_name] = SIPStatus[status_name]
                except KeyError:
                    sip.series_statuses[table_name] = SIPStatus.IN_PROGRESS

                if edepot_id:
                    sip.series_edepot_ids[table_name] = edepot_id

            for table_name, uri_serieregister, _, _ in tables:
                series_id = uri_serieregister.rsplit("/", 1)[-1] if uri_serieregister else ""
                if series_id:
                    sip.series_zip_names[table_name] = f"{series_id}-{sip.name}-SIPC.zip"

            sip.derive_overall_status()

            self.application.add_sip(sip)

            self.migration_sip_loaded_signal.emit(sip)

            yield
