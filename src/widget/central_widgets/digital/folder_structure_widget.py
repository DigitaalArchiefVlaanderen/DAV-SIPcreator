from PySide6 import QtWidgets, QtGui

from src.widget.base_widget import BaseWidget
from src.widget.components.digital.mapping_widget import FolderMappingWidget

from src.window.base_window import Window


class FolderStructureWidget(BaseWidget):
    def __init__(self, parent_window: Window):
        super().__init__()

        self.parent_window = parent_window

        self.setup_ui()

    def setup_ui(self) -> None:
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.vertical_layout)

        font = QtGui.QFont()
        font.setBold(True)
        font.setUnderline(True)
        font.setPointSize(20)
        title = QtWidgets.QLabel(text=self.title)
        title.setFont(font)

        self.folder_mapping_widget = FolderMappingWidget()

        self.vertical_layout.addWidget(title)
        self.vertical_layout.addWidget(self.folder_mapping_widget)

    def add_to_metadata(self, tags: list) -> None:
        self.folder_mapping_widget.add_to_metadata(tags=tags)

    def mapping_closed_handler(self, path_in_sip_map_column: str) -> None:
        df = self.sip.read_metadata()
        folder_structure = self.folder_structure_widget.mapping.get_mapping()

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
