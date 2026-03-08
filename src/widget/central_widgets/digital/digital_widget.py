"""
This file contains the implementation of the main widget for the digital view.
It also contains some controls specifically for this view.
"""
import os
from typing import Iterable

from PySide6 import QtWidgets, QtCore


from src.utils.base_object import ApplicationMixin
from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.digital.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.helper import count_files_from_dirs

from src.widget.central_widgets.central_widget import CentralWidget
from src.widget.central_widgets.digital.digital_grid_view import DigitalGridView
from src.widget.components.digital.dossier_widget import DossierWidget
from src.widget.components.searchable_list_widget import SearchableListWidgetWithSelection, SearchableListWidgetWithDropdown
from src.widget.components.digital.sip_listitem_widget import SipListitemWidget

from src.window.base_window import Window
from src.window.grid_window import GridWindow


class DigitalWidget(CentralWidget):
    UI_TEXT = UI_TEXT_ELEMENTS["digital"]["main"]

    dossier_loaded_signal = QtCore.Signal(list)

    def __init__(self, parent_window: Window):
        super().__init__(parent_window)

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        # Controls
        self.add_dossier_button = AddDossierButton()
        self.add_dossiers_button = AddDossiersButton()
        self.start_sip_button = StartSIPButton()
        self.sip_zips_locatie_button = QtWidgets.QPushButton(text=self.UI_TEXT["controls"]["sip_zips_locatie_button_text"])
        self.sip_databases_locatie_button = QtWidgets.QPushButton(text=self.UI_TEXT["controls"]["sip_databases_locatie_button_text"])

        # Lists
        self.dossier_list_widget = SearchableListWidgetWithSelection(search_field="label_text")
        self.dossier_list_widget.setup_ui(
            select_all_text=self.UI_TEXT["dossier_list"]["select_all"],
            remove_item_text=self.UI_TEXT["dossier_list"]["remove_dossiers"]
        )

        self.sip_list_widget = SearchableListWidgetWithDropdown(search_field="sip.name", dropdown_search_field="sip.status.status_label")
        self.sip_list_widget.setup_ui(
            dropdown_options=[
                SIPStatus.IN_PROGRESS.status_label,
                SIPStatus.SIP_CREATED.status_label,
                SIPStatus.UPLOADING.status_label,
                SIPStatus.DELETED.status_label,
                SIPStatus.UPLOADED.status_label,
                SIPStatus.PROCESSING.status_label,
                SIPStatus.ACCEPTED.status_label,
                SIPStatus.REJECTED.status_label
            ]
        )

        self.grid_layout.addWidget(self.add_dossier_button, 0, 0)
        self.grid_layout.addWidget(self.add_dossiers_button, 0, 1)
        self.grid_layout.addWidget(self.sip_zips_locatie_button, 0, 2)
        self.grid_layout.addWidget(self.sip_databases_locatie_button, 0, 3)
        self.grid_layout.addWidget(self.start_sip_button, 1, 2, 1, 2)
        self.grid_layout.addWidget(self.dossier_list_widget, 2, 0, 1, 2)
        self.grid_layout.addWidget(self.sip_list_widget, 2, 2, 1, 2)

    def setup_signals(self) -> None:
        self.dossier_loaded_signal.connect(self.dossiers_loaded_handler)

        self.application.digital_sip_loaded_signal.connect(self.digital_sip_loaded_handler)
        self.application.application_environment_changed_signal.connect(self.environment_changed_handler)

        self.add_dossier_button.interaction_finished_signal.connect(lambda d: self.dossier_list_widget.add_widgets([d]))
        self.add_dossier_button.interaction_finished_signal.connect(lambda d: self.application.main_db_controller.write_dossier_paths([d.path]))
        self.add_dossiers_button.interaction_finished_signal.connect(self.dossier_list_widget.add_widgets)
        self.add_dossiers_button.interaction_finished_signal.connect(lambda widgets: self.application.main_db_controller.write_dossier_paths([w.path for w in widgets]))

        self.dossier_list_widget.selection_changed_signal.connect(self.dossier_selection_changed_handler)
        self.start_sip_button.clicked.connect(lambda: self.start_sip_button.button_click_handler(selected_dossiers=self.dossier_list_widget.get_selected_items()))
        self.start_sip_button.interaction_finished_signal.connect(self.start_sip_handler)

        self.sip_zips_locatie_button.clicked.connect(lambda: os.startfile(self.application.configuration.sips_location))
        self.sip_databases_locatie_button.clicked.connect(lambda: os.startfile(self.application.configuration.sip_db_location))

    # Initial load, should get triggered from the parent window
    # NOTE: only loads the dossiers, the SIPs are loaded on application level
    def load_items(self) -> Iterable[None]:
        dossier_paths = self.application.main_db_controller.read_dossier_paths()
        self.dossier_loaded_signal.emit(dossier_paths)
        yield

    # Handlers
    # NOTE: this needs to happen here, since we cannot create widgets in a thread
    def dossiers_loaded_handler(self, dossier_paths: list[str]) -> None:
        self.dossier_list_widget.add_widgets(
            widgets=[DossierWidget(path=p) for p in dossier_paths],
            select=False
        )

    def digital_sip_loaded_handler(self, sip: SIP) -> None:
        if sip.environment != self.application.configuration.active_environment:
            return

        listitem = SipListitemWidget(parent_window=self.parent_window, sip=sip)
        self.sip_list_widget.add_widgets([listitem])

    def environment_changed_handler(self) -> None:
        self.sip_list_widget.clear_widgets()

        for sip in self.application.get_sips(SIP):
            listitem = SipListitemWidget(parent_window=self.parent_window, sip=sip)
            self.sip_list_widget.add_widgets([listitem])

    def dossier_selection_changed_handler(self) -> None:
        self.start_sip_button.setEnabled(len(self.dossier_list_widget.get_selected_items()) > 0)

    def start_sip_handler(self) -> None:
        """
        If we got here, that means a few things.
        Dossiers are currently selected, and we have less than 9999 files in the selected dossiers combined (after filtering out ignores files)

        This means we can now start the process of creating a SIP using these dossiers
        """
        sip = SIP()
        sip.set_dossiers(self.dossier_list_widget.get_selected_items())

        self.application.add_sip(sip)

        self.sip_detail_window = self.application.window_controller.open_sip_detail_window(sip=sip)

        self.dossier_list_widget.remove_selected_handler()

        self.digital_sip_loaded_handler(sip)

    def open_grid_handler(self, sip: SIP) -> None:
        if not self.application.digital_sip_db_controller.db_exists(sip.db_name):
            sip.set_data_from_dossiers()
            self.application.digital_sip_db_controller.create_sip_db(sip=sip)

        if not self.application.digital_sip_db_controller.is_valid_db(sip.db_name):
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["text"].format(
                    db_path=os.path.join(
                        self.application.configuration.sip_db_location,
                        sip.db_name
                    )
                )
            )
            return

        if not sip.grid_data.has_data:
            sip.grid_data.data_as_df = self.application.digital_sip_db_controller.read_sip_data(sip.db_name)

        self.grid_window = GridWindow(sip=sip)
        grid_view = DigitalGridView(sip=sip)
        self.grid_window.setCentralWidget(grid_view)
        self.grid_window.show()


# Controls
class AddDossierButton(QtWidgets.QPushButton):
    UI_TEXT = UI_TEXT_ELEMENTS["digital"]["main"]["controls"]["add_dossier_button"]

    interaction_finished_signal = QtCore.Signal(DossierWidget)

    def __init__(self):
        super().__init__()
        self.setText(self.UI_TEXT["button_text"])

        self.clicked.connect(self.button_click_handler)

    def button_click_handler(self) -> None:
        dossier_path = QtWidgets.QFileDialog.getExistingDirectory(
            caption=self.UI_TEXT["dialog_message"]
        )

        # Nothing was selected
        if dossier_path == "":
            return

        dossier_widget = DossierWidget(path=dossier_path)

        self.interaction_finished_signal.emit(dossier_widget)

class AddDossiersButton(QtWidgets.QPushButton, ApplicationMixin):
    UI_TEXT = UI_TEXT_ELEMENTS["digital"]["main"]["controls"]["add_dossiers_button"]

    interaction_finished_signal = QtCore.Signal(list)

    def __init__(self):
        super().__init__()
        self.setText(self.UI_TEXT["button_text"])

        self.clicked.connect(self.button_click_handler)

    def button_click_handler(self) -> None:
        dossier_path = QtWidgets.QFileDialog.getExistingDirectory(
            caption=self.UI_TEXT["dialog_message"]
        )

        # Nothing was selected
        if dossier_path == "":
            return

        paths = os.listdir(dossier_path)

        dossier_widgets = [
            DossierWidget(path=os.path.join(dossier_path, p))
            for p in paths
            if os.path.isdir(os.path.join(dossier_path, p))
        ]

        # NOTE: calculate estimated time, and warn the user if it could take a while
        estimated_seconds = len(paths) // 800

        if estimated_seconds > 2:
            self.application.notify_user_signal.emit(
                self.UI_TEXT["actions_takes_long_warning"]["title"],
                self.UI_TEXT["actions_takes_long_warning"]["text"].format(estimated_seconds=estimated_seconds)
            )

        self.interaction_finished_signal.emit(dossier_widgets)

class StartSIPButton(QtWidgets.QPushButton, ApplicationMixin):
    UI_TEXT = UI_TEXT_ELEMENTS["digital"]["main"]["controls"]["start_sip_button"]

    interaction_finished_signal = QtCore.Signal()

    def __init__(self):
        super().__init__()
        self.setText(self.UI_TEXT["button_text"])

        self.setDisabled(True)

    def button_click_handler(self, selected_dossiers: list[DossierWidget]) -> None:
        # NOTE: maximum amount of lines is 9999 + header
        amount_of_files = count_files_from_dirs([d.path for d in selected_dossiers])

        if amount_of_files > 9999:
            self.application.notify_user_signal.emit(
                self.UI_TEXT["too_many_files_warning"]["title"],
                self.UI_TEXT["too_many_files_warning"]["text"].format(amount_of_files=amount_of_files)
            )
            return
        
        self.interaction_finished_signal.emit()
