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
        title = QtWidgets.QLabel(text=self.parent_window.sip.name)
        title.setFont(font)

        self.folder_mapping_widget = FolderMappingWidget()

        self.vertical_layout.addWidget(title)
        self.vertical_layout.addWidget(self.folder_mapping_widget)

    def add_to_metadata(self, tags: list) -> None:
        self.folder_mapping_widget.add_to_metadata(tags=tags)
