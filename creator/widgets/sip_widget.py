from PySide6 import QtWidgets, QtGui, QtCore

import os
import ftplib
import socket
import threading

from ..application import Application

from ..controllers.db_controller import SIPDBController, NotASIPDBException
from ..controllers.file_controller import FileController

from ..utils.state import State
from ..utils.state_utils.sip import SIP
from ..utils.sip_status import SIPStatus

from ..widgets.warning_dialog import WarningDialog
from ..widgets.dialog import YesNoDialog

from ..windows.sip_view import SIPView


class SIPWidget(QtWidgets.QFrame):
    def __init__(self, sip: SIP):
        super().__init__()

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self.sip = sip
        self.sip_id = sip._id
        self.sip_name = sip.name

        self.connection_details = {}

        self.metadata_df = None
        self.import_template_location = None
        self.import_template_df = None
        self.mapping = {}

        # sip location if created
        self.sip_location = ""

        self.setFrameShape(QtWidgets.QFrame.Panel)
        self.setFixedHeight(250)

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

        dossiers_scrollarea = QtWidgets.QScrollArea()
        dossiers_scrollarea.setWidgetResizable(True)
        dossiers_scrollarea.setMaximumHeight(180)
        dossiers_scrollarea.setMinimumWidth(100)
        dossiers_scrollarea.setStyleSheet("border: 0;")
        dossiers_widget.setFrameShape(QtWidgets.QFrame.Box)

        scroll_widget = QtWidgets.QWidget()
        dossiers_scrollarea.setWidget(scroll_widget)

        font = QtGui.QFont()
        font.setBold(True)
        font.setUnderline(True)
        dossier_title = QtWidgets.QLabel(text="Dossiers")
        dossier_title.setFont(font)
        dossier_widget_layout.addWidget(dossier_title)
        dossier_widget_layout.addWidget(dossiers_scrollarea)

        scroll_layout = QtWidgets.QVBoxLayout()
        scroll_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        scroll_widget.setLayout(scroll_layout)

        for dossier in self.sip.dossiers:
            label = QtWidgets.QLabel(text=dossier.dossier_label)
            scroll_layout.addWidget(label)

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
            lambda: os.startfile(self.state.configuration.sip_db_location)
        )
        self.open_explorer_button.setEnabled(False)

        self.open_edepot_button = QtWidgets.QPushButton(text="E-depot locatie")
        self.open_edepot_button.clicked.connect(
            lambda: os.startfile(
                f"{self.state.configuration.active_environment.api_url}/input/processing-list/{self.sip.edepot_sip_id}"
            )
        )
        self.open_edepot_button.setEnabled(False)

        self.delete_button = QtWidgets.QPushButton(text="Verwijder")
        self.delete_button.clicked.connect(self.delete_button_clicked)
        self.delete_button.setEnabled(False)

        controls_layout.addWidget(self.open_button)
        controls_layout.addWidget(self.upload_button)
        controls_layout.addWidget(self.open_explorer_button)
        controls_layout.addWidget(self.open_edepot_button)
        controls_layout.addWidget(self.delete_button)
        controls_layout.addStretch()

        # Layout
        layout.addWidget(sip_info_widget)
        layout.addWidget(dossiers_widget)
        layout.addWidget(controls)

    def open_button_clicked(self) -> None:
        self.__sip_view = SIPView(sip_widget=self)

        db_path = os.path.join(self.state.configuration.sip_db_location, f"{self.sip.name}.db")
        db_controller = SIPDBController(db_path)

        db_exists = os.path.exists(db_path)
        db_is_valid = db_controller.is_valid_db()

        if db_exists:
            if not db_is_valid:
                raise NotASIPDBException(f"Database laden is gefaald.\nDe database op locatie '{db_path}' is geen SIP database of is corrupt.")

            self.import_template_df = db_controller.read_data_table()
            self.__sip_view.open_grid_clicked(first_open=False)
            return
        
        # NOTE: can only continue if we can load the series
        if not self.state.check_series_loaded():
            return

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

    def delete_button_clicked(self) -> None:
        # Deletes the SIP and it's corresponding files (md5)

        dialog = YesNoDialog(
            title="Verwijder files",
            text="Ben je zeker dat je de SIP en al zijn bijhorende files wilt verwijderen?\nDeze actie kan niet ongedaan gemaakt worden.",
        )
        dialog.exec()

        if not dialog.result():
            return

        sip_location = os.path.join(
            self.state.configuration.sips_location,
            self.sip.file_name,
        )
        sidecar_location = os.path.join(
            self.state.configuration.sips_location,
            self.sip.sidecar_file_name,
        )
        db_location = os.path.join(
            self.state.configuration.sip_db_location,
            f"{self.sip.name}.db"
        )

        try:
            os.remove(sip_location)
        except FileNotFoundError:
            pass

        try:
            os.remove(sidecar_location)
        except FileNotFoundError:
            pass

        try:
            os.remove(db_location)
        except FileNotFoundError:
            pass

        self.deleteLater()

        # NOTE: set the status to deleted, this will be caught automatically and deleted appropriately
        self.sip.set_status(SIPStatus.DELETED)


    # Handlers
    def _update_status(self, status: SIPStatus) -> None:
        self.sip_status_label.setText(status.get_status_label())
        self.sip_status_label.setStyleSheet(status.value)

        if status == SIPStatus.IN_PROGRESS:
            self.open_button.setEnabled(True)
            self.upload_button.setEnabled(False)
            self.open_explorer_button.setEnabled(False)
            self.open_edepot_button.setEnabled(False)
            self.delete_button.setEnabled(False)
        elif status == SIPStatus.SIP_CREATED:
            self.open_button.setEnabled(False)
            self.upload_button.setEnabled(True)
            self.open_explorer_button.setEnabled(True)
            self.open_edepot_button.setEnabled(False)
            self.delete_button.setEnabled(True)
        elif status in (
            SIPStatus.UPLOADING,
            SIPStatus.UPLOADED,
        ):
            self.open_button.setEnabled(False)
            self.upload_button.setEnabled(False)
            self.open_explorer_button.setEnabled(True)
            self.open_edepot_button.setEnabled(False)
            self.delete_button.setEnabled(True)
        elif status in (
            SIPStatus.PROCESSING,
            SIPStatus.ACCEPTED,
            SIPStatus.REJECTED,
        ):
            self.open_button.setEnabled(False)
            self.upload_button.setEnabled(False)
            self.open_explorer_button.setEnabled(True)
            self.open_edepot_button.setEnabled(True)
            self.delete_button.setEnabled(True)

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

        # NOTE: this status will periodically get checked through the API, setting it to UPLOADED allows it to be picked up to be checked
        self.sip.set_status(SIPStatus.UPLOADED)
