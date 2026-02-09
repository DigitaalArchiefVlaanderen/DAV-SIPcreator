from PySide6 import QtWidgets


from src.utils.constants import get_logo, UI_TEXT_ELEMENTS


class YesNoDialog(QtWidgets.QDialog):
    UI_TEXT = UI_TEXT_ELEMENTS["dialog_window"]["yes_no_dialog"]

    def __init__(self, title: str, text: str):
        super().__init__()

        self.resize(400, 300)
        self.setWindowTitle(title)

        self.setWindowIcon(get_logo())

        grid_layout = QtWidgets.QGridLayout()
        self.setLayout(grid_layout)

        yes_button = QtWidgets.QPushButton(text=self.UI_TEXT["yes"])
        no_button = QtWidgets.QPushButton(text=self.UI_TEXT["no"])

        yes_button.clicked.connect(self.accept)
        no_button.clicked.connect(self.reject)

        text_label = QtWidgets.QLabel(text=text)
        text_label.setWordWrap(True)

        grid_layout.addWidget(text_label, 0, 0, 3, 2)
        grid_layout.addWidget(yes_button, 4, 0, 1, 1)
        grid_layout.addWidget(no_button, 4, 1, 1, 1)
