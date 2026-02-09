from PySide6 import QtWidgets, QtGui, QtCore


from src.utils.constants import BusinessRules, UI_TEXT_ELEMENTS
from src.utils.data_objects.series import SeriesStatus
from src.utils.data_objects.sip import SIP

from src.widget.base_widget import BaseWidget, ApplicationMixin
from src.widget.components.mapping_widget import TagMappingWidget, FolderMappingWidget

UI_TEXT = UI_TEXT_ELEMENTS["digital"]["sip_detail_view"]


class SipDetailWidget(BaseWidget):
    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()

    def setup_ui(self) -> None:
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.vertical_layout)


        self.sip_name_edit = SipNameEditAndStatusWidget(sip=self.sip)
        self.series_type_selector = SeriesTypeSelectorWidget(sip=self.sip)
        self.series_retrieval = SeriesRetrievalWidget(sip=self.sip)
        self.metadata_file_selector = MetadataFileSelectorWidget()
        self.folder_structure_button = FolderStructureButton(sip=self.sip)

        self.tag_mapping = TagMappingWidget()
        self.tag_mapping.setMinimumSize(100, 400)

        self.open_grid_button = OpenGridButton()
        self.open_grid_button.setEnabled(False)


        self.vertical_layout.addWidget(self.sip_name_edit)
        self.vertical_layout.addWidget(self.series_type_selector)
        self.vertical_layout.addWidget(self.series_retrieval)
        self.vertical_layout.addWidget(self.metadata_file_selector)
        self.vertical_layout.addWidget(self.folder_structure_button)
        self.vertical_layout.addWidget(self.tag_mapping)
        self.vertical_layout.addWidget(self.open_grid_button)


# Components
class SipNameEditAndStatusWidget(BaseWidget):
    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.horizontal_layout)

        title_font = QtGui.QFont()
        title_font.setBold(True)
        title_font.setPointSize(20)
        self.title_edit = QtWidgets.QLineEdit(text=self.sip.name)
        self.title_edit.setFont(title_font)
        self.title_edit.setMaxLength(BusinessRules.SIP_TITLE_MAX_LENGTH)
        
        self.status_label = QtWidgets.QLabel(text=self.sip.status.status_label)
        self.status_label.setStyleSheet(self.sip.status.value)

        self.horizontal_layout.addWidget(self.title_edit, stretch=5)
        self.horizontal_layout.addWidget(self.status_label)

    def setup_signals(self) -> None:
        self.title_edit.editingFinished.connect(
            lambda: self.sip.set_name(self.title_edit.text())
        )

class SeriesTypeSelectorWidget(BaseWidget):
    selection_changed_signal = QtCore.Signal()

    SELECTED_TYPE = SeriesStatus.PUBLISHED

    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.horizontal_layout)


        self.series_amount_label = QtWidgets.QLabel(text=self._get_series_text())

        self.published_radiobutton = QtWidgets.QRadioButton(text=UI_TEXT["published_series_text"])
        self.published_radiobutton.setChecked(True)

        self.submitted_radiobutton = QtWidgets.QRadioButton(text=UI_TEXT["submitted_series_text"])
        

        self.horizontal_layout.addWidget(self.series_amount_label)
        self.horizontal_layout.addWidget(self.published_radiobutton)
        self.horizontal_layout.addWidget(self.submitted_radiobutton)
        
    def setup_signals(self) -> None:
        self.application.series_updated_signal.connect(self.series_updated_handler)

        # NOTE: since they are linked, we only need to capture one of them
        self.published_radiobutton.toggled.connect(self.radio_buttons_toggled_handler)

    # Helpers
    def _get_series_text(self) -> str:
        return f"{len(self.application.series[self.sip.environment.name]):d} serie(s)"

    # Handlers
    def series_updated_handler(self) -> None:
        self.series_amount_label.setText(self._get_series_text())

    def radio_buttons_toggled_handler(self, checked: bool) -> None:
        self.SELECTED_TYPE = SeriesStatus.PUBLISHED if checked else SeriesStatus.SUBMITTED

        self.selection_changed_signal.emit()

class SeriesDropdownWidget(QtWidgets.QComboBox, ApplicationMixin):
    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip

        self.setEditable(True)
        self.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.completer().setCompletionMode(
            QtWidgets.QCompleter.PopupCompletion
        )
        self.completer().setFilterMode(
            QtCore.Qt.MatchFlag.MatchContains
        )
        self.setMaximumWidth(900)

        self.series_type: SeriesStatus = SeriesStatus.PUBLISHED

        self.setup_signals()
        
    def setup_signals(self) -> None:
        self.application.series_updated_signal.connect(self.series_updated_handler)

    # Helper
    def clear_series(self) -> None:
        for i in reversed(range(self.count())):
            self.removeItem(i)

    def set_series(self) -> None:
        series = [
            s for s in self.application.series[self.sip.environment.name]
            if s.status == self.series_type
        ]

        for serie in series:
            self.addItem(
                serie.get_full_name(),
                userData=serie
            )

    # Handler
    def series_updated_handler(self) -> None:
        self.clear_series()
        self.set_series()

class SeriesRetrievalWidget(BaseWidget):
    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.horizontal_layout)


        self.series_dropdown = SeriesDropdownWidget(sip=self.sip)

        self.import_template_retrieval_button = QtWidgets.QPushButton(text=UI_TEXT["import_template_retrieval_button_text"])


        self.horizontal_layout.addWidget(self.series_dropdown, stretch=5)
        self.horizontal_layout.addWidget(self.import_template_retrieval_button)
        
    def setup_signals(self) -> None:
        self.import_template_retrieval_button.clicked.connect(self.import_template_retrieval_clicked_handler)

    def import_template_retrieval_clicked_handler(self) -> None:
        selected_series = self.series_dropdown.currentData()

        # TODO: this requires some background work
        ...

class MetadataFileSelectorWidget(BaseWidget):
    # TODO: use to then get metadatadf and stuff (creator.windows.sip_view 150)
    metadata_path_selected = QtCore.Signal(str)

    SELECTOR_TYPE = "Metadata Files (*.xlsx)"

    def __init__(self):
        super().__init__()

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.horizontal_layout = QtWidgets.QHBoxLayout()
        self.setLayout(self.horizontal_layout)


        self.metadata_file_button = QtWidgets.QPushButton(text=UI_TEXT["metadata_file_button_text"])

        self.metadata_path_scrollarea = QtWidgets.QScrollArea()
        self.metadata_path_label = QtWidgets.QLabel(text=UI_TEXT["metadata_file_path_default_text"])
        self.metadata_path_scrollarea.setWidget(self.metadata_path_label)
        self.metadata_path_scrollarea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)


        self.horizontal_layout.addWidget(self.metadata_file_button, stretch=5)
        self.horizontal_layout.addWidget(self.metadata_path_scrollarea)
        
    def setup_signals(self) -> None:
        self.metadata_file_button.clicked.connect(self.metadata_file_button_clicked_handler)

    def metadata_file_button_clicked_handler(self) -> None:
        metadata_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            caption=UI_TEXT["metadata_selection_dialog_window"]["title"], filter=self.SELECTOR_TYPE
        )

        if metadata_path == "":
            return

        self.metadata_path_label.setText(metadata_path)
        self.metadata_path_selected.emit(metadata_path)

# TODO: below
class FolderStructureButton(QtWidgets.QPushButton, ApplicationMixin):
    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip

        self.setText(UI_TEXT["folder_structure_button_text"])

        self.setup_signals()
        
    def setup_signals(self) -> None:
        ...

class OpenGridButton(QtWidgets.QPushButton, ApplicationMixin):
    def __init__(self):
        super().__init__()

        self.setText(UI_TEXT["open_grid_button_text"])

        self.clicked.connect(self.open_grid_clicked_handler)

    def open_grid_clicked_handler(self) -> None:
        ...
