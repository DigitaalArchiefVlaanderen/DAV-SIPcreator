"""
Base class of a background worker
"""
from PySide6 import QtCore

class Worker(QtCore.QObject):
    finished = QtCore.Signal()

    def __init__(self) -> None:
        super().__init__()

        self.force_stop = False

    def run(self) -> None:
        raise NotImplementedError
