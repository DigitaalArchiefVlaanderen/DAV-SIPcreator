import os
from contextlib import suppress

from PySide6 import QtCore, QtGui, QtWidgets

from src.utils.constants import KLANT_ROLE, UI_TEXT_ELEMENTS
from src.utils.data_objects.analog.sip import AnalogSIP
from src.utils.data_objects.sip_status import SIPStatus

from src.widget.components.base_sip_controls_widget import BaseSipControlsWidget
from src.widget.dialog.yes_no_dialog import YesNoDialog

from src.window.base_window import Window

UI_TEXT = UI_TEXT_ELEMENTS["sip"]["controls"]


class AnalogSipListitemWidget(QtWidgets.QFrame):
    open_grid_signal = QtCore.Signal(AnalogSIP)

    def __init__(self, parent_window: Window, sip: AnalogSIP):
        super().__init__()

        self.sip = sip

        self.setup_ui(parent_window)

    def setup_ui(self, parent_window: Window) -> None:
        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.horizontal_layout)

        self.setFrameShape(QtWidgets.QFrame.Panel)
        self.setFixedHeight(150)

        self.name_and_status_widget = AnalogNameAndStatusWidget(sip=self.sip)
        self.controls_widget = AnalogControlsWidget(parent_window=parent_window, sip=self.sip)

        self.controls_widget.open_grid_signal.connect(self.open_grid_signal.emit)

        self.horizontal_layout.addWidget(self.name_and_status_widget)
        self.horizontal_layout.addWidget(self.controls_widget)


class AnalogNameAndStatusWidget(QtWidgets.QFrame):
    def __init__(self, sip: AnalogSIP):
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


class AnalogControlsWidget(BaseSipControlsWidget):
    open_grid_signal = QtCore.Signal(AnalogSIP)

    def __init__(self, parent_window: Window, sip: AnalogSIP):
        self.parent_window = parent_window
        super().__init__(sip)
        self._update_role_visibility()

    def setup_signals(self) -> None:
        super().setup_signals()
        self.sip.series_changed_signal.connect(self.sip_status_changed_handler)
        self.application.application_role_changed_signal.connect(self._update_role_visibility)

    def _has_edepot_info(self) -> bool:
        return bool(self.sip.edepot_sip_id)

    def _upload_allowed(self) -> bool:
        return self.sip.series is not None and self.sip.grid_valid

    def _update_role_visibility(self) -> None:
        is_klant = self.application.configuration.active_role == KLANT_ROLE

        self.upload_button.setHidden(is_klant)
        self.edepot_button.setHidden(is_klant)

    def open_button_clicked_handler(self) -> None:
        self.open_grid_signal.emit(self.sip)

    def upload_button_clicked_handler(self) -> None:
        if self.sip.status == SIPStatus.IN_PROGRESS:
            self.open_grid_signal.emit(self.sip)
            return

        from src.controller.upload_controller import UploadController

        self.application.start_task(
            window=self.parent_window,
            description=UI_TEXT_ELEMENTS["toolbar_info"]["analog"]["upload_right_text"],
            function=lambda: UploadController().upload_sip(sip=self.sip),
            is_generator=False,
        )

    def edepot_button_clicked_handler(self) -> None:
        self.sip.open_edepot_url()

    def remove_button_clicked_handler(self) -> None:
        dialog = YesNoDialog(
            title=UI_TEXT["actions"]["remove"]["title"],
            text=UI_TEXT["actions"]["remove"]["text"],
        )
        dialog.exec()

        if not dialog.result():
            return

        self.application.window_controller.close_windows_for_sip(self.sip)

        with suppress(FileNotFoundError, PermissionError):
            os.remove(self.sip.db_path)

        self.sip.set_status(SIPStatus.DELETED)

        sip_listitem_widget = self.parent()
        sip_listitem_widget.hide()
        sip_listitem_widget.deleteLater()
