import os
from contextlib import suppress

from PySide6 import QtWidgets, QtCore, QtGui

from src.utils.constants import UI_TEXT_ELEMENTS, KLANT_ROLE
from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.workers.worker import Worker

from src.widget.base_widget import BaseWidget
from src.widget.dialog.migration_tab_status_dialog import MigrationTabStatusDialog
from src.widget.dialog.migration_upload_dialog import MigrationUploadDialog
from src.widget.dialog.yes_no_dialog import YesNoDialog


UI_TEXT = UI_TEXT_ELEMENTS["sip"]["controls"]


class MigrationSipListitemWidget(QtWidgets.QFrame):
    open_overdrachtslijst_signal = QtCore.Signal(MigrationSIP)

    def __init__(self, sip: MigrationSIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()

    def setup_ui(self) -> None:
        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.horizontal_layout)

        self.setFrameShape(QtWidgets.QFrame.Panel)
        self.setFixedHeight(150)

        self.name_and_status_widget = MigrationNameAndStatusWidget(sip=self.sip)
        self.controls_widget = MigrationControlsWidget(sip=self.sip)

        self.controls_widget.open_overdrachtslijst_signal.connect(self.open_overdrachtslijst_signal.emit)

        self.horizontal_layout.addWidget(self.name_and_status_widget)
        self.horizontal_layout.addWidget(self.controls_widget)


class MigrationNameAndStatusWidget(QtWidgets.QFrame):
    def __init__(self, sip: MigrationSIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.vertical_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.vertical_layout)

        self.setFrameShape(QtWidgets.QFrame.Box)

        name_font = QtGui.QFont()
        name_font.setBold(True)
        name_font.setUnderline(True)
        self.name_label = QtWidgets.QLabel(text=self.sip.name)
        self.name_label.setFont(name_font)

        self.status_label = QtWidgets.QLabel(text=self.sip.status.status_label)
        self.status_label.setStyleSheet(self.sip.status.value)

        self.status_button = QtWidgets.QPushButton(text=self.sip.status.status_label)
        self.status_button.setFlat(True)
        self.status_button.setStyleSheet(self.sip.status.value)
        self.status_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.status_button.clicked.connect(self._status_button_clicked)

        self.vertical_layout.addWidget(self.name_label)
        self.vertical_layout.addWidget(self.status_label)
        self.vertical_layout.addWidget(self.status_button)

        self._update_status_visibility()

    def setup_signals(self) -> None:
        self.sip.name_changed_signal.connect(self._update_name)
        self.sip.status_changed_signal.connect(self._update_status)

    def _update_name(self) -> None:
        if self.name_label is None:
            return

        self.name_label.setText(self.sip.name)

    def _update_status(self) -> None:
        self.status_label.setText(self.sip.status.status_label)
        self.status_label.setStyleSheet(self.sip.status.value)
        self.status_button.setText(self.sip.status.status_label)
        self.status_button.setStyleSheet(self.sip.status.value)

        self._update_status_visibility()

    def _update_status_visibility(self) -> None:
        is_partially = self.sip.status == SIPStatus.PARTIALLY_UPLOADED

        self.status_label.setVisible(not is_partially)
        self.status_button.setVisible(is_partially)

    def _status_button_clicked(self) -> None:
        dialog = MigrationTabStatusDialog(series_statuses=self.sip.series_statuses)
        dialog.exec()


class MigrationControlsWidget(BaseWidget):
    open_overdrachtslijst_signal = QtCore.Signal(MigrationSIP)

    def __init__(self, sip: MigrationSIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()
        self.setup_signals()
        self.sip_status_changed_handler()
        self._update_role_visibility()

    def setup_ui(self) -> None:
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.vertical_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.vertical_layout)

        self.open_button = QtWidgets.QPushButton(text=UI_TEXT["open_button_text"])

        self.upload_button = QtWidgets.QPushButton(text=UI_TEXT["upload_button_text"])
        self.upload_button.setEnabled(False)

        self.edepot_button = QtWidgets.QPushButton(text=UI_TEXT["edepot_button_text"])
        self.edepot_button.setEnabled(False)

        self.remove_button = QtWidgets.QPushButton(text=UI_TEXT["remove_button_text"])

        self.vertical_layout.addWidget(self.open_button)
        self.vertical_layout.addWidget(self.upload_button)
        self.vertical_layout.addWidget(self.edepot_button)
        self.vertical_layout.addWidget(self.remove_button)
        self.vertical_layout.addStretch()

    def setup_signals(self) -> None:
        self.sip.status_changed_signal.connect(self.sip_status_changed_handler)
        self.application.application_role_changed_signal.connect(self._update_role_visibility)

        self.open_button.clicked.connect(self.open_button_clicked_handler)
        self.upload_button.clicked.connect(self.upload_button_clicked_handler)
        self.edepot_button.clicked.connect(self.sip.open_edepot_url)
        self.remove_button.clicked.connect(self.remove_button_clicked_handler)

    def _update_role_visibility(self) -> None:
        is_klant = self.application.configuration.active_role == KLANT_ROLE

        self.upload_button.setHidden(is_klant)
        self.edepot_button.setHidden(is_klant)

    def open_button_clicked_handler(self) -> None:
        self.open_overdrachtslijst_signal.emit(self.sip)

    def upload_button_clicked_handler(self) -> None:
        uploadable = [
            name for name, status in self.sip.series_statuses.items()
            if status == SIPStatus.SIP_CREATED
        ]

        if not uploadable:
            return

        dialog = MigrationUploadDialog(series_names=uploadable)
        dialog.exec()

        if not dialog.result():
            return

        selected = dialog.selected_series

        for series_name in selected:
            self.sip.series_statuses[series_name] = SIPStatus.UPLOADING

            self.application.migration_sip_db_controller.update_series_status(
                self.sip, series_name, SIPStatus.UPLOADING
            )

        self.sip.derive_overall_status()

        self._start_series_uploads(selected)

    def _start_series_uploads(self, series_names: list[str]) -> None:
        from src.controller.upload_controller import UploadController

        upload_controller = UploadController()
        configuration = self.application.configuration
        tables = self.application.migration_sip_db_controller.read_tables(self.sip.db_name)

        series_id_map: dict[str, str] = {}

        for table_name, uri_serieregister, _, _ in tables:
            if table_name in series_names:
                series_id_map[table_name] = uri_serieregister.rsplit("/", 1)[-1] if uri_serieregister else ""

        upload_infos: list[tuple[str, str, str]] = []

        for series_name in series_names:
            series_id = series_id_map.get(series_name, "")
            sip_file_name = f"{series_id}-{self.sip.overdrachtslijst_name}-SIPC.zip"
            sidecar_file_name = f"{series_id}-{self.sip.overdrachtslijst_name}-SIPC.xml"

            sip_location = os.path.join(configuration.sips_location, sip_file_name)
            sidecar_location = os.path.join(configuration.sips_location, sidecar_file_name)

            if not upload_controller._validate_upload(self.sip, sip_location, sidecar_location):
                self.sip.series_statuses[series_name] = SIPStatus.SIP_CREATED

                self.application.migration_sip_db_controller.update_series_status(
                    self.sip, series_name, SIPStatus.SIP_CREATED
                )

                continue

            upload_infos.append((series_name, sip_location, sidecar_location))

        if not upload_infos:
            self.sip.derive_overall_status()

            return

        def background_upload():
            results = []

            for series_name, sip_loc, sidecar_loc in upload_infos:
                try:
                    upload_controller._perform_upload(self.sip, sip_loc, sidecar_loc)
                    results.append((series_name, True))
                except Exception:
                    results.append((series_name, False))

            return results

        Worker.start(
            background_upload,
            on_result=self._on_upload_complete,
            on_error=lambda e: self.application.error_handler(e),
        )

    def _on_upload_complete(self, results: list[tuple[str, bool]]) -> None:
        for series_name, success in results:
            if success:
                self.sip.series_statuses[series_name] = SIPStatus.UPLOADED

                self.application.migration_sip_db_controller.update_series_status(
                    self.sip, series_name, SIPStatus.UPLOADED
                )
            else:
                self.sip.series_statuses[series_name] = SIPStatus.SIP_CREATED

                self.application.migration_sip_db_controller.update_series_status(
                    self.sip, series_name, SIPStatus.SIP_CREATED
                )

        self.sip.derive_overall_status()

    def sip_status_changed_handler(self) -> None:
        match self.sip.status:
            case SIPStatus.IN_PROGRESS:
                self.open_button.setEnabled(True)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(True)
            case SIPStatus.SIP_CREATED:
                self.open_button.setEnabled(True)
                self.upload_button.setEnabled(True)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(True)
            case SIPStatus.PARTIALLY_UPLOADED:
                self.open_button.setEnabled(True)
                self.upload_button.setEnabled(True)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(True)
            case SIPStatus.UPLOADING:
                self.open_button.setEnabled(False)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(True)
            case SIPStatus.UPLOADED:
                self.open_button.setEnabled(False)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(True)
            case SIPStatus.PROCESSING | SIPStatus.ACCEPTED | SIPStatus.REJECTED:
                self.open_button.setEnabled(False)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(True)
                self.remove_button.setEnabled(True)
            case SIPStatus.DELETED:
                self.open_button.setEnabled(False)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(False)
            case x:
                raise ValueError(f"Found unknown SIPStatus: {x}")

    def remove_button_clicked_handler(self) -> None:
        dialog = YesNoDialog(
            title=UI_TEXT["actions"]["remove"]["title"],
            text=UI_TEXT["actions"]["remove"]["text"],
        )
        dialog.exec()

        if not dialog.result():
            return

        with suppress(FileNotFoundError, PermissionError):
            os.remove(self.sip.db_path)

        self.sip.set_status(SIPStatus.DELETED)

        sip_listitem_widget = self.parent()
        sip_listitem_widget.hide()
        sip_listitem_widget.deleteLater()
