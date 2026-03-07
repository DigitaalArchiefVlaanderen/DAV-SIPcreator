import os

import numpy as np

from src.utils.data_objects.digital.sip import SIP
from src.utils.constants import UI_TEXT_ELEMENTS

from src.widget.central_widgets.digital.folder_structure_widget import FolderStructureWidget

from src.window.base_window import Window


class FolderMappingWindow(Window):
    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()

    def setup_ui(self) -> None:
        self.setWindowTitle(UI_TEXT_ELEMENTS["window_titles"]["digital"]["folder_structure"])
        
        self.folder_structure_widget = FolderStructureWidget(parent_window=self)
        self.setCentralWidget(self.folder_structure_widget)
        
        path_in_sip_map_column = [
            k for k, v in self.sip.tag_mapping.items()
            if v == "Path in SIP"
        ][0]
        # Only allow columns where not all fields are empty
        columns_without_empty_fields = [
            c
            for c, all_empty in dict(
                self.sip.read_metadata().eq("").all()
            ).items()
            if not all_empty and c != path_in_sip_map_column
        ]

        self.folder_structure_widget.add_to_metadata(columns_without_empty_fields)
        self.folder_structure_widget.folder_mapping_widget.save_button.clicked.connect(
            lambda: self.mapping_closed_handler(path_in_sip_map_column=path_in_sip_map_column)
        )

    def mapping_closed_handler(self, path_in_sip_map_column: str) -> None:
        df = self.sip.read_metadata()
        folder_structure = self.folder_structure_widget.folder_mapping_widget.get_mapping()

        # NOTE: only check for files (anything with an extension)
        df_sub = df[df[path_in_sip_map_column].str.contains(r"\.[a-zA-Z0-9]+$", regex=True, na=False)][[*folder_structure]].apply(lambda x: x.str.strip())

        if np.any(df_sub.isna()) or np.any(df_sub == ""):
            self.application.thread_error_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["folder_mapping_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["folder_mapping_error"]["text"]
            )
            return

        # Kamerplanten/groot/monstera.docx
        # jaar -> dor of niet dor
        # Kamerplanten/groot/**2022/dor**/monstera.docx

        df["__folder"] = df[path_in_sip_map_column].apply(lambda x: x.rsplit("/", 1)[0])
        df["__file"] = df[path_in_sip_map_column].apply(lambda x: "" if len(x.rsplit("/", 1)) == 1 else x.rsplit("/", 1)[1])

        folder_mapping = {
            path_in_sip: mapped_name
            for path_in_sip, mapped_name in zip(
                df[path_in_sip_map_column],
                df[["__folder", *folder_structure, "__file"]].fillna("").astype(str).convert_dtypes().agg("/".join, axis=1),
            )
            # NOTE: only do aggregate mapping if it's a stuk (with an extension)
            if os.path.splitext(path_in_sip)[1] != ""
        }

        self.sip.folder_mapping = folder_mapping

        self.close()
