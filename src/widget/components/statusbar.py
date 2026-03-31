"""
Statusbar to display some status messages to the user
"""

from PySide6 import QtCore, QtWidgets


class Statusbar(QtWidgets.QStatusBar):
    def __init__(self, parent: QtWidgets.QMainWindow):
        super().__init__(parent)
        self.parent_window = parent

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setLineWidth(2)
        separator.setMidLineWidth(1)

        self.label_right = QtWidgets.QLabel()
        self.label_right.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        self.label_right.setWordWrap(False)
        self.label_right.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        self.update_label_right_width()
        self.parent_window.resizeEvent = self.on_parent_resize

        self.addPermanentWidget(separator)
        self.addPermanentWidget(self.label_right)

        self.installEventFilter(self)

    # Hack into the event filter to set the tooltip, this way we do not care what type of elements we're dealing with
    def eventFilter(self, obj, event):
        if obj == self and event.type() == QtCore.QEvent.ToolTip:
            tooltip = self.left_text

            # Only set right text if we're actually over it
            if self.label_right.geometry().contains(event.pos()):
                tooltip = self.right_text

            QtWidgets.QToolTip.showText(event.globalPos(), tooltip)

            return True

        return super().eventFilter(obj, event)

    def update_label_right_width(self) -> None:
        max_width = self.parent_window.width() // 2
        self.label_right.setMaximumWidth(max_width)

    def on_parent_resize(self, event) -> None:
        self.update_label_right_width()

        # Call original
        QtWidgets.QMainWindow.resizeEvent(self.parent_window, event)

    @property
    def left_text(self) -> str:
        return self.currentMessage()

    # NOTE: this exists to serve as an easier way to handle signals that need to set a message
    def set_left_text(self, text: str) -> None:
        self.showMessage(text, timeout=0)

    @property
    def right_text(self) -> str:
        return self.label_right.text()

    def set_right_text(self, text: str) -> None:
        self.label_right.setText(text)
