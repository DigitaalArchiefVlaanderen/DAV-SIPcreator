from PySide6 import QtWidgets, QtCore

from src.controller.file_controller import FileController
from src.utils.constants import ColumnName, UI_TEXT_ELEMENTS
from src.utils.data_objects.digital.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.grid.table.common.grid_table_view import GridTableView
from src.utils.grid.table.common.proxy_model import SortFilterProxyModel, TableFilter
from src.utils.grid.table.digital_data_verification_table import DigitalDataVerificationTable

from src.widget.base_widget import BaseWidget


UI_TEXT = UI_TEXT_ELEMENTS["digital"]["grid"]

NON_DUPLICATABLE_COLUMNS = {
    ColumnName.PATH_IN_SIP.value,
    ColumnName.TYPE.value,
    ColumnName.DOSSIER_REF.value,
    ColumnName.ANALOOG.value,
    ColumnName.NAAM.value,
    ColumnName.OPENINGSDATUM.value,
    ColumnName.SLUITINGSDATUM.value,
}


class DigitalGridView(BaseWidget):
    def __init__(self, sip: SIP) -> None:
        super().__init__()

        self.sip = sip
        self.has_unsaved_changes = False

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        self.series_label = QtWidgets.QLabel()
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
        self.proxy_model = SortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self.table_view = GridTableView()
        self.table_view.setModel(self.proxy_model)

        self._populate_column_dropdown()

        self.create_sip_button = QtWidgets.QPushButton(text=UI_TEXT["create_sip_button_text"])
        self.save_button = QtWidgets.QPushButton(text=UI_TEXT["save_button_text"])

        self._update_series_label()

        if self.sip.series:
            self.table_model.validate_all()

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
        self.default_sorting_button.clicked.connect(self.proxy_model.reset_sorting)
        self.name_extension_checkbox.stateChanged.connect(self._name_extension_clicked)
        self.show_bad_rows_checkbox.stateChanged.connect(self._bad_rows_clicked)
        self.show_dossiers_only_checkbox.stateChanged.connect(self._dossiers_only_clicked)
        self.add_column_button.clicked.connect(self._add_column_button_clicked)
        self.save_button.clicked.connect(self._save_button_clicked)
        self.create_sip_button.clicked.connect(self._create_sip_clicked)
        self.table_model.dataChanged.connect(self._data_changed)
        self.table_model.validation_finished_signal.connect(self._update_create_sip_button)
        self.sip.series_changed_signal.connect(self._on_series_changed)

    def _on_series_changed(self) -> None:
        self._update_series_label()

        if self.sip.series:
            self.table_model.validate_all()

    def _update_series_label(self) -> None:
        if self.sip.series:
            self.series_label.setText(self.sip.series.get_full_name())
            self.series_label.setStyleSheet("")
            self.series_label.setToolTip("")
            font = self.series_label.font()
            font.setBold(False)
            self.series_label.setFont(font)
        else:
            fallback = self.sip.saved_series_name or self.sip.name
            self.series_label.setText(fallback)
            self.series_label.setStyleSheet("color: red;")
            self.series_label.setToolTip(UI_TEXT["series_not_found_tooltip"])
            font = self.series_label.font()
            font.setBold(True)
            self.series_label.setFont(font)

        self._update_create_sip_button()

    def _populate_column_dropdown(self) -> None:
        seen = set()

        for col in self.table_model.raw_data.columns:
            base_col = col.rstrip()
            if base_col not in NON_DUPLICATABLE_COLUMNS and base_col not in seen:
                self.column_dropdown.addItem(base_col)
                seen.add(base_col)

    def _update_create_sip_button(self) -> None:
        self.create_sip_button.setEnabled(
            not self.table_model.has_bad_rows
            and self.sip.series is not None
            and not self.table_model.is_validating
        )

    def _data_changed(self) -> None:
        self.has_unsaved_changes = True
        self._update_create_sip_button()

    def _name_extension_clicked(self, state: int) -> None:
        self.table_model.filter_name_column(
            active=state == QtCore.Qt.CheckState.Checked.value
        )

    def _bad_rows_clicked(self, state: int) -> None:
        self.proxy_model.toggle_filter(TableFilter.BAD_ROWS)

    def _dossiers_only_clicked(self, state: int) -> None:
        self.proxy_model.toggle_filter(TableFilter.DOSSIERS_ONLY)

    def _add_column_button_clicked(self) -> None:
        column = self.column_dropdown.currentText()

        if not column:
            return

        df = self.table_model.raw_data

        self.table_model.beginResetModel()

        new_column_name = column
        while (new_column_name := f"{new_column_name} ") in df.columns:
            pass

        col_loc = df.columns.get_loc(column)
        spaces = len(new_column_name) - len(column)
        df.insert(col_loc + spaces, new_column_name, "")

        self.table_model.endResetModel()

    def _save_button_clicked(self) -> None:
        self.application.digital_sip_db_controller.save_data(self.sip)
        self.has_unsaved_changes = False

        self.application.notify_user_signal.emit(
            UI_TEXT["save_success"]["title"],
            UI_TEXT["save_success"]["text"],
        )

    def _create_sip_clicked(self) -> None:
        self._save_button_clicked()

        if not FileController().create_sip(sip=self.sip, strip_name_extensions=self.table_model.should_filter_name_column):
            return

        self.sip.set_status(SIPStatus.SIP_CREATED)

        self.application.notify_user_signal.emit(
            UI_TEXT["create_sip_success"]["title"],
            UI_TEXT["create_sip_success"]["text"],
        )
