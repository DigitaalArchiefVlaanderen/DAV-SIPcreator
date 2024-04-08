from PySide6 import QtWidgets

from dataclasses import dataclass, field

from typing import List, Callable
import uuid
import os

from .dossier import Dossier
from ..series import Series
from ..sip_status import SIPStatus
from ..configuration import Environment


def get_next_sip_name():
    db_controller = QtWidgets.QApplication.instance().db_controller

    return f"SIP {db_controller.get_sip_count() + 1}"


@dataclass
class SIP:
    environment_name: str
    dossiers: List[Dossier]

    _id: str = field(default_factory=lambda: str(uuid.uuid4()))

    name: str = field(default_factory=get_next_sip_name)
    status: SIPStatus = SIPStatus.IN_PROGRESS
    series: Series = field(default_factory=Series)

    metadata_file_path: str = "Nog geen pad geselecteerd"
    mapping: dict = field(default_factory=dict)

    @property
    def file_name(self):
        return f"{self.series._id}-{self.name}.zip"

    def get_sip_folder_structure(self) -> dict:
        def _get_dossier_folder_structure(base_path: str, dossier_path: str) -> dict:
            structure = {}

            for location in os.listdir(dossier_path):
                location_path = os.path.join(dossier_path, location)

                if os.path.isfile(location_path) or len(os.listdir(location_path)) == 0:
                    structure[location] = os.path.relpath(
                        location_path,
                        base_path,
                    ).replace("\\", "/")
                else:
                    structure = {
                        **structure,
                        **_get_dossier_folder_structure(base_path, location_path),
                    }

            return structure

        sip_structure = {}

        for dossier in self.dossiers:
            sip_structure = {
                **sip_structure,
                dossier.dossier_label: {
                    "Path in SIP": dossier.dossier_label,
                    "path": dossier.path,
                    "Type": "dossier",
                    "DossierRef": dossier.dossier_label,
                    # To be determined based on the files for this dossier
                    "Openingsdatum": None,
                    "Sluitingsdatum": None,
                },
                **{
                    file_name: {
                        "Path in SIP": f"{dossier.dossier_label}/{location}",
                        "path": os.path.join(dossier.path, location),
                        "Type": (
                            # Set specific bad-type to filter on later
                            "geen"
                            if not os.path.isfile(os.path.join(dossier.path, location))
                            or os.path.getsize(os.path.join(dossier.path, location))
                            == 0
                            else "stuk"
                        ),
                        "DossierRef": dossier.dossier_label,
                        # Openingsdatum will be the creation dates of the file
                        # There is no cross-platform way of doing this sadly
                        # nt is Windows
                        "Openingsdatum": (
                            os.path.getctime(os.path.join(dossier.path, location))
                            if os.name == "nt"
                            else os.stat(
                                os.path.join(dossier.path, location)
                            ).st_birthtime
                        ),
                        # Sluitingsdatum will be the last edited time of the file
                        # This works as a cross-platform way of getting modification time
                        "Sluitingsdatum": os.path.getmtime(
                            os.path.join(dossier.path, location)
                        ),
                    }
                    for file_name, location in _get_dossier_folder_structure(
                        dossier.path, dossier.path
                    ).items()
                },
            }

        return sip_structure

    @property
    def environment(self) -> Environment:
        return QtWidgets.QApplication.instance().state.configuration.get_environment(
            self.environment_name
        )
