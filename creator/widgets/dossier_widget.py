from PySide6 import QtWidgets, QtCore

import os

from ..utils.state_utils.dossier import Dossier


class DossierWidget(QtWidgets.QFrame):
    selection_changed: QtCore.Signal = QtCore.Signal()

    def __init__(self, dossier: Dossier):
        super().__init__()

        self.dossier = dossier
        self.dossier_label = dossier.dossier_label

        self.setFrameShape(QtWidgets.QFrame.Panel)

        layout = QtWidgets.QHBoxLayout()

        self.selection_button_widget = QtWidgets.QCheckBox(
            text=self.dossier.dossier_label
        )
        layout.addWidget(self.selection_button_widget)
        self.selection_button_widget.stateChanged.connect(
            lambda *_: self.selection_changed.emit()
        )

        self.setLayout(layout)

    def is_selected(self) -> bool:
        return self.selection_button_widget.isChecked()

    def set_selected(self, value: bool):
        self.selection_button_widget.setChecked(value)
