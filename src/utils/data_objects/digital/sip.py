"""
Data object to hold all the values related to a SIP.

Note that some fields are private, and use properties and explicit setters.
This is to make sure we can trigger signals when needed.

As a sidenote on this, the reason to use explicit setters, and not "name.setter" for example
is so that we can still easily use them in a lambda format

eg: lambda: sip.set_name(<new name>)
"""

import os
import re
from datetime import datetime

import pandas as pd

from src.controller.excel_controller import ExcelController

from src.utils.constants import FILE_REGEXES_TO_IGNORE, UI_TEXT_ELEMENTS, ColumnName, RowType
from src.utils.data_objects.sip import SIP as CommonSIP
from src.utils.pyside_helper import Helper

from src.widget.components.digital.dossier_widget import DossierWidget


class SIP(CommonSIP):
    def __init__(self):
        super().__init__()

        self.__dossiers: list[DossierWidget] = []

        self.set_name(Helper().get_next_sip_name(sip_type=type(self)))

        self.tag_mapping: list[tuple[str, str]] = []
        self.folder_mapping: dict = dict()

        self.import_template_path: str = None
        self.metadata_path: str = None

    @property
    def dossiers(self) -> list[DossierWidget]:
        return self.__dossiers

    def set_dossiers(self, new_dossiers: list[DossierWidget]) -> None:
        self.__dossiers = new_dossiers

    def set_import_template_path(self, import_template_path: str) -> None:
        self.import_template_path = import_template_path

    def read_import_template(self) -> pd.DataFrame | None:
        if self.import_template_path is None:
            return

        return ExcelController.read_excel(self.import_template_path)

    def read_metadata(self) -> pd.DataFrame | None:
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
        dossier_name = os.path.basename(dossier.path)

        return {
            (path_in_sip := self._map_file_location_to_sip_location(dossier_name)): {
                "path": dossier.path,
                ColumnName.PATH_IN_SIP.value: path_in_sip,
                ColumnName.TYPE.value: RowType.DOSSIER,
                ColumnName.NAAM.value: os.path.basename(path_in_sip),
                ColumnName.DOSSIER_REF.value: path_in_sip.split("/")[0],
                ColumnName.OPENINGSDATUM.value: None,
                ColumnName.SLUITINGSDATUM.value: None,
            }
        }

    def _get_dossier_folder_structure(self, base_path: str, dossier_path: str) -> dict[str, str]:
        """
        Returns a dict mapping file/folder names to their relative paths from base_path.

        {
            <file_name_1>: <root>/<file_name_1>,
            <file_name_2>: <root>/<subfolder>/<file_name_2>,
            ...
        }
        """
        structure = {}

        for dirpath, dirnames, filenames in os.walk(dossier_path):
            # Include empty directories, but skip '.' and '..' (relative path artifacts)
            if not filenames and not dirnames:
                rel_path = os.path.relpath(dirpath, base_path).replace("\\", "/")

                if rel_path in (".", ".."):
                    continue

                dir_name = os.path.basename(dirpath)
                structure[dir_name] = rel_path

            for filename in filenames:
                file_path = os.path.join(dirpath, filename)
                structure[filename] = os.path.relpath(file_path, base_path).replace("\\", "/")

        return structure

    def _get_file_structure(self, dossier: DossierWidget) -> dict[str, str]:
        dossier_name = os.path.basename(dossier.path)

        return {
            (path_in_sip := self._map_file_location_to_sip_location(f"{dossier_name}/{relative_location}")): {
                "path": (real_path := os.path.join(dossier.path, relative_location)),
                ColumnName.PATH_IN_SIP.value: path_in_sip,
                ColumnName.TYPE.value: (
                    RowType.GEEN
                    if not os.path.isfile(real_path)
                    or os.path.getsize(real_path) == 0
                    or any(re.match(p, file_name) is not None for p in FILE_REGEXES_TO_IGNORE)
                    else RowType.STUK
                ),
                ColumnName.NAAM.value: os.path.basename(path_in_sip),
                ColumnName.DOSSIER_REF.value: path_in_sip.split("/")[0],
                # Openingsdatum will be the creation dates of the file
                # There is no cross-platform way of doing this sadly
                # nt is Windows
                ColumnName.OPENINGSDATUM.value: (
                    os.path.getctime(real_path) if os.name == "nt" else os.stat(real_path).st_birthtime
                ),
                # Sluitingsdatum will be the last edited time of the file
                # This works as a cross-platform way of getting modification time
                ColumnName.SLUITINGSDATUM.value: os.path.getmtime(real_path),
            }
            for file_name, relative_location in self._get_dossier_folder_structure(dossier.path, dossier.path).items()
        }

    def _get_folder_structure(self) -> dict[str, str]:
        folder_structure = dict()

        for dossier in self.dossiers:
            dossier_structure = self._get_dossier_structure(dossier=dossier)
            file_structure = self._get_file_structure(dossier=dossier)

            dossier_key = next(iter(dossier_structure))

            if not file_structure or all(f[ColumnName.TYPE.value] == RowType.GEEN for f in file_structure.values()):
                dossier_structure[dossier_key][ColumnName.TYPE.value] = RowType.GEEN

            folder_structure = {
                **folder_structure,
                **dossier_structure,
                **file_structure,
            }

        return folder_structure

    def set_data_from_dossiers(self) -> None:
        import_template = self.read_import_template()
        if import_template is None:
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["no_import_template_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["no_import_template_error"]["text"],
            )
            return

        df = pd.DataFrame(columns=import_template.columns)

        folder_structure = self._get_folder_structure()

        main_columns = (
            ColumnName.PATH_IN_SIP.value,
            ColumnName.TYPE.value,
            ColumnName.DOSSIER_REF.value,
            ColumnName.NAAM.value,
            ColumnName.OPENINGSDATUM.value,
            ColumnName.SLUITINGSDATUM.value,
        )

        for column in main_columns:
            df[column] = [s[column] for s in folder_structure.values()]

        type_col = ColumnName.TYPE.value
        dossier_ref_col = ColumnName.DOSSIER_REF.value
        opening_col = ColumnName.OPENINGSDATUM.value
        closing_col = ColumnName.SLUITINGSDATUM.value

        open_dates_df = df.loc[df[type_col] == RowType.DOSSIER][[dossier_ref_col]].join(
            df.loc[df[type_col] == RowType.STUK]
            .groupby(by=dossier_ref_col)[opening_col]
            .min()
            .apply(lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d")),
            on=dossier_ref_col,
            rsuffix="_r",
        )
        close_dates_df = df.loc[df[type_col] == RowType.DOSSIER][[dossier_ref_col]].join(
            df.loc[df[type_col] == RowType.STUK]
            .groupby(by=dossier_ref_col)[closing_col]
            .max()
            .apply(lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d")),
            on=dossier_ref_col,
            rsuffix="_r",
        )

        # NOTE: we don't care about the lost values from files here
        # Windows tends to just do random things with it anyway, so it's likely no good
        df[opening_col] = None
        df[closing_col] = None

        df.loc[df[type_col] == RowType.DOSSIER, opening_col] = open_dates_df[opening_col]
        df.loc[df[type_col] == RowType.DOSSIER, closing_col] = close_dates_df[closing_col]

        self.grid_data.data_as_df = df.fillna("")

    def apply_tag_mapping(self) -> None:
        if not self.tag_mapping:
            return

        metadata_df = self.read_metadata()

        if metadata_df is None:
            return

        path_in_sip_col = ColumnName.PATH_IN_SIP.value
        path_metadata_col = next(
            (meta_col for meta_col, import_col in self.tag_mapping if import_col == path_in_sip_col),
            None,
        )

        if path_metadata_col is None:
            return

        temp_df = metadata_df.copy(deep=True)

        if self.folder_mapping and path_metadata_col in temp_df.columns:
            temp_df[path_metadata_col] = temp_df[path_metadata_col].replace(self.folder_mapping)

        lookup_df = temp_df.set_index(path_metadata_col, drop=False)
        df = self.grid_data.data_as_df

        for meta_col, import_col in self.tag_mapping:
            if import_col == path_in_sip_col:
                continue

            if meta_col not in lookup_df.columns:
                continue

            if import_col not in df.columns:
                continue

            lookup = lookup_df[meta_col]
            df[import_col] = df[path_in_sip_col].map(lookup).fillna(df[import_col])

        self.grid_data.data_as_df = df.fillna("")
