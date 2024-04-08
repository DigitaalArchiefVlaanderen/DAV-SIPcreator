from PySide6 import QtWidgets, QtCore

import os

from ..utils.state_utils.dossier import Dossier


class DossierWidget(QtWidgets.QFrame):
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
        self.selection_changed = self.selection_button_widget.stateChanged

        remove_button_widget = QtWidgets.QPushButton(text="X")
        remove_button_widget.clicked.connect(self.delete_click)
        remove_button_widget.setMaximumWidth(20)
        layout.addWidget(remove_button_widget)

        self.setLayout(layout)

    def delete_click(self):
        QtWidgets.QApplication.instance().state.remove_dossier(self.dossier)
        self.deleteLater()

    def is_selected(self) -> bool:
        return self.selection_button_widget.isChecked()

    def set_selected(self, value: bool):
        self.selection_button_widget.setChecked(value)
