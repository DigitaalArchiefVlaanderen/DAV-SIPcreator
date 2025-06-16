from abc import abstractmethod

from PySide6 import QtWidgets


class MainWidget(QtWidgets.QWidget):
    @abstractmethod
    def setup_ui(self) -> None:
        pass

    @abstractmethod
    def load_items(self) -> None:
        pass