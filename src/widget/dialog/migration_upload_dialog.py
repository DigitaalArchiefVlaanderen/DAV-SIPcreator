from PySide6 import QtWidgets, QtCore

from src.utils.constants import get_logo, UI_TEXT_ELEMENTS


UI_TEXT = UI_TEXT_ELEMENTS["migration"]["upload_dialog"]


class MigrationUploadDialog(QtWidgets.QDialog):
    def __init__(self, series_names: list[str]):
        super().__init__()

        self.selected_series: list[str] = []

        self.resize(400, 350)
        self.setWindowTitle(UI_TEXT["title"])
        self.setWindowIcon(get_logo())

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        description_label = QtWidgets.QLabel(text=UI_TEXT["description"])
        layout.addWidget(description_label)

        self.checkboxes: dict[str, QtWidgets.QCheckBox] = {}

        for name in series_names:
            checkbox = QtWidgets.QCheckBox(text=name)
            self.checkboxes[name] = checkbox
            layout.addWidget(checkbox)

        layout.addStretch()

        button_layout = QtWidgets.QHBoxLayout()

        upload_button = QtWidgets.QPushButton(text=UI_TEXT["upload_button_text"])
        cancel_button = QtWidgets.QPushButton(text=UI_TEXT["cancel_button_text"])

        upload_button.clicked.connect(self._upload_clicked)
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(upload_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def _upload_clicked(self) -> None:
        self.selected_series = [
            name for name, cb in self.checkboxes.items() if cb.isChecked()
        ]

        if not self.selected_series:
            return

        self.accept()
