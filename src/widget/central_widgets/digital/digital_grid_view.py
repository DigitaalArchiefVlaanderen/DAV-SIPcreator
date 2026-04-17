from PySide6 import QtCore, QtWidgets

from src.controller.file_controller import FileController

from src.utils.constants import UI_TEXT_ELEMENTS, ColumnName
from src.utils.data_objects.digital.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.grid.table.common.proxy_model import TableFilter
from src.utils.grid.table.digital_data_verification_table import DigitalDataVerificationTable
from src.utils.workers.worker import Worker

from src.widget.central_widgets.base_grid_view import BaseGridView

UI_TEXT = UI_TEXT_ELEMENTS["digital"]["grid"]

NON_DUPLICATABLE_COLUMNS = {
    ColumnName.PATH_IN_SIP,
    ColumnName.TYPE,
    ColumnName.DOSSIER_REF,
    ColumnName.ANALOOG,
    ColumnName.NAAM,
    ColumnName.OPENINGSDATUM,
    ColumnName.SLUITINGSDATUM,
}


class DigitalGridView(BaseGridView):
    NON_DUPLICATABLE_COLUMNS = NON_DUPLICATABLE_COLUMNS

    def __init__(self, sip: SIP) -> None:
        super().__init__(sip)

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self._create_common_widgets(UI_TEXT)

        self.name_extension_checkbox = QtWidgets.QCheckBox(text=UI_TEXT["name_extension_checkbox_text"])
        self.name_extension_checkbox.setChecked(False)

        self.show_dossiers_only_checkbox = QtWidgets.QCheckBox(text=UI_TEXT["dossiers_only_checkbox_text"])

        self._create_table(DigitalDataVerificationTable(sip=self.sip))

        self._update_series_label()

        if self.sip.series:
            self.table_model.validate_all()

        checkbox_layout = QtWidgets.QHBoxLayout()
        checkbox_layout.addWidget(self.name_extension_checkbox)
        checkbox_layout.addWidget(self.show_bad_rows_checkbox)
        checkbox_layout.addWidget(self.show_dossiers_only_checkbox)
        checkbox_layout.addStretch()

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.save_button, 1)
        button_layout.addWidget(self.create_sip_button, 1)

        self.grid_layout.addWidget(self.series_label, 0, 0, 1, 3)
        self.grid_layout.addWidget(self.default_sorting_button, 0, 3, 1, 1)
        self.grid_layout.addLayout(checkbox_layout, 1, 0, 1, 2)
        self.grid_layout.addWidget(self.column_dropdown, 1, 2, 1, 1)
        self.grid_layout.addWidget(self.add_column_button, 1, 3, 1, 1)
        self.grid_layout.addWidget(self.table_view, 2, 0, 1, 4)
        self.grid_layout.addLayout(button_layout, 3, 0, 1, 4)

    def setup_signals(self) -> None:
        self._connect_common_signals()
        self.name_extension_checkbox.stateChanged.connect(self._name_extension_clicked)
        self.show_dossiers_only_checkbox.stateChanged.connect(self._dossiers_only_clicked)
        self.sip.series_changed_signal.connect(self._on_series_changed)

    def _on_series_changed(self) -> None:
        self._update_series_label()

        if self.sip.series:
            self.table_model.validate_all()

    def _update_create_sip_button(self) -> None:
        valid = not self.table_model.has_bad_rows and self.sip.series is not None and not self.table_model.is_validating
        self.create_sip_button.setEnabled(valid)
        self.sip.set_grid_valid(valid)

    def _name_extension_clicked(self, state: int) -> None:
        self.table_model.filter_name_column(active=state == QtCore.Qt.CheckState.Checked.value)

    def _dossiers_only_clicked(self, state: int) -> None:
        self.proxy_model.toggle_filter(TableFilter.DOSSIERS_ONLY)

    def _save_button_clicked(self) -> None:
        self.application.digital_sip_db_controller.save_data(self.sip)
        self.has_unsaved_changes = False

        self.application.notify_user_signal.emit(
            UI_TEXT["save_success"]["title"],
            UI_TEXT["save_success"]["text"],
        )

    def _create_sip_clicked(self) -> None:
        self._save_button_clicked()

        self.save_button.setEnabled(False)
        self.create_sip_button.setEnabled(False)

        strip = self.table_model.should_filter_name_column

        Worker.start(
            lambda: FileController().create_sip(sip=self.sip, strip_name_extensions=strip),
            on_result=self._on_sip_created,
            on_error=lambda e: self.application.error_handler(e),
            on_finished=self._on_create_sip_finished,
            track_in=self._active_workers,
        )

    def _on_sip_created(self, success: bool) -> None:
        if not success:
            return

        self.sip.set_status(SIPStatus.SIP_CREATED)

        self.application.notify_user_signal.emit(
            UI_TEXT["create_sip_success"]["title"],
            UI_TEXT["create_sip_success"]["text"],
        )

        self.window().close()
