from PySide6 import QtWidgets


class Dialog(QtWidgets.QDialog):
    def __init__(self, title: str, text: str):
        super().__init__()

        self.resize(400, 300)
        self.setWindowTitle(title)

        vertical_layout = QtWidgets.QVBoxLayout()
        self.setLayout(vertical_layout)

        ok_button = QtWidgets.QDialogButtonBox.StandardButton.Ok
        cancel_button = QtWidgets.QDialogButtonBox.StandardButton.Cancel

        buttonBox = QtWidgets.QDialogButtonBox(ok_button | cancel_button)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        text_label = QtWidgets.QLabel(text=text)
        text_label.setWordWrap(True)

        vertical_layout.addWidget(text_label)
        vertical_layout.addWidget(buttonBox)


class YesNoDialog(QtWidgets.QDialog):
    def __init__(self, title: str, text: str):
        super().__init__()

        self.resize(400, 300)
        self.setWindowTitle(title)

        vertical_layout = QtWidgets.QVBoxLayout()
        self.setLayout(vertical_layout)

        yes_button = QtWidgets.QDialogButtonBox.StandardButton.Yes
        no_button = QtWidgets.QDialogButtonBox.StandardButton.No

        buttonBox = QtWidgets.QDialogButtonBox(yes_button | no_button)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        text_label = QtWidgets.QLabel(text=text)
        text_label.setWordWrap(True)

        vertical_layout.addWidget(text_label)
        vertical_layout.addWidget(buttonBox)
