"""
This file contains the implementation of the main widget for the digital view.
It also contains some controls specifically for this view.
"""
import os
from typing import Iterable

from PySide6 import QtWidgets, QtCore


from src.utils.base_object import ApplicationMixin
from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.sip import SIP, SIPStatus
from src.utils.helper import count_files_from_dirs
from src.utils.pyside_helper import Helper

from src.widget.base_widget import BaseWidget
from src.widget.central_widgets.sip_detail_widget import SipDetailWidget
from src.widget.components.dossier_widget import DossierWidget
from src.widget.components.searchable_list_widget import SearchableListWidgetWithSelection, SearchableListWidgetWithDropdown
from src.widget.components.sip_listitem_widget import SipListitemWidget
from src.widget.dialog.warning_dialog import WarningDialog

from src.window.base_window import Window


class DigitalWidget(BaseWidget):
    UI_TEXT = UI_TEXT_ELEMENTS["digital"]["main"]

    dossier_loaded_signal = QtCore.Signal(list)
    sip_loaded_signal = QtCore.Signal(SIP)

    def __init__(self):
        super().__init__()

        self.dossier_loaded_signal.connect(self.dossiers_loaded_handler)
        self.sip_loaded_signal.connect(self.sip_loaded_handler)

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        # Controls
        self.add_dossier_button = AddDossierButton()
        self.add_dossiers_button = AddDossiersButton()
        self.start_sip_button = StartSIPButton()
        
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
        self.grid_layout.addWidget(self.start_sip_button, 0, 2, 1, 2)
        self.grid_layout.addWidget(self.dossier_list_widget, 1, 0, 1, 2)
        self.grid_layout.addWidget(self.sip_list_widget, 1, 2, 1, 2)


        # Signal setup
        self.add_dossier_button.interaction_finished_signal.connect(lambda d: self.dossier_list_widget.add_widgets([d]))
        self.add_dossier_button.interaction_finished_signal.connect(lambda d: self.application.main_db_controller.write_dossier_paths([d.path]))
        self.add_dossiers_button.interaction_finished_signal.connect(self.dossier_list_widget.add_widgets)
        self.add_dossiers_button.interaction_finished_signal.connect(lambda widgets: self.application.main_db_controller.write_dossier_paths([w.path for w in widgets]))

        self.dossier_list_widget.selection_changed_signal.connect(self.dossier_selection_changed_handler)
        self.start_sip_button.clicked.connect(lambda: self.start_sip_button.button_click_handler(selected_dossiers=self.dossier_list_widget.get_selected_items()))
        self.start_sip_button.interaction_finished_signal.connect(self.start_sip_handler)

    # Initial load, should get triggered from the parent window
    def load_items(self) -> Iterable[None]:
        dossier_paths = self.application.main_db_controller.read_dossier_paths()
        self.dossier_loaded_signal.emit(dossier_paths)

        # NOTE: this is a bit ugly but it will have to do
        # We need some data from the db, which happens in the background
        # But to fully make the sip, we also need to verify the data vs the API
        # Which also happens in the background
        # And to avoid either one having to wait for the other (since we need UI updates)
        # We just pass the necessary info to here, then wait after we've done the UI updates
        sip_items: list[tuple[SIP, str, str]] = []

        for sip, series_id, series_name in self.application.sip_db_controller.g_read_all_sip_dbs():
            self.sip_loaded_signal.emit(sip)
            sip_items.append((sip, series_id, series_name))

            # NOTE: I know this looks really strange, but we don't actually need to yield anything
            # This is setup since this will be used in a thread, in which case we can use it as a generator
            # Which tends to work better
            yield

        Helper().wait_for_series_loaded(warn=False)
        for sip, series_id, series_name in sip_items:
            sip.set_series(
                self.application.get_series_by_id_or_name(
                    sip.environment.name, 
                    series_id,
                    series_name
                )
            )

    # NOTE: this needs to happen here, since we cannot create widgets in a thread
    def dossiers_loaded_handler(self, dossier_paths: list[str]) -> None:
        dossier_widgets = [DossierWidget(p) for p in dossier_paths]

        self.dossier_list_widget.add_widgets(dossier_widgets, select=False)

    # NOTE: this needs to happen here, since we cannot create widgets in a thread
    def sip_loaded_handler(self, sip: SIP) -> None:
        self.sip_list_widget.add_widgets([SipListitemWidget(sip)])

    # Handlers
    def dossier_selection_changed_handler(self) -> None:
        self.start_sip_button.setEnabled(len(self.dossier_list_widget.get_selected_items()) > 0)

    def start_sip_handler(self) -> None:
        """
        If we got here, that means a few things.
        Dossiers are currently selected, and we have less than 9999 files in the selected dossiers combined (after filtering out ignores files)

        This means we can now start the process of creating a SIP using these dossiers
        """
        self.sip_detail_window = Window()

        sip = SIP()
        sip.set_dossiers(self.dossier_list_widget.get_selected_items())
        self.dossier_list_widget.remove_selected_handler()
        self.application.main_db_controller.delete_dossier_paths([w.path for w in self.dossier_list_widget.get_selected_items()])

        self.sip_listitem_widget = SipListitemWidget(sip=sip)
        self.sip_listitem_widget.open_grid_signal.connect(self.open_grid_handler)
        self.sip_list_widget.add_widgets([self.sip_listitem_widget])

        self.sip_detail_widget = SipDetailWidget(parent_window=self.sip_detail_window, sip=sip)
        self.sip_detail_window.setCentralWidget(self.sip_detail_widget)

        self.sip_detail_window.show()

    # TODO
    def open_grid_handler(self, sip: SIP) -> None:
        """
            All the values should already be in place in the sip,
            only some checks are left and then opening the grid
        """
        

        if not self.application.sip_db_controller.is_valid_db(sip.db_name):
            self.application.thread_error_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["invalid_database_error"]["text"].format(db_path=os.path.join(self.application.configuration.sip_db_location, self.sip.db_name))
            )
            return

        ...


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
            DossierWidget(path=p)
            for p in paths
            if os.path.isdir(os.path.join(dossier_path, p))
        ]

        # NOTE: calculate estimated time, and warn the user if it could take a while
        estimated_seconds = len(paths) // 800

        if estimated_seconds > 2:
            self.application.thread_error_signal.emit(
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
            self.application.thread_error_signal.emit(
                self.UI_TEXT["too_many_files_warning"]["title"],
                self.UI_TEXT["too_many_files_warning"]["text"].format(amount_of_files=amount_of_files)
            )
            return
        
        self.interaction_finished_signal.emit()
