from collections.abc import Iterator

from PySide6 import QtCore

from src.utils.data_objects.analog.sip import AnalogSIP
from src.utils.pyside_helper import Helper
from src.utils.worker_user.base_retriever import BaseRetriever


class AnalogRetriever(BaseRetriever):
    analog_sip_loaded_signal = QtCore.Signal(AnalogSIP)

    def _load_sips(self) -> Iterator[None]:
        pending_series_info: list[tuple[AnalogSIP, str, str, str]] = []

        for sip, series_id, series_name in self.application.analog_sip_db_controller.g_read_all_sip_dbs():
            self.application.add_sip(sip)
            self.analog_sip_loaded_signal.emit(sip)

            pending_series_info.append((sip, sip.environment.name, series_id, series_name))

            yield

        Helper().wait_for_series_loaded(warn=False)

        for sip, env_name, series_id, series_name in pending_series_info:
            series = self.application.get_series_by_id_or_name(env_name, series_id, series_name, warn=False)
            sip.set_series(series)
