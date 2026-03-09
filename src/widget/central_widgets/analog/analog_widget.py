import os
from typing import Iterable

import pandas as pd
from PySide6 import QtWidgets, QtCore

from src.controller.api_controller import APIController
from src.controller.excel_controller import ExcelController
from src.utils.constants import UI_TEXT_ELEMENTS, DB_FILE_EXTENSION
from src.utils.data_objects.analog.sip import AnalogSIP
from src.utils.data_objects.grid_data import GridData
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.workers.worker import Worker

from src.widget.central_widgets.central_widget import CentralWidget
from src.widget.central_widgets.analog.analog_grid_creation_dialog import AnalogGridCreationDialog
from src.widget.components.migration.migration_listitem_widget import MigrationSipListitemWidget
from src.widget.components.searchable_list_widget import SearchableListWidgetWithDropdown

from src.window.analog.analog_grid_window import AnalogGridWindow
from src.window.base_window import Window

UI_TEXT = UI_TEXT_ELEMENTS["analog"]["main"]


class AnalogWidget(CentralWidget):
    def __init__(self, parent_window: Window):
        super().__init__(parent_window)

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        self.start_sip_button = QtWidgets.QPushButton(
            UI_TEXT["controls"]["start_sip_button_text"]
        )

        common_controls = UI_TEXT_ELEMENTS["common"]["controls"]
        self.sip_zips_locatie_button = QtWidgets.QPushButton(
            common_controls["sip_zips_locatie_button_text"]
        )
        self.sip_databases_locatie_button = QtWidgets.QPushButton(
            common_controls["sip_databases_locatie_button_text"]
        )

        self.sip_list_widget = SearchableListWidgetWithDropdown(
            search_field="sip.name",
            dropdown_search_field="sip.status.status_label"
        )
        self.sip_list_widget.setup_ui(
            dropdown_options=[
                SIPStatus.IN_PROGRESS.status_label,
                SIPStatus.SIP_CREATED.status_label,
                SIPStatus.UPLOADING.status_label,
                SIPStatus.DELETED.status_label,
                SIPStatus.UPLOADED.status_label,
                SIPStatus.PROCESSING.status_label,
                SIPStatus.ACCEPTED.status_label,
                SIPStatus.REJECTED.status_label,
            ]
        )

        self.grid_layout.addWidget(self.sip_zips_locatie_button, 0, 0)
        self.grid_layout.addWidget(self.sip_databases_locatie_button, 0, 1)
        self.grid_layout.addWidget(self.start_sip_button, 1, 0, 1, 2)
        self.grid_layout.addWidget(self.sip_list_widget, 2, 0, 1, 2)

    def setup_signals(self) -> None:
        self.application.analog_sip_loaded_signal.connect(self.analog_sip_loaded_handler)
        self.application.application_environment_changed_signal.connect(self.environment_changed_handler)

        self.start_sip_button.clicked.connect(self._start_sip_clicked)
        self.sip_zips_locatie_button.clicked.connect(
            lambda: os.startfile(self.application.configuration.sips_location)
        )
        self.sip_databases_locatie_button.clicked.connect(
            lambda: os.startfile(self.application.configuration.analoog_location)
        )

    def load_items(self) -> Iterable[None]:
        yield

    def analog_sip_loaded_handler(self, sip: AnalogSIP) -> None:
        if sip.environment != self.application.configuration.active_environment:
            return

        listitem = MigrationSipListitemWidget(sip=sip)
        listitem.open_overdrachtslijst_signal.connect(self._open_grid_handler)
        self.sip_list_widget.add_widgets([listitem])

    def environment_changed_handler(self) -> None:
        self.sip_list_widget.clear_widgets(delete=True)

        for sip in self.application.get_sips(AnalogSIP):
            listitem = MigrationSipListitemWidget(sip=sip)
            listitem.open_overdrachtslijst_signal.connect(self._open_grid_handler)
            self.sip_list_widget.add_widgets([listitem])

    def _open_grid_handler(self, sip: AnalogSIP) -> None:
        db_controller = self.application.analog_sip_db_controller

        if not db_controller.db_exists(sip.db_name):
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["text"].format(
                    db_path=os.path.join(
                        self.application.configuration.analoog_location,
                        sip.db_name,
                    )
                ),
            )

            return

        if not sip.grid_data.has_data:
            df = db_controller.read_data(sip.db_name)
            sip.grid_data.data_as_df = df

        self.grid_window = AnalogGridWindow(sip=sip)
        self.grid_window.show()

    def _start_sip_clicked(self) -> None:
        self.creation_dialog = AnalogGridCreationDialog()
        self.creation_dialog.sip_creation_requested_signal.connect(self._on_sip_creation_requested)
        self.creation_dialog.show()

    def _on_sip_creation_requested(self, sip_name: str, series_id: str) -> None:
        self.start_sip_button.setEnabled(False)

        def background_create():
            import_template_loc = APIController.get_import_template(
                configuration=self.application.configuration,
                environment=self.application.configuration.active_environment,
                series_id=series_id,
            )

            template_df = ExcelController.read_excel(import_template_loc)
            columns = template_df.columns.tolist()

            return columns

        self._template_worker = Worker(function=background_create, is_generator=False)
        self._template_thread = QtCore.QThread()

        self._template_worker.moveToThread(self._template_thread)
        self._template_thread.started.connect(self._template_worker.run)
        self._template_worker.result_ready_signal.connect(
            lambda columns: self._on_template_downloaded(sip_name, series_id, columns)
        )
        self._template_worker.error_encountered_signal.connect(
            lambda e: self.application.error_handler(e)
        )
        self._template_worker.finished_signal.connect(self._template_thread.quit)
        self._template_worker.finished_signal.connect(self._template_thread.deleteLater)
        self._template_worker.finished_signal.connect(lambda: self.start_sip_button.setEnabled(True))

        self._template_thread.start()

    def _on_template_downloaded(self, sip_name: str, series_id: str, columns: list[str]) -> None:
        env_name = self.application.configuration.active_environment_name

        series = self.application.get_series_by_id_or_name(
            environment_name=env_name,
            series_id=series_id,
            series_name="",
        )

        if series is None:
            return

        sip = AnalogSIP()

        if not sip.set_name(sip_name):
            return

        sip.set_series(series)

        success = self.application.analog_sip_db_controller.create_sip_db(
            sip=sip,
            columns=columns,
            series_id=series_id,
            series_name=series.get_full_name(),
        )

        if not success:
            return

        df = pd.DataFrame(columns=columns)
        df.loc[0] = [""] * len(columns)
        sip.grid_data = GridData()
        sip.grid_data.data_as_df = df.fillna("")

        self.application.add_sip(sip)

        self.analog_sip_loaded_handler(sip)

        if hasattr(self, "creation_dialog") and self.creation_dialog is not None:
            self.creation_dialog.close()
            self.creation_dialog = None

        self._open_grid_handler(sip)
