from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6 import QtWidgets

from src.utils.base_object import ApplicationMixin

if TYPE_CHECKING:
    from src.window.base_window import Window


class BaseWidget(QtWidgets.QWidget, ApplicationMixin): ...


class ComponentWidget(BaseWidget):
    def __init__(self, parent_window: Window) -> None:
        super().__init__()

        self.parent_window = parent_window
