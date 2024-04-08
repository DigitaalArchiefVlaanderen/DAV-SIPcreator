from PySide6 import QtWidgets, QtGui, QtCore

import hashlib
import shutil
import os
import ftplib
import uuid

from ..utils.state_utils.sip import SIP
from ..utils.sip_status import SIPStatus
from ..utils.series import Series
from ..widgets.warning_dialog import WarningDialog
from ..windows.sip_view import SIPView
from ..controllers.file_controller import FileController


class SIPWidget(QtWidgets.QFrame):
    def __init__(self, sip: SIP):
        super().__init__()

        self.application = QtWidgets.QApplication.instance()
        self.sip = sip
        self.sip_id = sip._id

        self.connection_details = {}

        self.metadata_df = None
        self.import_template_location = None
        self.import_template_df = None
        self.mapping = {}

        # metadata file to be put in the SIP
        self.export_template_df = None

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

        controls_layout.addWidget(self.open_button)
        controls_layout.addWidget(self.upload_button)

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

        if self.import_template_df is not None:
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
            self.application.state.configuration.misc.save_location,
            FileController.SIP_STORAGE,
            self.sip.file_name,
        )

        md5 = hashlib.md5(open(sip_location, "rb").read()).hexdigest()
        sidecar_location = f"{sip_location[:-4]}.xml"

        side_car_info = """
<?xml version="1.0" encoding="UTF-8"?>
<mhs:Sidecar xmlns:mhs="https://zeticon.mediahaven.com/metadata/20.3/mhs/" version="20.3" xmlns:mh="https://zeticon.mediahaven.com/metadata/20.3/mh/">
     <mhs:Technical>
              <mh:Md5>{md5}</mh:Md5>
     </mhs:Technical>
</mhs:Sidecar>""".format(
            md5=md5
        )

        with open(sidecar_location, "w", encoding="utf-8") as f:
            f.write(side_car_info)

        with ftplib.FTP_TLS(
            self.sip.environment.ftps_url,
            self.sip.environment.ftps_username,
            self.sip.environment.ftps_password,
        ) as session:
            session.prot_p()

            with open(sip_location, "rb") as f:
                session.storbinary(f"STOR {self.sip.series._id}-{self.sip.name}.zip", f)
            with open(sidecar_location, "rb") as f:
                session.storbinary(f"STOR {self.sip.series._id}-{self.sip.name}.xml", f)

        self.sip.sip_status = SIPStatus.ARCHIVED
        self.application.state.update_sip(self.sip)
        self.sip_status_label.setText(self.sip.sip_status.get_status_label())
        self.sip_status_label.setStyleSheet(self.sip.sip_status.value)
        self.open_button.setEnabled(False)
        self.upload_button.setEnabled(False)

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


# TODO: bollekes vs vakskes
# TODO: configuratie, duidelijker knopke
# TODO: dossier verwijderen uit lijst
# TODO: lijst dossiers (zoekbalk) lijst sips (zoekbalk)
# TODO: indicatie van aantal dossiers/sips
# TODO: check max lines
# TODO: voeg dossiers toe knop
# TODO: openingsdatum < closing
# TODO: cellen doortrekken
# TODO: datum niet op stukniveau invullen, wel op dossierniveau