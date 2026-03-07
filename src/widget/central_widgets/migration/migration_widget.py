from PySide6 import QtWidgets

from src.utils.constants import UI_TEXT_ELEMENTS

from src.widget.central_widgets.central_widget import CentralWidget
from src.widget.components.searchable_list_widget import SearchableListWidget


class MigrationWidget(CentralWidget):
    UI_TEXT = UI_TEXT_ELEMENTS["migration"]["main"]

    def __init__(self) -> None:
        super().__init__()

        self.setup_ui()

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        self.title_label = QtWidgets.QLabel(self.UI_TEXT["title"])

        self.import_overdrachtslijst_button = QtWidgets.QPushButton(self.UI_TEXT["controls"]["import_overdrachtslijst_button"]["button_text"])

        self.file_location_button = QtWidgets.QPushButton(self.UI_TEXT["controls"]["bestandslocatie_button_text"])

        self.searchable_list_widget = SearchableListWidget(search_field="name")
        self.searchable_list_widget.setup_ui()

        self.grid_layout.addWidget(self.title_label, 0, 0)
        self.grid_layout.addWidget(self.import_overdrachtslijst_button, 1, 0)
        self.grid_layout.addWidget(self.file_location_button, 1, 1)
        self.grid_layout.addWidget(self.searchable_list_widget, 2, 0, 1, 2)
