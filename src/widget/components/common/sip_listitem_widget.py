from PySide6 import QtWidgets

from src.utils.base_object import ApplicationMixin
from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.sip import SIP, SIPStatus

from src.widget.dialog.yes_no_dialog import YesNoDialog


UI_TEXT = UI_TEXT_ELEMENTS["sip"]

class SipListItemWidget(QtWidgets.QFrame, ApplicationMixin):
    """
        Container widget for SIP list items for migration and analoog.
    """

    def __init__(self, sip: SIP) -> None:
        super().__init__()
        
        self.sip = sip

        self.sip.status_changed_signal.connect(self.update_status_handler)

        self.setup_ui()

    def setup_ui(self) -> None:
        self.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Raised)
        
        self.grid_layout = QtWidgets.QGridLayout(self)
        self.setLayout(self.grid_layout)

        self.name_label = NameLabel(self.sip)
        self.open_button = OpenButton(self.sip)
        self.upload_button = UploadButton(self.sip)
        self.upload_button.setEnabled(False)

        self.edepot_button = EdepotButton(self.sip)
        self.edepot_button.setEnabled(False)

        self.remove_button = RemoveButton(self.sip)

        self.grid_layout.addWidget(self.name_label, 0, 0)
        self.grid_layout.addWidget(self.open_button, 1, 0)
        self.grid_layout.addWidget(self.upload_button, 2, 0)
        self.grid_layout.addWidget(self.edepot_button, 3, 0)
        self.grid_layout.addWidget(self.remove_button, 4, 0)

    def update_status_handler(self) -> None:
        status = self.sip.status

        match status:
            case SIPStatus.IN_PROGRESS:
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(False)
            case SIPStatus.SIP_CREATED:
                self.upload_button.setEnabled(True)
                self.edepot_button.setEnabled(False)
            case SIPStatus.UPLOADING:
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(False)
            case s if s in (SIPStatus.UPLOADED, SIPStatus.PROCESSING, SIPStatus.ACCEPTED):
                self.upload_button.setEnabled(False)
                self.edepot_button.setEnabled(True)
            case SIPStatus.REJECTED:
                self.upload_button.setEnabled(True)
                self.edepot_button.setEnabled(True)
            

class NameLabel(QtWidgets.QLabel, ApplicationMixin):
    def __init__(self, sip: SIP) -> None:
        super().__init__(sip.name)
        self.sip = sip

        self.sip.name_changed_signal.connect(self.update_name)

    def update_name(self, name: str) -> None:
        self.setText(name)

class OpenButton(QtWidgets.QPushButton, ApplicationMixin):
    def __init__(self, sip: SIP) -> None:
        super().__init__(self.UI_TEXT_ELEMENTS["sip"]["controls"]["open_button_text"])
        self.sip = sip

class UploadButton(QtWidgets.QPushButton, ApplicationMixin):
    def __init__(self, sip: SIP) -> None:
        super().__init__(self.UI_TEXT_ELEMENTS["sip"]["controls"]["upload_button_text"])
        self.sip = sip

class EdepotButton(QtWidgets.QPushButton, ApplicationMixin):
    def __init__(self, sip: SIP) -> None:
        super().__init__(self.UI_TEXT_ELEMENTS["sip"]["controls"]["edepot_button_text"])
        self.sip = sip

        self.clicked.connect(self.sip.open_edepot_url)

class RemoveButton(QtWidgets.QPushButton, ApplicationMixin):
    def __init__(self, sip: SIP) -> None:
        super().__init__(self.UI_TEXT_ELEMENTS["sip"]["controls"]["remove_button_text"])
        self.sip = sip

        self.clicked.connect(self.clicked_handler)

    def clicked_handler(self) -> None:
        # Turn into yesnodialog
        dialog = YesNoDialog(
            title=self.UI_TEXT_ELEMENTS["sip"]["controls"]["actions"]["remove"]["title"],
            text=self.UI_TEXT_ELEMENTS["sip"]["controls"]["actions"]["remove"]["text"],
        )
        dialog.exec()

        if dialog.result() == QtWidgets.QDialog.DialogCode.Accepted:
            # TODO: remove
            ...
