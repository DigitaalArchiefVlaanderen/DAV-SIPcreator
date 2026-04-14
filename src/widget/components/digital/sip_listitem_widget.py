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

from src.widget.components.base_sip_controls_widget import BaseSipControlsWidget
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


class ControlsWidget(BaseSipControlsWidget):
    UI_TEXT = UI_TEXT_ELEMENTS["sip"]["controls"]

    def __init__(self, parent_window: Window, sip: SIP):
        self.parent_window = parent_window
        super().__init__(sip)

    def setup_signals(self) -> None:
        super().setup_signals()
        self.sip.series_changed_signal.connect(self.sip_status_changed_handler)

    def _has_edepot_info(self) -> bool:
        return True  # Digital always shows edepot button when status allows

    def _upload_allowed(self) -> bool:
        return self.sip.series is not None and self.sip.grid_valid

    def _on_status_updated(self) -> None:
        has_series = self.sip.series is not None
        if not has_series and self.sip.status == SIPStatus.SIP_CREATED:
            set_widget_warning_style(self.upload_button, self.UI_TEXT["upload_no_series_tooltip"])
        else:
            clear_widget_warning_style(self.upload_button)

    def open_button_clicked_handler(self) -> None:
        if (
            self.application.digital_sip_db_controller.is_valid_db(self.sip.db_name)
            and self.application.digital_sip_db_controller.read_sip_data(self.sip.db_name) is not None
        ):
            self.application.window_controller.open_digital_grid_signal.emit(self.sip)
            return

        self.application.window_controller.open_window(self.sip, SipDetailWindow)

    def upload_button_clicked_handler(self) -> None:
        if self.sip.status == SIPStatus.IN_PROGRESS:
            self.application.window_controller.open_digital_grid_signal.emit(self.sip)
            return

        self.application.start_task(
            window=self.parent_window,
            description=UI_TEXT_ELEMENTS["toolbar_info"]["digital"]["upload_right_text"],
            function=lambda: UploadController().upload_sip(sip=self.sip),
            is_generator=False,
        )

    def edepot_button_clicked_handler(self) -> None:
        self.sip.open_edepot_url()

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
