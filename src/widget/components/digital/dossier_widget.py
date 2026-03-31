import os

from PySide6 import QtWidgets


class DossierWidget(QtWidgets.QLabel):
    def __init__(self, path: str):
        super().__init__()

        self.path = os.path.normpath(path)
        self.label_text = os.path.basename(self.path)

        self.setText(self.label_text)

    def __eq__(self, other: "DossierWidget") -> bool:
        if not isinstance(other, DossierWidget):
            return False

        return self.label_text == other.label_text
