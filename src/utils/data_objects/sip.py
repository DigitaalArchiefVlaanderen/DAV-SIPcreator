import os
import uuid

from PySide6 import QtCore

from src.utils.base_object import BaseObject
from src.utils.data_objects.configuration import Environment
from src.utils.data_objects.grid_data import GridData
from src.utils.data_objects.series import Series
from src.utils.data_objects.sip_status import SIPStatus


class SIP(BaseObject):
    name_changed_signal = QtCore.Signal()
    status_changed_signal = QtCore.Signal()
    series_changed_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()

        self.__id: str = str(uuid.uuid4())
        self.__name: str = "No name set"
        self.__status: SIPStatus = SIPStatus.IN_PROGRESS
        self.__series: Series = None
        
        self.environment: Environment = self.application.configuration.active_environment
        self._is_transitioned: bool = False

        self.edepot_sip_id: str = None

        self.grid_data: GridData = GridData()

    @property
    def name(self) -> str:
        return self.__name

    def set_name(self, new_name: str) -> None:
        self.__name = new_name
        self.name_changed_signal.emit()

    @property
    def status(self) -> SIPStatus:
        return self.__status

    def set_status(self, new_status: SIPStatus) -> None:
        self.__status = new_status
        self.status_changed_signal.emit()
    
    @property
    def series(self) -> Series | None:
        return self.__series

    def set_series(self, series: Series) -> None:
        self.__series = series
        self.series_changed_signal.emit()

    @property
    def db_name(self) -> str:
        prefix = "new_" if self._is_transitioned else ""
        return f"{prefix}{self.name}.db"

    def mark_as_transitioned(self) -> None:
        self._is_transitioned = True

    @property
    def file_name(self) -> str:
        return f"{self.series._id}-{self.name}-SIPC.zip"
    
    @property
    def sidecar_file_name(self) -> str:
        return f"{self.series._id}-{self.name}-SIPC.xml"

    def __eq__(self, other):
        if not isinstance(other, SIP):
            return NotImplemented
        return self.__id == other.__id

    def __hash__(self):
        return hash(self.__id)

    def open_edepot_url(self) -> str:
        return os.startfile(f"{self.environment.api_url}/input/processing-list/{self.edepot_sip_id}")
