from PySide6 import QtWidgets, QtCore, QtGui

from ..utils.path_loader import resource_path


class Dialog(QtWidgets.QDialog):
    def __init__(self, title: str, text: str):
        super().__init__()

        self.resize(400, 300)
        self.setWindowTitle(title)

        self.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))

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

        self.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))

        grid_layout = QtWidgets.QGridLayout()
        self.setLayout(grid_layout)

        yes_button = QtWidgets.QPushButton(text="Ja")
        no_button = QtWidgets.QPushButton(text="Nee")

        yes_button.clicked.connect(self.accept)
        no_button.clicked.connect(self.reject)

        text_label = QtWidgets.QLabel(text=text)
        text_label.setWordWrap(True)

        grid_layout.addWidget(text_label, 0, 0, 3, 2)
        grid_layout.addWidget(yes_button, 4, 0, 1, 1)
        grid_layout.addWidget(no_button, 4, 1, 1, 1)


class ChoiceDialog(QtWidgets.QDialog):
    def __init__(self, title: str, text: str, choices: list[str], default_selected=False):
        super().__init__()

        self.resize(400, 300)
        self.setWindowTitle(title)

        self.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))

        vertical_layout = QtWidgets.QVBoxLayout()
        self.setLayout(vertical_layout)

        ok_button = QtWidgets.QDialogButtonBox.StandardButton.Ok
        cancel_button = QtWidgets.QDialogButtonBox.StandardButton.Cancel

        buttonBox = QtWidgets.QDialogButtonBox(ok_button | cancel_button)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)

        text_label = QtWidgets.QLabel(text=text)
        text_label.setWordWrap(True)

        self.choices_widget = QtWidgets.QListWidget()
        for choice in choices:
            item = QtWidgets.QListWidgetItem(choice)
            item.setCheckState(QtCore.Qt.CheckState.Checked if default_selected else QtCore.Qt.CheckState.Unchecked)
            self.choices_widget.addItem(item)

        vertical_layout.addWidget(text_label)
        vertical_layout.addWidget(self.choices_widget)
        vertical_layout.addWidget(buttonBox)

    def get_selected_choices(self) -> list[str]:
        selected = [
            self.choices_widget.item(i).text()
            for i in range(self.choices_widget.count())
            if self.choices_widget.item(i).checkState() == QtCore.Qt.CheckState.Checked
        ]
        
        return selected
