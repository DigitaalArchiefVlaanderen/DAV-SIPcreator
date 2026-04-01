"""
Implementation of the listitem for a SIP
"""

import os
from contextlib import suppress

from PySide6 import QtCore, QtGui, QtWidgets

from src.controller.upload_controller import UploadController

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.digital.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.pyside_helper import clear_widget_warning_style, set_widget_warning_style

from src.widget.base_widget import BaseWidget
from src.widget.dialog.yes_no_dialog import YesNoDialog

from src.window.base_window import Window
from src.window.digital.sip_detail_window import SipDetailWindow

UI_TEXT = UI_TEXT_ELEMENTS["digital"]["main"]["sip_list"]


class SipListitemWidget(QtWidgets.QFrame):
    removed_signal = QtCore.Signal(object)

    def __init__(self, parent_window: Window, sip: SIP):
        super().__init__()

        self.parent_window = parent_window
        self.sip = sip

        self.setup_ui()

    def setup_ui(self) -> None:
        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.horizontal_layout)

        self.setFrameShape(QtWidgets.QFrame.Panel)
        self.setFixedHeight(250)

        self.sip_name_and_status_widget = SipNameAndStatusWidget(sip=self.sip)
        self.dossiers_widget = DossiersWidget(sip=self.sip)
        self.controls_widget = ControlsWidget(parent_window=self.parent_window, sip=self.sip)

        self.horizontal_layout.addWidget(self.sip_name_and_status_widget)
        self.horizontal_layout.addWidget(self.dossiers_widget)
        self.horizontal_layout.addWidget(self.controls_widget)


# Components
class SipNameAndStatusWidget(QtWidgets.QFrame):
    def __init__(self, sip: SIP):
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
        self.sip.name_changed_signal.connect(lambda: self.name_label.setText(self.sip.name))
        self.sip.status_changed_signal.connect(lambda: self.status_label.setText(self.sip.status.status_label))
        self.sip.status_changed_signal.connect(lambda: self.status_label.setStyleSheet(self.sip.status.value))


class DossiersWidget(QtWidgets.QFrame):
    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()

    def setup_ui(self) -> None:
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.vertical_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.vertical_layout)

        self.setFrameShape(QtWidgets.QFrame.Box)

        # Title
        dossiers_title_font = QtGui.QFont()
        dossiers_title_font.setBold(True)
        dossiers_title_font.setUnderline(True)
        self.dossiers_title = QtWidgets.QLabel(text=UI_TEXT["dossiers_title"])
        self.dossiers_title.setFont(dossiers_title_font)

        # Dossiers
        self.scroll_layout = QtWidgets.QVBoxLayout()
        self.scroll_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_widget.setLayout(self.scroll_layout)

        self.dossiers_scrollarea = QtWidgets.QScrollArea()
        self.dossiers_scrollarea.setWidget(self.scroll_widget)
        self.dossiers_scrollarea.setWidgetResizable(True)
        self.dossiers_scrollarea.setMaximumHeight(180)
        self.dossiers_scrollarea.setMinimumWidth(100)
        self.dossiers_scrollarea.setStyleSheet("border: 0;")

        for dossier in self.sip.dossiers:
            label = QtWidgets.QLabel(text=dossier.label_text)
            self.scroll_layout.addWidget(label)

        # Adding to layout
        self.vertical_layout.addWidget(self.dossiers_title)
        self.vertical_layout.addWidget(self.dossiers_scrollarea)


class ControlsWidget(BaseWidget):
    UI_TEXT = UI_TEXT_ELEMENTS["sip"]["controls"]

    def __init__(self, parent_window: Window, sip: SIP):
        super().__init__()

        self.sip = sip
        self.parent_window = parent_window

        self.setup_ui()
        self.setup_signals()
        self.sip_status_changed_handler()

    def setup_ui(self) -> None:
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.vertical_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.vertical_layout)

        self.open_button = QtWidgets.QPushButton(text=self.UI_TEXT["open_button_text"])

        self.upload_button = QtWidgets.QPushButton(text=self.UI_TEXT["upload_button_text"])
        self.upload_button.setEnabled(False)

        self.edepot_button = QtWidgets.QPushButton(text=self.UI_TEXT["edepot_button_text"])
        self.edepot_button.setEnabled(False)

        self.remove_button = QtWidgets.QPushButton(text=self.UI_TEXT["remove_button_text"])

        self.vertical_layout.addWidget(self.open_button)
        self.vertical_layout.addWidget(self.upload_button)
        self.vertical_layout.addWidget(self.edepot_button)
        self.vertical_layout.addWidget(self.remove_button)
        self.vertical_layout.addStretch()

    def setup_signals(self) -> None:
        # SIP signals
        self.sip.status_changed_signal.connect(self.sip_status_changed_handler)
        # NOTE: in case of the series now having been added, we may want to change the button availabilities
        self.sip.series_changed_signal.connect(self.sip_status_changed_handler)

        # Control signals
        self.open_button.clicked.connect(self.open_button_clicked_handler)
        self.upload_button.clicked.connect(self.upload_button_clicked_handler)
        self.edepot_button.clicked.connect(self.sip.open_edepot_url)
        self.remove_button.clicked.connect(self.remove_button_clicked_handler)

    # Handlers
    def open_button_clicked_handler(self) -> None:
        if (
            self.application.digital_sip_db_controller.is_valid_db(self.sip.db_name)
            and self.application.digital_sip_db_controller.read_sip_data(self.sip.db_name) is not None
        ):
            self.application.window_controller.open_digital_grid_signal.emit(self.sip)
            return

        self.application.window_controller.open_window(self.sip, SipDetailWindow)

    def upload_button_clicked_handler(self) -> None:
        self.application.start_task(
            window=self.parent_window,
            description=UI_TEXT_ELEMENTS["toolbar_info"]["digital"]["upload_right_text"],
            function=lambda: UploadController().upload_sip(sip=self.sip),
            is_generator=False,
        )

    def sip_status_changed_handler(self) -> None:
        has_series = self.sip.series is not None

        match self.sip.status:
            case SIPStatus.IN_PROGRESS:
                self.open_button.setEnabled(True)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(True)
            case SIPStatus.SIP_CREATED:
                self.open_button.setEnabled(True)
                self.upload_button.setEnabled(has_series)
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

        self._update_upload_button_style(has_series)

    def _update_upload_button_style(self, has_series: bool) -> None:
        if not has_series and self.sip.status == SIPStatus.SIP_CREATED:
            set_widget_warning_style(self.upload_button, self.UI_TEXT["upload_no_series_tooltip"])
        else:
            clear_widget_warning_style(self.upload_button)

    def remove_button_clicked_handler(self) -> None:
        dialog = YesNoDialog(
            title=self.UI_TEXT["actions"]["remove"]["title"],
            text=self.UI_TEXT["actions"]["remove"]["text"],
        )
        dialog.exec()

        if not dialog.result():
            return

        # Close any open windows for this SIP (grid, detail, folder mapping)
        self.application.window_controller.close_windows_for_sip(self.sip)

        db_location = os.path.join(self.application.configuration.sip_db_location, self.sip.db_name)

        with suppress(FileNotFoundError, PermissionError):
            os.remove(db_location)

        self.sip.set_status(SIPStatus.DELETED)

        sip_listitem_widget = self.parent()
        sip_listitem_widget.removed_signal.emit(sip_listitem_widget)
