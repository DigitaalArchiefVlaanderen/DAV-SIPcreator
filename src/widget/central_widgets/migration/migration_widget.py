import os
from typing import Iterable

import pandas as pd
from PySide6 import QtWidgets

from src.controller.excel_controller import ExcelController
from src.utils.constants import UI_TEXT_ELEMENTS, KLANT_ROLE
from src.utils.data_objects.grid_data import GridData
from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.data_objects.sip_status import SIPStatus

from src.widget.central_widgets.central_widget import CentralWidget
from src.widget.components.migration.migration_listitem_widget import MigrationSipListitemWidget
from src.widget.components.searchable_list_widget import SearchableListWidgetWithDropdown

from src.window.base_window import Window
from src.window.migration.migration_tab_window import MigrationTabWindow


class MigrationWidget(CentralWidget):
    UI_TEXT = UI_TEXT_ELEMENTS["migration"]["main"]

    def __init__(self, parent_window: Window):
        super().__init__(parent_window)

        self.setup_ui()
        self.setup_signals()
        self._update_role_visibility()

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        self.import_overdrachtslijst_button = QtWidgets.QPushButton(
            self.UI_TEXT["controls"]["import_overdrachtslijst_button"]["button_text"]
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
        self.grid_layout.addWidget(self.import_overdrachtslijst_button, 1, 0, 1, 2)
        self.grid_layout.addWidget(self.sip_list_widget, 2, 0, 1, 2)

    def setup_signals(self) -> None:
        self.application.migration_sip_loaded_signal.connect(self.migration_sip_loaded_handler)
        self.application.application_environment_changed_signal.connect(self.environment_changed_handler)
        self.application.application_role_changed_signal.connect(self._update_role_visibility)

        self.import_overdrachtslijst_button.clicked.connect(self._import_overdrachtslijst_clicked)
        self.sip_zips_locatie_button.clicked.connect(
            lambda: os.startfile(self.application.configuration.sips_location)
        )
        self.sip_databases_locatie_button.clicked.connect(
            lambda: os.startfile(self.application.configuration.overdrachtslijsten_location)
        )

    def load_items(self) -> Iterable[None]:
        yield

    def migration_sip_loaded_handler(self, sip: MigrationSIP) -> None:
        if sip.environment != self.application.configuration.active_environment:
            return

        listitem = MigrationSipListitemWidget(sip=sip)
        listitem.open_overdrachtslijst_signal.connect(self.open_overdrachtslijst_handler)
        self.sip_list_widget.add_widgets([listitem])

    def environment_changed_handler(self) -> None:
        self.sip_list_widget.clear_widgets(delete=True)

        for sip in self.application.get_sips(MigrationSIP):
            listitem = MigrationSipListitemWidget(sip=sip)
            listitem.open_overdrachtslijst_signal.connect(self.open_overdrachtslijst_handler)
            self.sip_list_widget.add_widgets([listitem])

    def open_overdrachtslijst_handler(self, sip: MigrationSIP) -> None:
        db_controller = self.application.migration_sip_db_controller

        if not db_controller.db_exists(sip.db_name):
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["text"].format(
                    db_path=os.path.join(
                        self.application.configuration.overdrachtslijsten_location,
                        sip.db_name,
                    )
                ),
            )
            return

        if not sip.main_grid_data.has_data:
            main_df = db_controller.read_main_data(sip.db_name)
            sip.main_grid_data.data_as_df = main_df

        self.tab_window = MigrationTabWindow(sip=sip)
        self.tab_window.show()

    def _update_role_visibility(self) -> None:
        is_klant = self.application.configuration.active_role == KLANT_ROLE

        self.import_overdrachtslijst_button.setHidden(is_klant)

    def _import_overdrachtslijst_clicked(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            caption=self.UI_TEXT["controls"]["import_overdrachtslijst_button"]["dialog_message"],
            filter="Excel bestanden (*.xlsx *.xlsm *.xltx *.xltm)",
        )

        if not file_path:
            return

        overdrachtslijst_name = os.path.splitext(os.path.basename(file_path))[0]

        sip = MigrationSIP()
        sip.set_name(overdrachtslijst_name)
        sip.overdrachtslijst_name = overdrachtslijst_name

        df = ExcelController.read_excel(file_path)
        sip.main_grid_data = GridData()
        sip.main_grid_data.data_as_df = df.fillna("")
        sip.grid_data = sip.main_grid_data

        self.application.migration_sip_db_controller.create_sip_db(sip)
        self.application.add_sip(sip)

        self.migration_sip_loaded_handler(sip)
