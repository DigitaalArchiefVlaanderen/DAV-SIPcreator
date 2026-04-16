import os

from PySide6 import QtWidgets

from src.controller.api_controller import APIController
from src.controller.sip_creation_controller import create_sip_zip, fill_import_template

from src.utils.constants import UI_TEXT_ELEMENTS, BusinessRules
from src.utils.data_objects.analog.sip import AnalogSIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.grid.table.analog_data_verification_table import (
    NON_DUPLICATABLE_COLUMNS,
    AnalogDataVerificationTable,
)
from src.utils.workers.worker import Worker

from src.widget.central_widgets.base_grid_view import BaseGridView

UI_TEXT = UI_TEXT_ELEMENTS["analog"]["grid"]


class AnalogGridView(BaseGridView):
    NON_DUPLICATABLE_COLUMNS = NON_DUPLICATABLE_COLUMNS

    def __init__(self, sip: AnalogSIP) -> None:
        super().__init__(sip)

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self._create_common_widgets(UI_TEXT)

        self.row_count_label = QtWidgets.QLabel()

        self._create_table(AnalogDataVerificationTable(sip=self.sip))

        self._update_series_label()
        self._update_row_count_label(self.table_model.count_data_rows())

        if self.sip.series:
            self.table_model.validate_all()

        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.addWidget(self.show_bad_rows_checkbox)
        controls_layout.addStretch()
        controls_layout.addWidget(self.column_dropdown)
        controls_layout.addWidget(self.add_column_button)
        controls_layout.addWidget(self.row_count_label)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.save_button, 1)
        button_layout.addWidget(self.create_sip_button, 1)

        self.grid_layout.addWidget(self.series_label, 0, 0, 1, 4)
        self.grid_layout.addWidget(self.default_sorting_button, 0, 4, 1, 1)
        self.grid_layout.addLayout(controls_layout, 1, 0, 1, 5)
        self.grid_layout.addWidget(self.table_view, 2, 0, 1, 5)
        self.grid_layout.addLayout(button_layout, 3, 0, 1, 5)

    def setup_signals(self) -> None:
        self._connect_common_signals()
        self.table_model.data_rows_changed_signal.connect(self._update_row_count_label)
        self.sip.series_changed_signal.connect(self._on_series_changed)

    def _on_series_changed(self) -> None:
        self._update_series_label()

        if self.sip.series:
            self.table_model.validate_all()

    def _update_create_sip_button(self) -> None:
        valid = (
            not self.table_model.has_bad_rows
            and self.table_model.count_data_rows() > 0
            and self.sip.series is not None
            and not self.table_model.is_validating
        )
        self.create_sip_button.setEnabled(valid)
        self.sip.set_grid_valid(valid)

    def _update_row_count_label(self, count: int) -> None:
        self.row_count_label.setText(UI_TEXT["row_count_label"].format(count=count))

        if count > BusinessRules.MAX_ROWS_PER_SERIES:
            self.row_count_label.setStyleSheet("QLabel {color: red;}")
        else:
            self.row_count_label.setStyleSheet("QLabel {color: black;}")

    def _add_column_button_clicked(self) -> None:
        column = self.column_dropdown.currentText()

        if not column:
            return

        self.table_model.insert_column(column)

    def _save_button_clicked(self, silent: bool = False) -> None:
        self.application.analog_sip_db_controller.save_data(self.sip, self.table_model.get_non_empty_df())
        self.has_unsaved_changes = False

        if not silent:
            self.application.notify_user_signal.emit(
                UI_TEXT["save_success"]["title"],
                UI_TEXT["save_success"]["text"],
            )

    def _create_sip_clicked(self) -> None:
        self._save_button_clicked(silent=True)

        self.save_button.setEnabled(False)
        self.create_sip_button.setEnabled(False)

        self._create_sip_worker = Worker.start(
            self._background_create_sip,
            on_result=self._on_sip_created,
            on_error=lambda e: self.application.error_handler(e),
            on_finished=self._on_create_sip_finished,
        )

    def _background_create_sip(self) -> bool:
        non_empty_df = self.table_model.get_non_empty_df()

        if len(non_empty_df) > BusinessRules.MAX_ROWS_PER_SERIES:
            self.application.notify_user_signal.emit(
                UI_TEXT["too_many_rows_error"]["title"],
                UI_TEXT["too_many_rows_error"]["text"].format(
                    max_rows=BusinessRules.MAX_ROWS_PER_SERIES, found_rows=len(non_empty_df)
                ),
            )
            return False

        configuration = self.application.configuration
        configuration.create_locations()

        import_template_loc = APIController.get_import_template(
            configuration=configuration,
            environment=self.sip.environment,
            series_id=self.sip.series._id,
        )

        temp_loc = os.path.join(configuration.grid_location, f"temp_{self.sip.series._id}.xlsx")
        sip_location = os.path.join(configuration.sips_location, self.sip.file_name)
        sidecar_location = os.path.join(configuration.sips_location, self.sip.sidecar_file_name)

        fill_import_template(non_empty_df, import_template_loc, temp_loc)

        try:
            create_sip_zip(temp_loc, sip_location, sidecar_location)
        finally:
            os.remove(temp_loc)

        return True

    def _on_sip_created(self, success: bool) -> None:
        if not success:
            return

        self.sip.set_status(SIPStatus.SIP_CREATED)

        self.application.notify_user_signal.emit(
            UI_TEXT["create_sip_success"]["title"],
            UI_TEXT["create_sip_success"]["text"],
        )

        self.window().close()
