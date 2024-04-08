from PySide6 import QtWidgets, QtGui, QtCore

import pandas as pd

from ..widgets.toolbar import Toolbar
from ..widgets.mapping_widget import FolderMappingWidget


class FolderStructure(QtWidgets.QMainWindow):
    closed: QtCore.Signal = QtCore.Signal(*(list,), arguments=["mapping"])

    def __init__(self, title: str):
        super().__init__()

        self.title = title

    def setup_ui(self) -> None:
        self.resize(800, 600)
        self.setWindowTitle("Mappen structuur")

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        self.toolbar = Toolbar()
        self.addToolBar(self.toolbar)

        grid_layout = QtWidgets.QGridLayout()
        central_widget.setLayout(grid_layout)

        font = QtGui.QFont()
        font.setBold(True)
        font.setUnderline(True)
        font.setPointSize(20)
        title = QtWidgets.QLabel(text=self.title)
        title.setFont(font)

        self.mapping = FolderMappingWidget()
        self.mapping.save_button.clicked.connect(self.close)

        grid_layout.addWidget(title, 0, 0)
        grid_layout.addWidget(self.mapping, 1, 0)

    def add_to_metadata(self, tags: list) -> None:
        self.mapping.add_to_metadata(tags=tags)

    def closeEvent(self, event):
        event.accept()

        self.closed.emit(self.mapping.get_mapping())
