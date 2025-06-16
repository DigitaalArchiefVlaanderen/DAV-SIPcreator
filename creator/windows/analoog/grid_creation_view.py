import os

from PySide6 import QtWidgets, QtCore, QtGui

from creator.application import Application

from creator.utils.path_loader import resource_path
from creator.utils.state import State
from creator.utils.series import Series


class GridCreationView(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self.state.check_series_loaded()
        self.setWindowTitle("SIP Analoog")
        self.resize(800, 600)

        self.setup_ui()

    def setup_ui(self) -> None:
        def _set_combobox_items(combobox: QtWidgets.QComboBox) -> None:
            combobox.clear()
            
            for series in self.state.series:
                if series.status != "Published":
                    continue

                combobox.addItem(series.get_name(), userData=series._id)

        def _get_next_name() -> str:
            """
                Gets a name in the form of "SIP <n>"
                Checks the storage location to make sure we don't have collisions in name
            """
            os.makedirs(self.state.configuration.analoog_location, exist_ok=True)

            next_n = 1

            names = os.listdir(self.state.configuration.analoog_location)
            
            while (name := f"SIP {next_n}.db") in names:
                next_n += 1

            return name[:-3]

        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        
        self.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))

        font = QtGui.QFont()
        font.setBold(True)
        font.setUnderline(True)
        font.setPointSize(20)

        self.title = QtWidgets.QLineEdit(text=_get_next_name())
        self.title.setFont(font)
        self.title.setMaxLength(185)
        
        self.series_combobox = QtWidgets.QComboBox()
        self.series_combobox.setEditable(True)
        self.series_combobox.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.series_combobox.completer().setCompletionMode(
            QtWidgets.QCompleter.PopupCompletion
        )
        self.series_combobox.completer().setFilterMode(
            QtCore.Qt.MatchFlag.MatchContains
        )
        self.series_combobox.setMaximumWidth(900)
        _set_combobox_items(self.series_combobox)

        self.open_grid_button = QtWidgets.QPushButton(text="Open metadata grid")

        layout.addWidget(self.title, 0, 0)
        layout.addWidget(self.series_combobox, 1, 0)
        layout.addItem(QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding), 2, 0)
        layout.addWidget(self.open_grid_button, 3, 0)

        layout.setSpacing(20)

    @property
    def open_grid_clicked(self) -> QtCore.SignalInstance:
        return self.open_grid_button.clicked

    @property
    def selected_series(self) -> Series:
        selected_series_id: str = self.series_combobox.currentData()

        for s in self.state.series:
            if s._id == selected_series_id:
                return s

    @property
    def entered_sip_name(self) -> str:
        return self.title.text()
