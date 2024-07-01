import os
import hashlib

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
            # NOTE: this only supports up to ZZ for now
            first_letter_value = (col_index // 26) - 1

            if first_letter_value >= 26:
                raise ValueError("There are too many columns")
            if first_letter_value == -1:
                return chr(65 + col_index)

            first_letter = chr(65 + first_letter_value)
            second_letter = chr(65 + col_index % 26)
            
            return f"{first_letter}{second_letter}"

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
    def create_sip(configuration: Configuration, sip: SIP):
        storage_location = configuration.misc.save_location
        location = os.path.join(storage_location, FileController.SIP_STORAGE)
        import_template_location = os.path.join(
            storage_location, FileController.GRID_STORAGE
        )

        FileController.ensure_folder_exists(location)
        sip_location = os.path.join(location, sip.file_name)
        sidecar_location = os.path.join(location, sip.sidecar_file_name)
        import_template_name = f"{sip._id}.xlsx"

        sip_folder_structure = sip.get_sip_folder_structure()

        with zipfile.ZipFile(
            sip_location, "w", compression=zipfile.ZIP_DEFLATED
        ) as zfile:
            zfile.write(
                os.path.join(import_template_location, import_template_name),
                "Metadata.xlsx",
            )

            for location in sip_folder_structure.values():
                device_location = location["path"]
                path_in_sip = location["Path in SIP"]

                if not os.path.exists(device_location):
                    raise FileNotFoundError(device_location)

                # Ignore bad types
                if location["Type"] != "geen":
                    zfile.write(device_location, path_in_sip)

        md5 = hashlib.md5(open(sip_location, "rb").read()).hexdigest()

        side_car_info = """
<?xml version="1.0" encoding="UTF-8"?>
<mhs:Sidecar xmlns:mhs="https://zeticon.mediahaven.com/metadata/20.3/mhs/" version="20.3" xmlns:mh="https://zeticon.mediahaven.com/metadata/20.3/mh/">
     <mhs:Technical>
              <mh:Md5>{md5}</mh:Md5>
     </mhs:Technical>
</mhs:Sidecar>""".format(
            md5=md5
        )

        with open(sidecar_location, "w", encoding="utf-8") as f:
            f.write(side_car_info)

    @staticmethod
    def existing_grid_path(configuration: dict, sip: SIP) -> str:
        storage_location = configuration.misc.save_location
        location = os.path.join(storage_location, FileController.GRID_STORAGE)

        file_name = f"{sip._id}.xlsx"
        path = os.path.join(location, file_name)

        if os.path.exists(path):
            return path

    @staticmethod
    def existing_grid(configuration: dict, sip: SIP) -> pd.DataFrame:
        if (path := FileController.existing_grid_path(configuration, sip)) is not None:
            return pd.read_excel(path, dtype=str)
