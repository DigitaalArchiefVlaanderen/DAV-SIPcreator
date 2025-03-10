from typing import Callable, List, Iterable
import os

from PySide6 import QtCore

from ..controllers.api_controller import APIController
from ..controllers.db_controller import DBController, SIPDBController, NotASIPDBException
from ..widgets.warning_dialog import WarningDialog
from .configuration import Configuration
from .state_utils.dossier import Dossier
from .state_utils.sip import SIP
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

        # NOTE: will be loaded at a later time
        self.series: List[Series] = None

    def check_series_loaded(self) -> bool:
        if self.series is None:
            self.load_series()

            return self.series is not None
        
        return True

    def load_series(self) -> None:
        # NOTE: this method only gets called when config changes or if no series exist yet
        # So clearing is never an issue here
        self.series = None

        if self.series is not None:
            return

        if not self.configuration.active_environment.has_api_credentials():
            WarningDialog(
                title="Connectie fout",
                text=f"Je API connectie gegevens staan niet in orde voor omgeving '{self.configuration.active_environment.name}'",
            ).exec()
            return

        self.series = APIController.get_series(self.configuration)

    @property
    def configuration(self) -> Configuration:
        return self.configuration_callback()

    @property
    def dossiers(self) -> List[Dossier]:
        self._dossiers = self.db_controller.read_dossiers()

        return self._dossiers

    def add_dossier(self, dossier: Dossier):
        self.db_controller.insert_dossier(dossier)
        self.dossiers.append(dossier)

    def add_dossiers(self, dossiers: List[Dossier]):
        self.db_controller.insert_dossiers(dossiers)
        self.dossiers.extend(dossiers)

    def remove_dossier(self, dossier: Dossier):
        self.db_controller.disable_dossier(dossier)

    def remove_dossiers(self, dossiers: Iterable[Dossier]):
        self.db_controller.disable_dossiers(dossiers)

    @property
    def sips(self) -> List[SIP]:
        if self._sips is None:
            self._sips = self.db_controller.read_sips()

        return self._sips

    def add_sip(self, sip: SIP) -> None:
        self.sips.append(sip)

    def update_sip(self, sip: SIP, fail_reason=None):
        db_path = os.path.join(
            self.configuration.sip_db_location,
            f"{sip.name}.db"
        )
        sip_db_controller = SIPDBController(db_path)

        if not os.path.exists(db_path):
            return

        if not sip_db_controller.is_valid_db():
            raise NotASIPDBException(f"Database laden is gefaald.\nDe database op locatie '{db_path}' is geen SIP database of is corrupt.")

        sip_db_controller.update_sip_table(sip=sip)

        if fail_reason is not None and fail_reason != "":
            self.sip_edepot_failed.emit(sip, fail_reason)
