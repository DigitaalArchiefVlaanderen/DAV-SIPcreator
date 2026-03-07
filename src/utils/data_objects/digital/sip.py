"""
Data object to hold all the values related to a SIP.

Note that some fields are private, and use properties and explicit setters.
This is to make sure we can trigger signals when needed.

As a sidenote on this, the reason to use explicit setters, and not "name.setter" for example
is so that we can still easily use them in a lambda format

eg: lambda: sip.set_name(<new name>)
"""
import os
from datetime import datetime
import re

import pandas as pd

from src.controller.excel_controller import ExcelController

from src.utils.constants import FILE_REGEXES_TO_IGNORE
from src.utils.pyside_helper import Helper

from src.widget.components.digital.dossier_widget import DossierWidget

from src.utils.data_objects.sip import SIP as CommonSIP


class SIP(CommonSIP):
    def __init__(self):
        super().__init__()

        self.__dossiers: list[DossierWidget] = []

        self.name = Helper().get_next_sip_name()

        self.tag_mapping: dict[str, str] = dict()
        self.folder_mapping: dict = dict()

        self.import_template_path: str = None
        self.metadata_path: str = None

    @property
    def dossiers(self) -> list[DossierWidget]:
        return self.__dossiers

    def set_dossiers(self, new_dossiers: list[DossierWidget]) -> None:
        self.__dossiers = new_dossiers

    def set_import_template_path(self, import_template_path: str) -> None:
        print("setting import template path", import_template_path)
        self.import_template_path = import_template_path

    def read_import_template(self) -> pd.DataFrame|None:
        if self.import_template_path is None:
            return
        
        return ExcelController.read_excel(self.import_template_path)

    def read_metadata(self) -> pd.DataFrame|None:
        if self.metadata_path is None:
            return
        
        return ExcelController.read_excel(self.metadata_path)

    # TODO clean this mess up?
    def _map_file_location_to_sip_location(self, location: str) -> str:
        """
            Since we have some mappings, we may need to map a real location
            to a fake one in the sip
        """
        if self.folder_mapping is None:
            return location
        
        return self.folder_mapping.get(location, location)

    def _get_dossier_structure(self, dossier: DossierWidget) -> dict[str, str]:
        return {
            (path_in_sip := self._map_file_location_to_sip_location(dossier.path)): {
                "path": dossier.path,

                "Path in SIP": path_in_sip,
                "Type": "dossier",
                "Naam": os.path.basename(path_in_sip),
                "DossierRef": path_in_sip.split("/")[0],
                # To be determined based on the files for this dossier
                "Openingsdatum": None,
                "Sluitingsdatum": None,
            }
        }

    def _get_dossier_folder_structure(self, base_path: str, dossier_path: str) -> dict[str, str]:
        """
            This one is a bit confusing so let me tell you what it does

            you pass in <root-folder>, <root-folder>
            and it gives you a dictionary that looks like this

            {
                <file_name_1>: <root>/<file_name_1>,
                <file_name_2>: <root>/<subfolder>/<file_name_2>,
                <file_name_3>: <root>/<subfolder>/<file_name_3>,
                <file_name_4>: <root>/<subfolder>/<2nd_subfolder>/<file_name_4>,
            }

            keep in mind this is just an example

            os.walk would work better, let me tell you (on my todo list)
        """
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
                    **self._get_dossier_folder_structure(base_path, location_path),
                }

        return structure

    def _get_file_structure(self, dossier: DossierWidget) -> dict[str, str]:
        return {
                (path_in_sip := self._map_file_location_to_sip_location(f'{dossier.path}/{relative_location}')): {
                    "path": (real_path := os.path.join(dossier.path, relative_location)),

                    "Path in SIP": path_in_sip,
                    "Type": (
                        # Set specific bad-type to filter on later
                        "geen"
                        if not os.path.isfile(real_path)
                        or os.path.getsize(real_path) == 0
                        or any(re.match(p, file_name) is not None for p in FILE_REGEXES_TO_IGNORE)
                        else "stuk"
                    ),
                    "Naam": os.path.basename(path_in_sip),
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
                for file_name, relative_location in self._get_dossier_folder_structure(
                    dossier.path, dossier.path
                ).items()
            }

    def _get_folder_structure(self) -> dict[str, str]:
        folder_structure = dict()

        for dossier in self.dossiers:
            dossier_structure = self._get_dossier_structure(dossier=dossier)
            file_structure = self._get_file_structure(dossier=dossier)
            
            if all(f["Type"] == "geen" for f in file_structure.values()):
                dossier_structure[dossier.path]["Type"] = "geen"

            folder_structure = {
                **folder_structure,
                **dossier_structure,
                **file_structure,
            }

        return folder_structure

    def set_data_from_dossiers(self) -> None:
        df = pd.DataFrame(
            columns=self.read_import_template().columns
        )

        folder_structure = self._get_folder_structure()

        main_columns = (
            "Path in SIP",
            "Type",
            "DossierRef",
            "Naam",
            "Openingsdatum",
            "Sluitingsdatum"
        )

        for column in main_columns:
            df[column] = [
                s[column] for s in folder_structure.values()
            ]
        
        open_dates_df = df.loc[df.Type == "dossier"][["DossierRef"]].join(
            df.loc[df.Type == "stuk"]
            .groupby(by="DossierRef")
            .Openingsdatum.min()
            .apply(lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d")),
            on="DossierRef",
            rsuffix="_r",
        )
        close_dates_df = df.loc[df.Type == "dossier"][["DossierRef"]].join(
            df.loc[df.Type == "stuk"]
            .groupby(by="DossierRef")
            .Sluitingsdatum.max()
            .apply(lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d")),
            on="DossierRef",
            rsuffix="_r",
        )

        # NOTE: we don't care about the lost values from files here
        # Windows tends to just do random things with it anyway, so it's likely no good
        df.Openingsdatum = None
        df.Sluitingsdatum = None

        df.loc[df.Type == "dossier", "Openingsdatum"] = open_dates_df.Openingsdatum
        df.loc[df.Type == "dossier", "Sluitingsdatum"] = close_dates_df.Sluitingsdatum

        self.grid_data.data_as_df = df
