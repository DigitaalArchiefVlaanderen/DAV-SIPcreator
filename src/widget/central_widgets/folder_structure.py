from PySide6 import QtWidgets, QtGui, QtCore

from src.widget.base_widget import BaseWidget
from src.widget.components.mapping_widget import FolderMappingWidget


class FolderStructure(BaseWidget):
    def __init__(self):
        super().__init__()

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

        self.mapping = FolderMappingWidget()

        self.vertical_layout.addWidget(title)
        self.vertical_layout.addWidget(self.mapping)

    def add_to_metadata(self, tags: list) -> None:
        self.mapping.add_to_metadata(tags=tags)
