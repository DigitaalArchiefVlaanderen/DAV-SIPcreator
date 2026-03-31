from PySide6 import QtCore, QtGui, QtWidgets

from src.utils.base_object import ApplicationMixin
from src.utils.constants import UI_TEXT_ELEMENTS, BusinessRules
from src.utils.data_objects.series import SeriesStatus

UI_TEXT = UI_TEXT_ELEMENTS["analog"]["grid_creation"]


class AnalogGridCreationDialog(QtWidgets.QWidget, ApplicationMixin):
    sip_creation_requested_signal = QtCore.Signal(str, str)

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(UI_TEXT["window_title"])
        self.resize(800, 400)
        self.setWindowIcon(self.application.windowIcon())

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        font = QtGui.QFont()
        font.setBold(True)
        font.setUnderline(True)
        font.setPointSize(20)

        self.title_input = QtWidgets.QLineEdit(text=self._get_next_name())
        self.title_input.setFont(font)
        self.title_input.setMaxLength(BusinessRules.SIP_TITLE_MAX_LENGTH)

        self.series_combobox = QtWidgets.QComboBox()
        self.series_combobox.setEditable(True)
        self.series_combobox.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.series_combobox.completer().setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
        self.series_combobox.completer().setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        self.series_combobox.setMaximumWidth(900)
        self._populate_series()

        self.open_grid_button = QtWidgets.QPushButton(text=UI_TEXT["open_grid_button_text"])

        layout.addWidget(self.title_input, 0, 0)
        layout.addWidget(self.series_combobox, 1, 0)
        layout.addItem(
            QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Policy.Minimum, QtWidgets.QSizePolicy.Policy.Expanding),
            2,
            0,
        )
        layout.addWidget(self.open_grid_button, 3, 0)
        layout.setSpacing(20)

    def setup_signals(self) -> None:
        self.open_grid_button.clicked.connect(self._on_open_grid_clicked)

    def _populate_series(self) -> None:
        self.series_combobox.clear()

        env_name = self.application.configuration.active_environment_name

        for series in self.application.sneaky_series().get(env_name, []):
            if series.status != SeriesStatus.PUBLISHED:
                continue

            self.series_combobox.addItem(series.get_full_name(), userData=series._id)

    def _get_next_name(self) -> str:
        from src.utils.data_objects.analog.sip import AnalogSIP
        from src.utils.pyside_helper import Helper

        return Helper().get_next_sip_name(sip_type=AnalogSIP)

    def _on_open_grid_clicked(self) -> None:
        sip_name = self.title_input.text().strip()

        if not sip_name:
            return

        series_id = self.series_combobox.currentData()

        if series_id is None:
            return

        self.open_grid_button.setEnabled(False)

        self.sip_creation_requested_signal.emit(sip_name, series_id)
