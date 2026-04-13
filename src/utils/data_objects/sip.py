import os
import uuid

from PySide6 import QtCore

from src.utils.base_object import BaseObject
from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.configuration import Environment
from src.utils.data_objects.grid_data import GridData
from src.utils.data_objects.series import Series
from src.utils.data_objects.sip_status import SIPStatus


class SIP(BaseObject):
    name_changed_signal = QtCore.Signal()
    status_changed_signal = QtCore.Signal()
    series_changed_signal = QtCore.Signal()
    grid_validity_changed_signal = QtCore.Signal(bool)

    def __init__(self):
        super().__init__()

        self.__id: str = str(uuid.uuid4())
        self.__name: str = "No name set"
        self.__status: SIPStatus = SIPStatus.IN_PROGRESS
        self.__series: Series = None
        self.__grid_valid: bool = False

        self.environment: Environment = self.application.configuration.active_environment

        self.edepot_sip_id: str = None
        self.saved_series_name: str = None

        self.grid_data: GridData = GridData()

    @property
    def name(self) -> str:
        return self.__name

    INVALID_NAME_CHARACTERS = set('<>:"/\\|?*')

    def set_name(self, new_name: str) -> bool:
        new_name = new_name.strip()

        if new_name == self.__name:
            return True

        if not new_name:
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip_name"]["empty_name_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip_name"]["empty_name_error"]["text"],
            )
            self.name_changed_signal.emit()

            return False

        invalid_chars = self.INVALID_NAME_CHARACTERS & set(new_name)
        if invalid_chars:
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip_name"]["invalid_characters_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip_name"]["invalid_characters_error"]["text"].format(
                    characters=" ".join(sorted(invalid_chars))
                ),
            )
            self.name_changed_signal.emit()

            return False

        from src.utils.pyside_helper import Helper

        if not Helper().is_sip_name_available(new_name, sip_type=type(self), exclude_sip=self):
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["duplicate_name_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["duplicate_name_error"]["text"].format(name=new_name),
            )
            self.name_changed_signal.emit()

            return False

        self.__name = new_name
        self.name_changed_signal.emit()

        return True

    def force_set_name(self, new_name: str) -> None:
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
    def grid_valid(self) -> bool:
        return self.__grid_valid

    def set_grid_valid(self, valid: bool) -> None:
        if self.__grid_valid != valid:
            self.__grid_valid = valid
            self.grid_validity_changed_signal.emit(valid)

    @property
    def db_name(self) -> str:
        return f"{self.name}.db"

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
