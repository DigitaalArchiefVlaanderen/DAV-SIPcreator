from PySide6 import QtWidgets, QtGui, QtCore

import shutil
import os
import ftplib
import uuid
import socket
import threading

from ..application import Application

from ..controllers.file_controller import FileController

from ..utils.state import State
from ..utils.configuration import Configuration
from ..utils.state_utils.sip import SIP
from ..utils.sip_status import SIPStatus
from ..utils.series import Series

from ..widgets.warning_dialog import WarningDialog

from ..windows.sip_view import SIPView


class SIPWidget(QtWidgets.QFrame):
    def __init__(self, sip: SIP):
        super().__init__()

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self.sip = sip
        self.sip_id = sip._id

        self.connection_details = {}

        self.metadata_df = None
        self.import_template_location = None
        self.import_template_df = None
        self.mapping = {}

        # sip location if created
        self.sip_location = ""

        self.setFrameShape(QtWidgets.QFrame.Panel)

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        # SIP info
        sip_info_widget = QtWidgets.QFrame()
        sip_info_widget.setFrameShape(QtWidgets.QFrame.Box)
        sip_info_layout = QtWidgets.QVBoxLayout()
        sip_info_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        sip_info_widget.setLayout(sip_info_layout)

        # TODO: get default values for these and properly input them
        font = QtGui.QFont()
        font.setBold(True)
        font.setUnderline(True)
        self.sip_name_label = QtWidgets.QLabel(text=self.sip.name)
        self.sip_name_label.setFont(font)

        self.sip_status_label = QtWidgets.QLabel(
            text=self.sip.status.get_status_label()
        )
        self.sip_status_label.setStyleSheet(self.sip.status.value)
        self.sip.status_changed.connect(self._update_status)
        self.sip.name_changed.connect(self._update_name)

        sip_info_layout.addWidget(self.sip_name_label)
        sip_info_layout.addWidget(self.sip_status_label)

        # Dossiers
        dossiers_widget = QtWidgets.QFrame()
        dossiers_widget.setFrameShape(QtWidgets.QFrame.Box)
        dossier_widget_layout = QtWidgets.QVBoxLayout()
        dossier_widget_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        dossiers_widget.setLayout(dossier_widget_layout)

        font = QtGui.QFont()
        font.setBold(True)
        font.setUnderline(True)
        dossier_title = QtWidgets.QLabel(text="Dossiers")
        dossier_title.setFont(font)
        dossier_widget_layout.addWidget(dossier_title)

        for dossier in self.sip.dossiers:
            label = QtWidgets.QLabel(text=dossier.dossier_label)
            dossier_widget_layout.addWidget(label)

        # Controls
        controls = QtWidgets.QWidget()
        controls_layout = QtWidgets.QVBoxLayout()
        controls.setLayout(controls_layout)

        self.open_button = QtWidgets.QPushButton(text="Open")
        self.open_button.clicked.connect(self.open_button_clicked)

        self.upload_button = QtWidgets.QPushButton(text="Upload")
        self.upload_button.clicked.connect(self.upload_button_clicked)
        self.upload_button.setEnabled(False)

        self.open_explorer_button = QtWidgets.QPushButton(text="Bestandslocatie")
        self.open_explorer_button.clicked.connect(
            lambda: os.startfile(
                os.path.join(
                    self.state.configuration.misc.save_location,
                    FileController.SIP_STORAGE,
                )
            )
        )
        self.open_explorer_button.setEnabled(False)

        controls_layout.addWidget(self.open_button)
        controls_layout.addWidget(self.upload_button)
        controls_layout.addWidget(self.open_explorer_button)

        # Layout
        layout.addWidget(sip_info_widget)
        layout.addWidget(dossiers_widget)
        layout.addWidget(controls)

    def open_button_clicked(self):
        if not self.sip.environment.has_api_credentials():
            WarningDialog(
                title="Connectie fout",
                text=f"Je API connectie gegevens staan niet in orde voor omgeving '{self.sip.environment.name}'",
            ).exec()
            return

        self.__sip_view = SIPView(sip_widget=self)

        if (
            FileController.existing_grid_path(
                self.application.state.configuration, self.sip
            )
            is not None
        ):
            self.import_template_df = FileController.existing_grid(
                self.application.state.configuration, self.sip
            )
            self.__sip_view.open_grid_clicked(first_open=False)
        else:
            self.__sip_view.setup_ui()
            self.__sip_view.show()

    def upload_button_clicked(self):
        if not self.sip.environment.has_ftps_credentials():
            WarningDialog(
                title="Connectie fout",
                text=f"Je FTPS connectie gegevens staan niet in orde voor omgeving '{self.sip.environment.name}'",
            ).exec()
            return

        sip_location = os.path.join(
            self.state.configuration.misc.save_location,
            FileController.SIP_STORAGE,
            self.sip.file_name,
        )
        sidecar_location = os.path.join(
            self.state.configuration.misc.save_location,
            FileController.SIP_STORAGE,
            self.sip.sidecar_file_name,
        )

        if not os.path.exists(sip_location) or not os.path.exists(sidecar_location):
            WarningDialog(
                title="Missende bestanden",
                text="De zip of sidecar is niet aanwezig, upload kan niet verder gaan.",
            ).exec()
            return

        # Check the connection
        try:
            ftplib.FTP_TLS(
                self.sip.environment.ftps_url,
                self.sip.environment.ftps_username,
                self.sip.environment.ftps_password,
            )
        except ftplib.error_perm:
            WarningDialog(
                title="Connectie fout",
                text=f"Je FTPS connectie login gegevens staan niet in orde voor omgeving '{self.sip.environment.name}'",
            ).exec()
            return
        except socket.gaierror:
            WarningDialog(
                title="Connectie fout",
                text=f"Je FTPS connectie url staat niet in orde voor omgeving '{self.sip.environment.name}'",
            ).exec()
            return

        # Perform upload in background
        t = threading.Thread(
            target=self._perform_upload,
            kwargs={"sip_location": sip_location, "sidecar_location": sidecar_location},
        )
        self.sip.set_status(SIPStatus.UPLOADING)
        t.start()

    def get_sip_folder_structure(self) -> dict:
        def _get_dossier_folder_structure(base_path: str, dossier_path: str) -> dict:
            structure = {}

            for location in os.listdir(dossier_path):
                location_path = os.path.join(dossier_path, location)

                if os.path.isfile(location_path):
                    structure[location] = os.path.relpath(
                        location_path,
                        base_path,
                    ).replace("\\", "/")
                else:
                    structure = {
                        **structure,
                        **_get_dossier_folder_structure(base_path, location_path),
                    }

            return structure

        sip_structure = {}

        for dossier in self.dossiers:
            sip_structure = {
                **sip_structure,
                dossier.dossier_label: {
                    "Path in SIP": dossier.dossier_label,
                    "path": dossier.dossier_path,
                    "Type": "dossier",
                    "DossierRef": dossier.dossier_label,
                    # To be determined based on the files for this dossier
                    "Openingsdatum": None,
                    "Sluitingsdatum": None,
                },
                **{
                    file_name: {
                        "Path in SIP": f"{dossier.dossier_label}/{location}",
                        "path": os.path.join(dossier.dossier_path, location),
                        "Type": "stuk",
                        "DossierRef": dossier.dossier_label,
                        # There is no cross-platform way of doing this sadly
                        # nt is Windows
                        "Openingsdatum": (
                            os.path.getctime(
                                os.path.join(dossier.dossier_path, location)
                            )
                            if os.name == "nt"
                            else os.stat(
                                os.path.join(dossier.dossier_path, location)
                            ).st_birthtime
                        ),
                        # This works as a cross-platform way of getting modification time
                        "Sluitingsdatum": os.path.getmtime(
                            os.path.join(dossier.dossier_path, location)
                        ),
                    }
                    for file_name, location in _get_dossier_folder_structure(
                        dossier.dossier_path, dossier.dossier_path
                    ).items()
                },
            }

        return sip_structure

    # Handlers
    def _update_status(self, status: SIPStatus) -> None:
        self.sip_status_label.setText(status.get_status_label())
        self.sip_status_label.setStyleSheet(status.value)

        if status == SIPStatus.IN_PROGRESS:
            self.open_button.setEnabled(True)
            self.upload_button.setEnabled(False)
            self.open_explorer_button.setEnabled(False)
        elif status == SIPStatus.SIP_CREATED:
            self.open_button.setEnabled(False)
            self.upload_button.setEnabled(True)
            self.open_explorer_button.setEnabled(True)
        elif status in (
            SIPStatus.UPLOADING,
            SIPStatus.ARCHIVED,
            SIPStatus.REJECTED,
        ):
            self.open_button.setEnabled(False)
            self.upload_button.setEnabled(False)
            self.open_explorer_button.setEnabled(True)

    def _update_name(self, name: str) -> None:
        # The updating of the status is handled separately
        self.sip_name_label.setText(name)

    # Upload
    def _perform_upload(self, sip_location: str, sidecar_location: str) -> None:
        with ftplib.FTP_TLS(
            self.sip.environment.ftps_url,
            self.sip.environment.ftps_username,
            self.sip.environment.ftps_password,
        ) as session:
            session.prot_p()

            with open(sip_location, "rb") as f:
                session.storbinary(f"STOR {self.sip.file_name}", f)
            with open(sidecar_location, "rb") as f:
                session.storbinary(f"STOR {self.sip.sidecar_file_name}", f)

        self.sip.set_status(SIPStatus.ARCHIVED)
