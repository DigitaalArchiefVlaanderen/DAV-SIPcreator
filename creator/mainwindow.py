import os
import json

from PySide6 import QtWidgets
import pandas as pd

from .application import Application

from .widgets.searchable_list_widget import (
    SearchableSelectionListView,
    SIPListWidget,
)
from .widgets.dossier_widget import DossierWidget
from .widgets.sip_widget import SIPWidget
from .widgets.toolbar import Toolbar
from .widgets.dialog import YesNoDialog
from .widgets.warning_dialog import WarningDialog

from .controllers.file_controller import FileController

from .utils.state import State
from .utils.state_utils.dossier import Dossier
from .utils.state_utils.sip import SIP
from .utils.sip_status import SIPStatus


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self.state.sip_edepot_failed.connect(self.fail_reason_show)

    def fail_reason_show(self, sip: SIP, reason: str):
        WarningDialog(
            title="SIP upload gefaald",
            text=f"SIP '{sip.name}' is geweigerd door het Edepot met volgende reden:\n\n{reason}",
        ).exec()

        storage_location = self.state.configuration.misc.save_location
        with open(
            os.path.join(
                storage_location, FileController.SIP_STORAGE, sip.error_file_name
            ),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                f"SIP '{sip.name}' is geweigerd door het Edepot met volgende reden:\n\n{reason}"
            )

    def setup_ui(self):
        self.resize(800, 600)
        self.setWindowTitle("SIP Creator")

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        grid_layout = QtWidgets.QGridLayout()
        central_widget.setLayout(grid_layout)

        # Dossiers
        add_dossier_button = QtWidgets.QPushButton(text="Voeg een dossier toe")
        add_dossier_button.clicked.connect(self.add_dossier_clicked)

        add_dossiers_button = QtWidgets.QPushButton(text="Voeg folder met dossiers toe")
        add_dossiers_button.clicked.connect(
            lambda: self.add_dossier_clicked(multi=True)
        )

        self.dossiers_list_view = SearchableSelectionListView()

        grid_layout.addWidget(add_dossier_button, 0, 0)
        grid_layout.addWidget(add_dossiers_button, 0, 1)
        grid_layout.addWidget(self.dossiers_list_view, 1, 0, 1, 2)

        # SIPS
        self.create_sip_button = QtWidgets.QPushButton(text="Start SIP")
        self.create_sip_button.clicked.connect(self.create_sip_clicked)
        self.create_sip_button.setEnabled(False)
        self.sip_list_view = SIPListWidget()

        # Toolbar
        self.toolbar = Toolbar()
        self.toolbar.configuration_changed.connect(self.sip_list_view.reload_widgets)
        self.addToolBar(self.toolbar)

        grid_layout.addWidget(self.create_sip_button, 0, 2, 1, 2)
        grid_layout.addWidget(self.sip_list_view, 1, 2, 1, 2)

    def load_items(self):
        removed_dossiers = []
        dossier_widgets = []

        for dossier in self.application.state.dossiers:
            if dossier.disabled:
                continue

            if not os.path.exists(dossier.path):
                removed_dossiers.append(dossier)
                continue

            dossier_widget = DossierWidget(dossier=dossier)

            dossier_widgets.append(dossier_widget)

        self.dossiers_list_view.add_items(
            widgets=dossier_widgets,
            selection_changed_callback=self.dossier_selection_changed,
            first_launch=True,
        )

        if len(removed_dossiers) > 0:
            dialog = YesNoDialog(
                title="Verwijderde dossiers",
                text="Een aantal dossiers lijken niet meer op hun plaats te staan.\nWilt u deze ook uit de lijst verwijderen?\n\nDeze boodschap zal anders blijven verschijnen.",
            )
            dialog.exec()

            if dialog.result():
                for dossier in removed_dossiers:
                    dossier.disabled = True
                    self.application.state.remove_dossier(dossier)

        missing_sips = []
        sips = self.application.state.sips
        sorted_sips = sorted(sips, key=lambda s: s.status.get_priority(), reverse=True)

        for sip in sorted_sips:
            # Check for missing sips
            if sip.status in (
                SIPStatus.SIP_CREATED,
                SIPStatus.UPLOADING,
                SIPStatus.UPLOADED,
                SIPStatus.ACCEPTED,
                SIPStatus.REJECTED,
            ):
                base_sip_path = os.path.join(
                    self.state.configuration.misc.save_location,
                    FileController.SIP_STORAGE,
                )
                # Check if the saved SIP and sidecar still exists
                if not os.path.exists(
                    os.path.join(
                        base_sip_path,
                        sip.file_name,
                    )
                    or not os.path.exists(
                        os.path.join(base_sip_path, sip.sidecare_file_name)
                    )
                ):
                    missing_sips.append(sip.name)

                    continue

            sip_widget = SIPWidget(sip=sip)

            try:
                if sip.metadata_file_path != "":
                    sip_widget.metadata_df = pd.read_excel(
                        sip.metadata_file_path, dtype=str
                    )
            except Exception:
                missing_sips.append(sip.name)
                continue

            sip.value_changed.connect(self.state.update_sip)

            # Uploading is not a valid state, could have happened because of forced shutdown during upload
            if sip.status == SIPStatus.UPLOADING:
                sip.set_status(SIPStatus.SIP_CREATED)

            result = FileController.existing_grid(
                self.application.state.configuration, sip
            )

            if result is not None:
                grid = result

                sip_widget.import_template_df = grid
                sip_widget.import_template_location = os.path.join(
                    self.application.state.configuration.misc.save_location,
                    FileController.IMPORT_TEMPLATE_STORAGE,
                    f"{sip.series._id}.xlsx",
                )

            if sip.status != SIPStatus.IN_PROGRESS:
                sip_widget.open_button.setEnabled(False)

            if sip.status == SIPStatus.SIP_CREATED:
                sip_widget.upload_button.setEnabled(True)
                
            if sip.status in (
                SIPStatus.UPLOADED,
                SIPStatus.PROCESSING,
                SIPStatus.ACCEPTED,
                SIPStatus.REJECTED,
                SIPStatus.SIP_CREATED,
            ):
                sip_widget.open_explorer_button.setEnabled(True)

            if sip.status in (SIPStatus.PROCESSING, SIPStatus.ACCEPTED, SIPStatus.REJECTED):
                sip_widget.open_edepot_button.setEnabled(True)

            self.sip_list_view.add_item(
                searchable_name_field="sip_name",
                widget=sip_widget,
            )

        if len(missing_sips) > 0:
            WarningDialog(
                title="Missende bestanden",
                text=f"Een of meerdere sips, sidecars of metadata zijn niet aanwezig.\n\nMissende sips: {json.dumps(missing_sips, indent=4)}\n\nDeze bestanden zijn nodig om gegevens in te laden, deze sips worden overgeslagen.",
            ).exec()

    def add_dossier_clicked(self, multi=False):
        dossier_path = QtWidgets.QFileDialog.getExistingDirectory(
            caption="Selecteer dossier om toe te voegen"
        )

        if dossier_path != "":
            paths = [dossier_path]

            if multi:
                paths = os.listdir(dossier_path)

            overlapping_labels = self.dossiers_list_view.get_overlapping_values(paths)

            unique_paths = [p for p in paths if p not in overlapping_labels]

            bad_dossiers = [
                os.path.normpath(os.path.join(dossier_path, partial_path))
                for partial_path in overlapping_labels
            ]
            dossiers = []
            dossier_widgets = []

            estimated_seconds = len(unique_paths) // 800

            if estimated_seconds > 2:
                WarningDialog(
                    title="Dossiers toevoegen",
                    text=f"Het toevoegen van veel dossiers kan een tijdje duren.\n\nGeschatte tijd: {estimated_seconds} seconden",
                ).exec()

            for partial_path in unique_paths:
                path = os.path.normpath(os.path.join(dossier_path, partial_path))

                # NOTE: we do not care about files in there, we only take the folders as dossiers
                if not os.path.isdir(path):
                    continue

                dossier = Dossier(path=path)
                dossiers.append(dossier)

                dossier_widget = DossierWidget(dossier=dossier)

                dossier_widgets.append(dossier_widget)

            self.dossiers_list_view.add_items(
                widgets=dossier_widgets,
                selection_changed_callback=self.dossier_selection_changed,
            )

            self.state.add_dossiers(dossiers=dossiers)

            if len(bad_dossiers) > 0:
                WarningDialog(
                    title="Dossiers niet toegevoegd",
                    text=f"Sommige dossiers overlappen in naamgeving met bestaande dossiers.\n\nDossiers die overlappen: {json.dumps(bad_dossiers, indent=4)}.\n\nVerander de namen van de dossiers (foldernamen) zodat ze uniek zijn in de lijst van dossiers en voeg opnieuw toe.",
                ).exec()

    def create_sip_clicked(self):
        selected_dossiers = list(self.dossiers_list_view.get_selected())

        if len(selected_dossiers) > 0:
            dossiers = [d.dossier for d in selected_dossiers]

            sip = SIP(
                environment_name=self.application.state.configuration.active_environment_name,
                dossiers=dossiers,
            )
            sip.value_changed.connect(self.state.update_sip)
            sip_widget = SIPWidget(sip=sip)

            success = self.sip_list_view.add_item(
                searchable_name_field="sip_id",
                widget=sip_widget,
            )

            if success:
                self.application.state.add_sip(sip)

                # Remove the dossiers from the list
                self.dossiers_list_view.remove_selected_clicked()

                # Open the SIP
                sip_widget.open_button_clicked()

    def dossier_selection_changed(self):
        self.create_sip_button.setEnabled(
            len(self.dossiers_list_view.get_selected()) > 0
        )

    def closeEvent(self, event):
        # If the main window dies, kill the whole application
        if any(
            s.status == SIPStatus.UPLOADING
            for s in self.application.db_controller.read_sips()
        ):
            WarningDialog(
                title="Upload bezig",
                text="Waarschuwing, een upload is momenteel bezig, de applicatie kan niet gesloten worden.",
            ).exec()

            event.ignore()
            return

        event.accept()
        self.application.quit()
