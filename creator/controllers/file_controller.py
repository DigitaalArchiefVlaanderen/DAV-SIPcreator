import os

import pandas as pd
from openpyxl import load_workbook
import shutil
import zipfile

from ..utils.state_utils.sip import SIP
from ..utils.configuration import Configuration


class FileController:
    GRID_STORAGE = "Grid"
    SIP_STORAGE = "SIPs"
    IMPORT_TEMPLATE_STORAGE = "import_templates"

    @staticmethod
    def ensure_folder_exists(location):
        if not os.path.exists(location):
            os.makedirs(location)

    @staticmethod
    def fill_import_template(df: pd.DataFrame, sip_widget):
        def _col_index_to_xslx_col(col_index: int) -> str:
            # NOTE: this only supports up to AZ for now
            if col_index < 26:
                return chr(65 + col_index)

            return f"A{_col_index_to_xslx_col(col_index-26)}"

        wb = load_workbook(sip_widget.import_template_location)
        ws = wb["Details"]

        # NOTE: there is probably a better way to do this, did not find it
        for row_index, row_info in df.iterrows():
            for col_index, value in enumerate(row_info.values):
                ws[f"{_col_index_to_xslx_col(col_index)}{row_index+2}"] = value

        wb.save(sip_widget.import_template_location)
        wb.close()

    @staticmethod
    def save_grid(configuration: Configuration, df: pd.DataFrame, sip_widget):
        storage_location = configuration.misc.save_location
        location = os.path.join(storage_location, FileController.GRID_STORAGE)

        file_name = f"{sip_widget.sip._id}.xlsx"
        path = os.path.join(location, file_name)

        FileController.ensure_folder_exists(location)
        FileController.fill_import_template(df=df, sip_widget=sip_widget)

        shutil.copyfile(sip_widget.import_template_location, path)

    @staticmethod
    def create_sip(configuration: Configuration, df: pd.DataFrame, sip_widget):
        storage_location = configuration.misc.save_location
        location = os.path.join(storage_location, FileController.SIP_STORAGE)
        import_template_location = os.path.join(
            storage_location, FileController.GRID_STORAGE
        )

        FileController.ensure_folder_exists(location)
        sip_name = f"{sip_widget.sip.series._id}-{sip_widget.sip.name}.zip"
        import_template_name = f"{sip_widget.sip._id}.xlsx"

        sip_folder_structure = sip_widget.sip.get_sip_folder_structure()

        with zipfile.ZipFile(
            os.path.join(location, sip_name), "w", compression=zipfile.ZIP_DEFLATED
        ) as zfile:
            zfile.write(
                os.path.join(import_template_location, import_template_name),
                "Metadata.xlsx",
            )

            for location in sip_folder_structure.values():
                device_location = location["path"]
                path_in_sip = location["Path in SIP"]

                zfile.write(device_location, path_in_sip)

    @staticmethod
    def existing_grid(configuration: dict, sip: SIP) -> pd.DataFrame:
        storage_location = configuration.misc.save_location
        location = os.path.join(storage_location, FileController.GRID_STORAGE)

        file_name = f"{sip._id}.xlsx"
        path = os.path.join(location, file_name)

        if os.path.exists(path):
            return pd.read_excel(path)
