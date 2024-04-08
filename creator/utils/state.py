from dataclasses import dataclass
import os
import json
from typing import Callable, List

from PySide6.QtWidgets import QApplication

from ..controllers.db_controller import DBController
from .configuration import Configuration
from .state_utils.dossier import Dossier
from .state_utils.sip import SIP


@dataclass
class State:
    configuration_callback: Callable
    db_controller: DBController

    @property
    def configuration(self) -> Configuration:
        return Configuration.from_json(self.configuration_callback())

    @property
    def dossiers(self) -> List[Dossier]:
        return self.db_controller.read_dossiers()

    def add_dossier(self, dossier: Dossier):
        self.db_controller.insert_dossier(dossier)

    def remove_dossier(self, dossier: Dossier):
        self.db_controller.delete_dossier(dossier)

    @property
    def sips(self) -> List[SIP]:
        return self.db_controller.read_sips(self.configuration)

    def add_sip(self, sip: SIP):
        self.db_controller.insert_sip(sip)

    def update_sip(self, sip: SIP):
        self.db_controller.update_sip(sip)
