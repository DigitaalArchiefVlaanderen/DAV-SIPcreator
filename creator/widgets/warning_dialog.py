from PySide6 import QtWidgets


class WarningDialog(QtWidgets.QDialog):
    def __init__(self, title: str, text: str):
        super().__init__()

        self.resize(400, 300)
        self.setWindowTitle(title)

        vertical_layout = QtWidgets.QVBoxLayout()
        self.setLayout(vertical_layout)

        ok_button = QtWidgets.QDialogButtonBox.StandardButton.Ok

        buttonBox = QtWidgets.QDialogButtonBox(ok_button)
        buttonBox.accepted.connect(self.accept)

        text_label = QtWidgets.QLabel(text=text)
        text_label.setWordWrap(True)

        vertical_layout.addWidget(text_label)
        vertical_layout.addWidget(buttonBox)
