from PySide6 import QtWidgets, QtGui

import os

from .widgets.searchable_list_widget import (
    SearchableListWidget,
    SearchableSelectionListView,
)
from .widgets.dossier_widget import DossierWidget
from .widgets.sip_widget import SIPWidget
from .widgets.toolbar import Toolbar

from .controllers.file_controller import FileController

from .utils.state_utils.dossier import Dossier
from .utils.state_utils.sip import SIP
from .utils.sip_status import SIPStatus


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.application = QtWidgets.QApplication.instance()

    def setup_ui(self):
        self.resize(800, 600)
        self.setWindowTitle("SIP Creator")

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        grid_layout = QtWidgets.QGridLayout()
        central_widget.setLayout(grid_layout)

        # Dossiers
        add_dossier_button = QtWidgets.QPushButton(text="Voeg dossier(s) toe")
        add_dossier_button.clicked.connect(self.add_dossier_clicked)
        self.dossiers_list_view = SearchableSelectionListView()

        grid_layout.addWidget(add_dossier_button, 0, 0)
        grid_layout.addWidget(self.dossiers_list_view, 1, 0)

        # SIPS
        create_sip_button = QtWidgets.QPushButton(text="Start SIP")
        create_sip_button.clicked.connect(self.create_sip_clicked)
        self.sip_list_view = SearchableListWidget()

        # Toolbar
        self.toolbar = Toolbar()
        self.addToolBar(self.toolbar)

        grid_layout.addWidget(create_sip_button, 0, 1)
        grid_layout.addWidget(self.sip_list_view, 1, 1)

    def load_items(self):
        for dossier in self.application.state.dossiers:
            self.dossiers_list_view.add_item(
                searchable_name_field="dossier_label",
                widget=DossierWidget(dossier=dossier),
            )

        for sip in self.application.state.sips:
            sip_widget = SIPWidget(sip=sip)
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

            self.sip_list_view.add_item(
                searchable_name_field="sip_id",
                widget=sip_widget,
            )

    def add_dossier_clicked(self):
        dossier_path = QtWidgets.QFileDialog.getExistingDirectory(
            caption="Selecteer dossier om toe te voegen"
        )

        if dossier_path != "":
            dossier = Dossier(path=dossier_path)

            self.dossiers_list_view.add_item(
                searchable_name_field="dossier_label",
                widget=DossierWidget(dossier=dossier),
            )
            self.application.state.add_dossier(dossier)

    def create_sip_clicked(self):
        selected_dossiers = list(self.dossiers_list_view.get_selected())

        if len(selected_dossiers) > 0:
            dossiers = [d.dossier for d in selected_dossiers]

            sip = SIP(
                environment_name=self.application.state.configuration.active_environment,
                dossiers=dossiers,
            )
            sip_widget = SIPWidget(sip=sip)

            success = self.sip_list_view.add_item(
                searchable_name_field="sip_id",
                widget=sip_widget,
            )

            if not success:
                return

            self.application.state.add_sip(sip)

            # Open the SIP
            sip_widget.open_button_clicked()

    def closeEvent(self, event):
        # If the main window dies, kill the whole application
        event.accept()
        self.application.quit()
