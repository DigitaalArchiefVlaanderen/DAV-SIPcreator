from PySide6 import QtWidgets

from src.utils.base_object import ApplicationMixin


class BaseWidget(QtWidgets.QWidget, ApplicationMixin):
    ...