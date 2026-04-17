import os
import shutil
from contextlib import suppress

import pandas as pd

from src.controller.api_controller import APIController
from src.controller.sip_creation_controller import create_sip_zip, fill_import_template

from src.utils.base_object import BaseObject
from src.utils.constants import UI_TEXT_ELEMENTS, ColumnName, RowType
from src.utils.data_objects.digital.sip import SIP

UI_TEXT = UI_TEXT_ELEMENTS["errors"]["sip"]


class FileController(BaseObject):
    def _is_sip_folder_structure_valid(self, sip_folder_structure: dict, df: pd.DataFrame) -> bool:
        folder_paths = set()

        for row in sip_folder_structure.values():
            path_in_sip, path = row[ColumnName.PATH_IN_SIP], row["path"]

            if sum(df[ColumnName.PATH_IN_SIP] == path_in_sip) == 0:
                self.application.notify_user_signal.emit(
                    UI_TEXT["folder_structure_new_path_error"]["title"],
                    UI_TEXT["folder_structure_new_path_error"]["text"].format(path=path),
                )
                return False

            elif sum(df[ColumnName.PATH_IN_SIP] == path_in_sip) > 1:
                self.application.notify_user_signal.emit(
                    UI_TEXT["folder_structure_duplicate_path_error"]["title"],
                    UI_TEXT["folder_structure_duplicate_path_error"]["text"].format(path_in_sip=path_in_sip),
                )
                return False

            folder_paths.add(path_in_sip)

        for _, row in df.iterrows():
            if row[ColumnName.PATH_IN_SIP] not in folder_paths:
                self.application.notify_user_signal.emit(
                    UI_TEXT["folder_structure_missing_path_error"]["title"],
                    UI_TEXT["folder_structure_missing_path_error"]["text"].format(
                        path_in_sip=row[ColumnName.PATH_IN_SIP]
                    ),
                )
                return False

        return True

    @staticmethod
    def _filter_df(df: pd.DataFrame, strip_name_extensions: bool = False) -> pd.DataFrame:
        filtered = df.loc[df[ColumnName.TYPE] != RowType.GEEN].copy()
        filtered.reset_index(drop=True, inplace=True)

        if strip_name_extensions and ColumnName.NAAM in filtered.columns:
            filtered[ColumnName.NAAM] = filtered[ColumnName.NAAM].apply(lambda v: v.rsplit(".", 1)[0] if v else v)

        return filtered

    def create_sip(self, sip: SIP, strip_name_extensions: bool = False) -> bool:
        configuration = self.application.configuration

        storage_location = configuration.sips_location
        import_template_location = os.path.join(configuration.import_templates_location, f"{sip.series._id}.xlsx")

        os.makedirs(storage_location, exist_ok=True)

        import_template_location = APIController.get_import_template(
            configuration=configuration,
            series_id=sip.series._id,
            environment=sip.environment,
        )

        sip_folder_structure = sip._get_folder_structure()
        filtered_folder_structure = {
            k: v for k, v in sip_folder_structure.items() if v[ColumnName.TYPE] != RowType.GEEN
        }

        df = FileController._filter_df(sip.grid_data.data_as_df, strip_name_extensions)

        if not self._is_sip_folder_structure_valid(sip_folder_structure=filtered_folder_structure, df=df):
            return False

        # Validate all files still exist before zipping
        for location in filtered_folder_structure.values():
            file_path = location["path"]

            if not os.path.exists(file_path):
                self.application.notify_user_signal.emit(
                    UI_TEXT["folder_structure_missing_path_error"]["title"],
                    UI_TEXT["folder_structure_missing_path_error"]["text"].format(path_in_sip=file_path),
                )
                return False

        temp_excel_location = os.path.join(configuration.import_templates_location, "temp.xlsx")
        shutil.copy(src=import_template_location, dst=temp_excel_location)

        fill_import_template(df, import_template_location, temp_excel_location)

        sip_location = os.path.join(storage_location, sip.file_name)
        sidecar_location = os.path.join(storage_location, sip.sidecar_file_name)

        additional_files = {
            location[ColumnName.PATH_IN_SIP]: location["path"] for location in filtered_folder_structure.values()
        }

        try:
            create_sip_zip(temp_excel_location, sip_location, sidecar_location, additional_files)
        except OSError as e:
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["file_system"]["disk_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["file_system"]["disk_error"]["text"].format(error=e),
            )
            return False
        finally:
            with suppress(PermissionError, FileNotFoundError):
                os.remove(temp_excel_location)

        return True
