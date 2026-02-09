"""
Data object to hold all the values related to a SIP.

Note that some fields are private, and use properties and explicit setters.
This is to make sure we can trigger signals when needed.

As a sidenote on this, the reason to use explicit setters, and not "name.setter" for example
is so that we can still easily use them in a lambda format

eg: lambda: sip.set_name(<new name>)
"""
import os

from PySide6 import QtCore

from src.utils.base_object import BaseObject
from src.utils.data_objects.series import Series
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.pyside_helper import Helper

from src.widget.components.dossier_widget import DossierWidget


class SIP(BaseObject):
    name_changed_signal = QtCore.Signal()
    status_changed_signal = QtCore.Signal()
    series_changed_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()

        # NOTE: these are fields that are shown in multiple views, so we make them "private"
        # and use getters and setters to trigger signals when needed
        self.__name = Helper().get_next_sip_name()
        self.__status = SIPStatus.IN_PROGRESS
        self.__dossiers: list[DossierWidget] = []
        self.__series: Series = None

        self.db_name = f"{self.name}.db"

        self.environment = self.application.configuration.active_environment

        self.tag_mapping: dict[str, str] = dict()
        self.folder_mapping: dict = dict()

        self.edepot_sip_id: str = None

        # NOTE: this is only temporary storage of the data,
        # it is not always going to be here, usually the data is just in a db
        self.data: dict[str, list[str]] = None

        self.import_template_path: str = None

    @property
    def name(self) -> str:
        return self.__name

    def set_name(self, new_name: str) -> None:
        self.__name = new_name
        self.db_name = f"{self.name}.db"
        self.name_changed_signal.emit()

    @property
    def status(self) -> SIPStatus:
        return self.__status

    def set_status(self, new_status: SIPStatus) -> None:
        self.__status = new_status
        self.status_changed_signal.emit()

    @property
    def dossiers(self) -> list[DossierWidget]:
        return self.__dossiers

    def set_dossiers(self, new_dossiers: list[DossierWidget]) -> None:
        self.__dossiers = new_dossiers

    @property
    def series(self) -> Series:
        Helper().wait_for_series_loaded(custom_signal=self.series_changed_signal)
        return self.__series

    # NOTE: seems stupid, but it's easier to be used in a lambda this way
    def set_series(self, series: Series) -> None:
        self.__series = series
        self.series_changed_signal.emit()

    def set_import_template_path(self, import_template_path: str) -> None:
        print("setting import template path", import_template_path)
        self.import_template_path = import_template_path

    @property
    def file_name(self) -> str:
        return f"{self.series._id}-{self.name}-SIPC.zip"
    
    @property
    def sidecar_file_name(self) -> str:
        return f"{self.series._id}-{self.name}-SIPC.zip"

    def open_edepot_url(self) -> str:
        return os.startfile(f"{self.environment.api_url}/input/processing-list/{self.edepot_sip_id}")
