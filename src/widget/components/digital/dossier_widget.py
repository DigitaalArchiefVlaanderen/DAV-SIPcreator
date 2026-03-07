import os

from PySide6 import QtWidgets


from src.window.base_window import Window


class DossierWidget(QtWidgets.QLabel):
    def __init__(self, parent_window: Window, path: str):
        super().__init__()
        
        self.parent_window = parent_window
        self.path = path
        self.label_text = os.path.basename(self.path)

        self.setText(self.label_text)

    def __eq__(self, other: "DossierWidget") -> bool:
        if not isinstance(other, DossierWidget):
            return False

        return self.path == other.path
