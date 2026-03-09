import os
from contextlib import suppress

from PySide6 import QtWidgets, QtCore, QtGui

from src.utils.constants import UI_TEXT_ELEMENTS, KLANT_ROLE
from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.data_objects.sip_status import SIPStatus

from src.widget.base_widget import BaseWidget
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

        self.vertical_layout.addWidget(self.name_label)
        self.vertical_layout.addWidget(self.status_label)

    def setup_signals(self) -> None:
        self.sip.name_changed_signal.connect(self._update_name)
        self.sip.status_changed_signal.connect(self._update_status)

    def _update_name(self) -> None:
        if self.name_label is None:
            return

        self.name_label.setText(self.sip.name)

    def _update_status(self) -> None:
        if self.status_label is None:
            return

        self.status_label.setText(self.sip.status.status_label)
        self.status_label.setStyleSheet(self.sip.status.value)


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
        pass

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
            case SIPStatus.UPLOADING | SIPStatus.UPLOADED:
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

        db_location = os.path.join(
            self.application.configuration.overdrachtslijsten_location,
            self.sip.db_name
        )

        with suppress(FileNotFoundError):
            os.remove(db_location)

        self.sip.set_status(SIPStatus.DELETED)

        sip_listitem_widget = self.parent()
        sip_listitem_widget.hide()
        sip_listitem_widget.deleteLater()
