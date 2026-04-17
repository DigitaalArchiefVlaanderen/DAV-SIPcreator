"""Base class for SIP listitem control widgets.

Provides shared button setup, signal wiring, status handler skeleton,
and grid validity handling. Subclasses override type-specific handlers.
"""

from PySide6 import QtCore, QtWidgets

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.sip import SIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.pyside_helper import clear_widget_warning_style, set_widget_warning_style

from src.widget.base_widget import BaseWidget

UI_TEXT = UI_TEXT_ELEMENTS["sip"]["controls"]


class BaseSipControlsWidget(BaseWidget):
    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()
        self.setup_signals()
        self.sip_status_changed_handler()

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
        self.sip.grid_validity_changed_signal.connect(self._on_grid_validity_changed)

        self.open_button.clicked.connect(self.open_button_clicked_handler)
        self.upload_button.clicked.connect(self._on_upload_clicked)
        self.edepot_button.clicked.connect(self.edepot_button_clicked_handler)
        self.remove_button.clicked.connect(self.remove_button_clicked_handler)

    def _on_grid_validity_changed(self, valid: bool) -> None:
        self.sip_status_changed_handler()

    def _has_edepot_info(self) -> bool:
        """Whether this SIP has e-depot information. Override for type-specific logic."""
        return False

    def _upload_allowed(self) -> bool:
        """Whether the upload button should be enabled based on type-specific checks.
        Override to add checks like has_series."""
        return self.sip.grid_valid

    def sip_status_changed_handler(self) -> None:
        upload_allowed = self._upload_allowed()
        has_edepot = self._has_edepot_info()

        match self.sip.status:
            case SIPStatus.IN_PROGRESS:
                self.open_button.setEnabled(True)
                self.upload_button.setEnabled(upload_allowed)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(True)
            case SIPStatus.SIP_CREATED:
                self.open_button.setEnabled(True)
                self.upload_button.setEnabled(upload_allowed)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(True)
            case SIPStatus.PARTIALLY_UPLOADED:
                self.open_button.setEnabled(True)
                self.upload_button.setEnabled(upload_allowed)
                self.edepot_button.setEnabled(has_edepot)
                self.remove_button.setEnabled(True)
            case SIPStatus.UPLOADING:
                self.open_button.setEnabled(False)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(True)
            case SIPStatus.UPLOADED:
                self.open_button.setEnabled(False)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(has_edepot)
                self.remove_button.setEnabled(True)
            case SIPStatus.PROCESSING | SIPStatus.ACCEPTED:
                self.open_button.setEnabled(False)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(has_edepot)
                self.remove_button.setEnabled(True)
            case SIPStatus.REJECTED:
                self.open_button.setEnabled(True)
                self.upload_button.setEnabled(upload_allowed)
                self.edepot_button.setEnabled(has_edepot)
                self.remove_button.setEnabled(True)
            case SIPStatus.DELETED:
                self.open_button.setEnabled(False)
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(False)
                self.remove_button.setEnabled(False)
            case x:
                raise ValueError(f"Found unknown SIPStatus: {x}")

        # Show warning on edepot button when status expects edepot info but it's missing
        edepot_expected = self.sip.status in (
            SIPStatus.PARTIALLY_UPLOADED,
            SIPStatus.UPLOADED,
            SIPStatus.PROCESSING,
            SIPStatus.ACCEPTED,
            SIPStatus.REJECTED,
        )
        if edepot_expected and not has_edepot:
            set_widget_warning_style(
                self.edepot_button,
                UI_TEXT_ELEMENTS["sip"]["controls"]["edepot_not_found_tooltip"],
            )
        else:
            clear_widget_warning_style(self.edepot_button)

        self._on_status_updated()

    def _on_status_updated(self) -> None:
        """Hook for subclasses to run additional logic after status update (e.g. styling)."""

    def _on_upload_clicked(self) -> None:
        self.upload_button.setEnabled(False)
        self.upload_button_clicked_handler()

    # Abstract methods -- subclasses must override
    def open_button_clicked_handler(self) -> None:
        raise NotImplementedError

    def upload_button_clicked_handler(self) -> None:
        raise NotImplementedError

    def edepot_button_clicked_handler(self) -> None:
        raise NotImplementedError

    def remove_button_clicked_handler(self) -> None:
        raise NotImplementedError
