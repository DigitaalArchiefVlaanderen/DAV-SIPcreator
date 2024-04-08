from typing import Callable, List

from PySide6 import QtCore

from ..controllers.db_controller import DBController
from .configuration import Configuration
from .state_utils.dossier import Dossier
from .state_utils.sip import SIP
from .sip_status import SIPStatus
from .series import Series


class State(QtCore.QObject):
    sip_edepot_failed: QtCore.Signal = QtCore.Signal(
        *(str, str), arguments=["sip_name", "fail_reason"]
    )

    def __init__(self, configuration_callback: Callable, db_controller: DBController):
        super().__init__()

        self.configuration_callback = configuration_callback
        self.db_controller = db_controller

        self._dossiers: List[Dossier] = None
        self._sips: List[SIP] = None

    @property
    def configuration(self) -> Configuration:
        return Configuration.from_json(self.configuration_callback())

    @property
    def dossiers(self) -> List[Dossier]:
        if self._dossiers is None:
            self._dossiers = self.db_controller.read_dossiers()

        return self._dossiers

    def add_dossier(self, dossier: Dossier):
        self.db_controller.insert_dossier(dossier)
        self.dossiers.append(dossier)

    def remove_dossier(self, dossier: Dossier):
        self.db_controller.disable_dossier(dossier)

    @property
    def sips(self) -> List[SIP]:
        if self._sips is None:
            self._sips = self.db_controller.read_sips()

        return self._sips

    def add_sip(self, sip: SIP):
        self.db_controller.insert_sip(sip)
        self.sips.append(sip)

    def update_sip(self, sip: SIP, fail_reason=None):
        self.db_controller.insert_series(sip.series)
        self.db_controller.update_sip(sip)

        if fail_reason is not None and fail_reason != "":
            self.sip_edepot_failed.emit(sip, fail_reason)

    def update_series(self, series: Series):
        self.db_controller.update_series(series)
