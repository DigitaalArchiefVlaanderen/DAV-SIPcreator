from PySide6 import QtWidgets, QtCore

from typing import List
import uuid
import os

from .dossier import Dossier
from ..series import Series
from ..sip_status import SIPStatus
from ..configuration import Environment


class FilenameNotUniqueException(Exception):
    def __init__(self, overlap: list, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.overlap = overlap


class SIP(QtCore.QObject):
    def __init__(
        self,
        environment_name: str,
        dossiers: List[Dossier],
        _id: str = None,
        name: str = None,
        status: SIPStatus = None,
        series: Series = None,
        metadata_file_path: str = None,
        tag_mapping: dict = None,
        folder_mapping: dict = None,
        edepot_sip_id: str = None,
    ):
        super().__init__()

        self.environment_name = environment_name
        self.dossiers = dossiers

        self._id = str(uuid.uuid4()) if _id is None else _id

        self.name = name
        self.status = SIPStatus.IN_PROGRESS if status is None else status
        self.series = Series() if series is None else series

        self.metadata_file_path = (
            "" if metadata_file_path is None else metadata_file_path
        )
        self.tag_mapping = {} if tag_mapping is None else tag_mapping
        self.folder_mapping = {} if folder_mapping is None else folder_mapping

        self.edepot_sip_id = edepot_sip_id

    # Signals
    status_changed: QtCore.Signal = QtCore.Signal(*(SIPStatus,), arguments=["status"])
    name_changed: QtCore.Signal = QtCore.Signal(*(str,), arguments=["name"])
    value_changed: QtCore.Signal = QtCore.Signal(*(QtCore.QObject,), arguments=["sip"])

    @property
    def file_name(self):
        return f"{self.series._id}-{self.name}-SIPC.zip"

    @property
    def sidecar_file_name(self):
        return f"{self.series._id}-{self.name}-SIPC.xml"

    @property
    def error_file_name(self):
        return f"{self.series._id}-{self.name}.txt"

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

        def _map_location_to_sip(location: str) -> str:
            # Location is the default "Path in SIP" location
            # This means it can have subfolders
            if self.folder_mapping is None:
                return location

            # Get the mapping, otherwise return default
            return self.folder_mapping.get(location, location)

        sip_structure = {}

        for dossier in self.dossiers:
            dossier_structure = {
                (path_in_sip := _map_location_to_sip(dossier.dossier_label)): {
                    "Path in SIP": path_in_sip,
                    "original Path in SIP": dossier.dossier_label,
                    "path": dossier.path,
                    "Type": "dossier",
                    "DossierRef": path_in_sip.split("/")[0],
                    # To be determined based on the files for this dossier
                    "Openingsdatum": None,
                    "Sluitingsdatum": None,
                }
            }

            file_structure = {
                (path_in_sip := _map_location_to_sip(f'{dossier.dossier_label}/{location}')): {
                    "Path in SIP": path_in_sip,
                    "original Path in SIP": f'{dossier.dossier_label}/{location}',
                    "path": (real_path := os.path.join(dossier.path, location)),
                    "Type": (
                        # Set specific bad-type to filter on later
                        "geen"
                        if not os.path.isfile(real_path)
                        or os.path.getsize(real_path) == 0
                        else "stuk"
                    ),
                    "DossierRef": path_in_sip.split("/")[0],
                    # Openingsdatum will be the creation dates of the file
                    # There is no cross-platform way of doing this sadly
                    # nt is Windows
                    "Openingsdatum": (
                        os.path.getctime(real_path)
                        if os.name == "nt"
                        else os.stat(real_path).st_birthtime
                    ),
                    # Sluitingsdatum will be the last edited time of the file
                    # This works as a cross-platform way of getting modification time
                    "Sluitingsdatum": os.path.getmtime(
                        real_path
                    ),
                }
                for file_name, location in _get_dossier_folder_structure(
                    dossier.path, dossier.path
                ).items()
            }

            if all(f["Type"] == "geen" for f in file_structure.values()):
                dossier_structure[dossier.dossier_label]["Type"] = "geen"

            overlapping_names = []

            for file_name in file_structure:
                if file_name in sip_structure:
                    overlapping_names.append(file_name)

            if len(overlapping_names):
                # raise FilenameNotUniqueException(overlap=overlapping_names)
                # NOTE: since this check is no longer required, remove the exception throwing
                # Do keep the code in case we need it at some point
                pass

            sip_structure = {
                **sip_structure,
                **dossier_structure,
                **file_structure,
            }

        return sip_structure

    @property
    def environment(self) -> Environment:
        return QtWidgets.QApplication.instance().state.configuration.get_environment(
            self.environment_name
        )

    # Setters
    def set_name(self, name: str) -> None:
        self.name = name
        self.name_changed.emit(name)
        self.value_changed.emit(self)

    def set_status(self, status: SIPStatus) -> None:
        self.status = status
        self.status_changed.emit(self.status)
        self.value_changed.emit(self)

    def set_series(self, series: Series) -> None:
        self.series = series
        self.value_changed.emit(self)

    def set_tag_mapping(self, tag_mapping: dict) -> None:
        self.tag_mapping = tag_mapping
        self.value_changed.emit(self)

    def set_metadata_file_path(self, metadata_file_path: str) -> None:
        self.metadata_file_path = metadata_file_path
        self.value_changed.emit(self)

    def set_edepot_sip_id(self, edepot_sip_id: str) -> None:
        self.edepot_sip_id = edepot_sip_id
        self.value_changed.emit(self)
