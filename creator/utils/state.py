from dataclasses import dataclass, field
import os
import json
from typing import Callable, List

from PySide6.QtWidgets import QApplication

from ..controllers.db_controller import DBController
from .configuration import Configuration
from .state_utils.dossier import Dossier
from .state_utils.sip import SIP
from .series import Series


@dataclass
class State:
    configuration_callback: Callable
    db_controller: DBController

    _dossiers: List[Dossier] = None
    _sips: List[SIP] = None

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

    def update_sip(self, sip: SIP):
        self.db_controller.insert_series(sip.series)
        self.db_controller.update_sip(sip)

    def update_series(self, series: Series):
        self.db_controller.update_series(series)
