import os

from PySide6 import QtWidgets

from src.utils.constants import UI_TEXT_ELEMENTS, get_logo

UI_TEXT = UI_TEXT_ELEMENTS["migration"]["edepot_dialog"]


class MigrationEdepotDialog(QtWidgets.QDialog):
    def __init__(self, series_edepot_ids: dict[str, str], base_url: str):
        super().__init__()

        self.series_edepot_ids = series_edepot_ids
        self.base_url = base_url

        self.resize(400, 300)
        self.setWindowTitle(UI_TEXT["title"])
        self.setWindowIcon(get_logo())

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        description_label = QtWidgets.QLabel(text=UI_TEXT["description"])
        layout.addWidget(description_label)

        for series_name, edepot_id in series_edepot_ids.items():
            button = QtWidgets.QPushButton(text=series_name)
            button.setCursor(QtWidgets.QApplication.overrideCursor() or button.cursor())
            button.clicked.connect(lambda _, eid=edepot_id: self._open_edepot(eid))
            layout.addWidget(button)

        layout.addStretch()

        close_button = QtWidgets.QPushButton(text=UI_TEXT["close_button_text"])
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)

    def _open_edepot(self, edepot_id: str) -> None:
        os.startfile(f"{self.base_url}/input/processing-list/{edepot_id}")
