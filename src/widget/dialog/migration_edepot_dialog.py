import os

from PySide6 import QtWidgets

from src.utils.constants import UI_TEXT_ELEMENTS, get_logo
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.pyside_helper import set_widget_warning_style

UI_TEXT = UI_TEXT_ELEMENTS["migration"]["edepot_dialog"]


class MigrationEdepotDialog(QtWidgets.QDialog):
    def __init__(
        self,
        series_statuses: dict[str, SIPStatus],
        series_edepot_ids: dict[str, str],
        base_url: str,
    ):
        super().__init__()

        self.series_edepot_ids = series_edepot_ids
        self.base_url = base_url

        self.resize(400, 350)
        self.setWindowTitle(UI_TEXT["title"])
        self.setWindowIcon(get_logo())

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        description_label = QtWidgets.QLabel(text=UI_TEXT["description"])
        layout.addWidget(description_label)

        self.checkboxes: dict[str, QtWidgets.QCheckBox] = {}

        for series_name, status in series_statuses.items():
            if status != SIPStatus.UPLOADED:
                continue

            edepot_id = series_edepot_ids.get(series_name, "")

            checkbox = QtWidgets.QCheckBox(text=series_name)
            self.checkboxes[series_name] = checkbox

            if not edepot_id:
                checkbox.setEnabled(False)
                set_widget_warning_style(
                    checkbox,
                    UI_TEXT_ELEMENTS["sip"]["controls"]["edepot_not_found_tooltip"],
                )

            layout.addWidget(checkbox)

        layout.addStretch()

        button_layout = QtWidgets.QHBoxLayout()

        open_button = QtWidgets.QPushButton(text=UI_TEXT["open_button_text"])
        cancel_button = QtWidgets.QPushButton(text=UI_TEXT["close_button_text"])

        open_button.clicked.connect(self._open_clicked)
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(open_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    @property
    def selected_edepot_ids(self) -> dict[str, str]:
        return {name: self.series_edepot_ids.get(name, "") for name, cb in self.checkboxes.items() if cb.isChecked()}

    def _open_clicked(self) -> None:
        for edepot_id in self.selected_edepot_ids.values():
            if edepot_id:
                os.startfile(f"{self.base_url}/input/processing-list/{edepot_id}")

        self.accept()
