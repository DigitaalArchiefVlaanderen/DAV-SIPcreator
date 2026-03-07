"""
Implementation of the listitem for a SIP
"""
import os
from contextlib import suppress

from PySide6 import QtWidgets, QtCore, QtGui

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.digital.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus

from src.widget.base_widget import BaseWidget
from src.widget.central_widgets.digital.sip_detail_widget import SipDetailWidget
from src.widget.dialog.yes_no_dialog import YesNoDialog

from src.window.base_window import Window


UI_TEXT = UI_TEXT_ELEMENTS["digital"]["main"]["sip_list"]

class SipListitemWidget(QtWidgets.QFrame):
    open_grid_signal = QtCore.Signal(SIP)

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
        self.controls_widget.open_grid_signal.connect(lambda: self.open_grid_signal.emit(self.sip))

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

    open_grid_signal = QtCore.Signal()

    def __init__(self, parent_window: Window, sip: SIP):
        super().__init__()

        self.sip = sip
        self.parent_window = parent_window

        self.setup_ui()
        self.setup_signals()

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

        # NOTE: we want to check if the user is trying to open a sip while the series are still loading
        self._pending_open = False
        self.application.series_retriever.finished_signal.connect(self.series_retrieval_finished_handler)

    # Handlers
    def series_retrieval_finished_handler(self) -> None:
        if self._pending_open:
            self._pending_open = False

            self.open_button_clicked_handler()

    def open_button_clicked_handler(self) -> None:
        if self.application.series_retrieval_busy:
            self._pending_open = True

            self.application.thread_error_signal.emit(
                UI_TEXT_ELEMENTS["warnings"]["series_still_loading_warning"]["title"],
                UI_TEXT_ELEMENTS["warnings"]["series_still_loading_warning"]["text"]
            )
            return

        if self.application.digital_sip_db_controller.is_valid_db(self.sip.db_name) \
                and self.application.digital_sip_db_controller.read_sip_data(self.sip.db_name):
            self.open_grid_signal.emit()
            return

        self.sip_detail_window = Window(title=self.sip.name)

        self.sip.name_changed_signal.connect(lambda: self.sip_detail_window.setWindowTitle(self.sip.name))

        self.sip_detail_widget = SipDetailWidget(parent_window=self.parent_window, sip=self.sip)
        self.sip_detail_widget.open_grid_signal.connect(self.open_grid_signal.emit)
        self.sip_detail_window.setCentralWidget(self.sip_detail_widget)

        self.sip_detail_window.show()

    # TODO
    def upload_button_clicked_handler(self) -> None:
        ...

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

    def remove_button_clicked_handler(self) -> None:
        dialog = YesNoDialog(
            title=self.UI_TEXT["actions"]["remove"]["title"],
            text=self.UI_TEXT["actions"]["remove"]["text"],
        )
        dialog.exec()

        if not dialog.result():
            return
        
        sips_location = self.application.configuration.sips_location
        sip_dbs_location = self.application.configuration.sip_db_location

        sip_location = os.path.join(sips_location, self.sip.file_name)
        sidecar_location = os.path.join(sips_location, self.sip.sidecar_file_name)
        db_location = os.path.join(sip_dbs_location, self.sip.db_name)

        with suppress(FileNotFoundError):
            os.remove(sip_location)
        with suppress(FileNotFoundError):
            os.remove(sidecar_location)
        with suppress(FileNotFoundError):
            os.remove(db_location)

        self.sip.set_status(SIPStatus.DELETED)
        self.deleteLater()
