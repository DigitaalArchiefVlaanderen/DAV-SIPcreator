from PySide6 import QtWidgets, QtCore

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.digital.sip import SIP
from src.utils.grid.table.digital_data_verification_table import DigitalDataVerificationTable

from src.widget.base_widget import BaseWidget


UI_TEXT = UI_TEXT_ELEMENTS["digital"]["grid"]


class DigitalGridView(BaseWidget):
    def __init__(self, sip: SIP) -> None:
        super().__init__()

        self.sip = sip

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        series_text = self.sip.series.get_full_name() if self.sip.series else UI_TEXT["series_not_found_text"]
        self.series_label = QtWidgets.QLabel(text=series_text)
        self.default_sorting_button = QtWidgets.QPushButton(text=UI_TEXT["default_sorting_button_text"])

        self.name_extension_checkbox = QtWidgets.QCheckBox(
            text=UI_TEXT["name_extension_checkbox_text"]
        )
        self.name_extension_checkbox.setChecked(False)

        self.show_bad_rows_checkbox = QtWidgets.QCheckBox(
            text=UI_TEXT["bad_rows_checkbox_text"]
        )

        self.show_dossiers_only_checkbox = QtWidgets.QCheckBox(
            text=UI_TEXT["dossiers_only_checkbox_text"]
        )

        self.column_dropdown = QtWidgets.QComboBox()
        self.add_column_button = QtWidgets.QPushButton(text=UI_TEXT["add_column_button_text"])

        self.table_model = DigitalDataVerificationTable(sip=self.sip)
        self.table_view = QtWidgets.QTableView()
        self.table_view.setModel(self.table_model)

        self.save_button = QtWidgets.QPushButton(text=UI_TEXT["save_button_text"])

        self.create_sip_button = QtWidgets.QPushButton(text=UI_TEXT["create_sip_button_text"])
        self.create_sip_button.setEnabled(False)

        self.grid_layout.addWidget(self.series_label, 0, 0, 1, 4)
        self.grid_layout.addWidget(self.default_sorting_button, 0, 4, 1, 1)
        self.grid_layout.addWidget(self.name_extension_checkbox, 1, 0)
        self.grid_layout.addWidget(self.show_bad_rows_checkbox, 1, 1)
        self.grid_layout.addWidget(self.show_dossiers_only_checkbox, 1, 2)
        self.grid_layout.addWidget(self.column_dropdown, 1, 3)
        self.grid_layout.addWidget(self.add_column_button, 1, 4)
        self.grid_layout.addWidget(self.table_view, 2, 0, 1, 5)
        self.grid_layout.addWidget(self.save_button, 3, 0, 1, 2)
        self.grid_layout.addWidget(self.create_sip_button, 3, 2, 1, 3)

    def setup_signals(self) -> None:
        self.show_bad_rows_checkbox.stateChanged.connect(self._bad_rows_clicked)
        self.show_dossiers_only_checkbox.stateChanged.connect(self._dossiers_only_clicked)
        self.add_column_button.clicked.connect(self._add_column_button_clicked)
        self.save_button.clicked.connect(self._save_button_clicked)
        self.create_sip_button.clicked.connect(self._create_sip_clicked)

    def _bad_rows_clicked(self, state: QtCore.Qt.CheckState) -> None:
        ...

    def _dossiers_only_clicked(self, state: QtCore.Qt.CheckState) -> None:
        ...

    def _add_column_button_clicked(self) -> None:
        ...

    def _save_button_clicked(self) -> None:
        ...

    def _create_sip_clicked(self) -> None:
        ...
