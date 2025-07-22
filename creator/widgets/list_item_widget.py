import os
import time
import ftplib
import threading
import sqlite3 as sql

from PySide6 import QtWidgets, QtCore

from creator.application import Application

from creator.controllers.api_controller import APIController

from creator.utils.configuration import Environment
from creator.utils.state import State
from creator.utils.analoog.list_item import ListItem

from creator.widgets.dialog import Dialog
from creator.widgets.warning_dialog import WarningDialog

from creator.windows.analoog.analoog_grid_view import AnaloogGridView


class ListItemWidget(QtWidgets.QWidget):
    edepot_id_found: QtCore.Signal = QtCore.Signal(
        *(str,), arguments=["edepot_id"]
    )
    updated_data_changed_since_last_upload: QtCore.Signal = QtCore.Signal()

    def __init__(self, list_item: ListItem):
        super().__init__()

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self.environment: Environment = self.state.configuration.active_environment

        self.list_item = list_item

        # NOTE: just a workaround at the moment for the listview
        self.name = self.list_item.name

        self.grid_view = AnaloogGridView(
            list_item=self.list_item
        )
        self.grid_view.setup_ui()

        self.setup_ui()

    def setup_ui(self) -> None:
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        title = QtWidgets.QLabel(text=self.list_item.name)

        self.open_button = QtWidgets.QPushButton(text="Open")
        self.open_button.clicked.connect(self.open_button_clicked)

        self.upload_button = QtWidgets.QPushButton(text="Upload")
        self.upload_button.clicked.connect(self.upload_button_clicked)
        self.upload_button.setEnabled(self.list_item.data_changed_since_last_upload and self.grid_view.model.is_data_valid())

        # NOTE: even if the data is not saved yet, we need to enable the button
        self.grid_view.model.data_changed.connect(lambda: self.upload_button.setEnabled(self.grid_view.model.is_data_valid()))
        self.updated_data_changed_since_last_upload.connect(lambda: self.upload_button.setEnabled(False))

        self.edepot_button = QtWidgets.QPushButton(text="Open E-depot")
        self.edepot_button.clicked.connect(self.edepot_button_clicked)
        self.edepot_button.setEnabled(self.list_item.edepot_id != "")
        self.edepot_id_found.connect(self.edepot_id_found_handler)

        layout.addWidget(title, 0, 0, 1, 3)
        layout.addWidget(self.open_button, 0, 3)
        layout.addWidget(self.upload_button, 1, 3)
        layout.addWidget(self.edepot_button, 2, 3)

    def open_button_clicked(self) -> None:
        self.grid_view.show()
    
    def upload_button_clicked(self) -> None:
        if not self.environment.has_ftps_credentials():
            WarningDialog(
                title="Connectie fout",
                text=f"Je FTPS connectie gegevens staan niet in orde voor omgeving '{self.sip.environment.name}'",
            ).exec()
            return

        # NOTE: disable button now
        self.upload_button.setEnabled(False)

        sip_location = os.path.join(self.state.configuration.sips_location, f"{self.list_item.grid.series._id}-{self.list_item.name}-SIPC.zip")
        md5_location = os.path.join(self.state.configuration.sips_location, f"{self.list_item.grid.series._id}-{self.list_item.name}-SIPC.xml")
        
        self.grid_view.create_sip_click(manual=False)

        t = threading.Thread(
            target=self._perform_upload,
            kwargs=dict(
                sip_location=sip_location,
                md5_location=md5_location,
            )
        )
        t.start()

        Dialog(
            title="Upload gestart",
            text="De upload is succesvol gestart."
        ).exec()

    def _perform_upload(self, sip_location: str, md5_location: str) -> None:
        with ftplib.FTP_TLS(
            self.environment.ftps_url,
            self.environment.ftps_username,
            self.environment.ftps_password,
        ) as session:
            session.prot_p()

            with open(sip_location, "rb") as f:
                session.storbinary(f"STOR {os.path.basename(sip_location)}", f)
            with open(md5_location, "rb") as f:
                session.storbinary(f"STOR {os.path.basename(md5_location)}", f)

        self._update_edepot_id()
        self._update_data_changed_since_last_upload()

    def _update_edepot_id(self) -> None:
        edepot_id = None

        while edepot_id is None:
            print(f"Starting to check for {self.list_item.name} - {self.list_item.grid.series.name}")
            # NOTE: wait some time for the edepot to pick them up
            time.sleep(10)

            edepot_id = APIController.get_sip_id_for_name(
                self.environment,
                f"{self.list_item.grid.series._id}-{self.list_item.name}-SIPC.zip"
            )
            
        print(f"id found: {edepot_id} for {self.list_item.grid.series._id}-{self.list_item.name}")

        with sql.connect(self.list_item.source_path) as conn:
            conn.execute(f'''
                UPDATE extra
                SET edepot_id='{edepot_id}';
            ''')

        self.edepot_id_found.emit(edepot_id)

    def _update_data_changed_since_last_upload(self) -> None:
        with sql.connect(self.list_item.source_path) as conn:
            conn.execute(f'''
                UPDATE extra
                SET data_changed_since_last_upload=0;
            ''')
        
        self.updated_data_changed_since_last_upload.emit()

    def edepot_id_found_handler(self, edepot_id: str) -> None:
        self.list_item.edepot_id = edepot_id
        self.edepot_button.setEnabled(edepot_id != "")

    def edepot_button_clicked(self) -> None:
        if self.list_item.edepot_id != "":
            os.startfile(
                f"{self.environment.api_url}/input/processing-list/{self.list_item.edepot_id}"
            )
