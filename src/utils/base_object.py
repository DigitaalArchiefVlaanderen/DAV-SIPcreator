from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from src.utils.application import Application


class ApplicationMixin:
    def __init__(self):
        self.application: Application = QtWidgets.QApplication.instance()


class BaseObject(QtCore.QObject, ApplicationMixin): ...
