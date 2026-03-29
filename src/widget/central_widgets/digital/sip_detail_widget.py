from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6 import QtWidgets, QtGui, QtCore

from src.utils.constants import BusinessRules, UI_TEXT_ELEMENTS
from src.utils.data_objects.series import SeriesStatus
from src.utils.data_objects.digital.sip import SIP

from src.widget.base_widget import BaseWidget, ComponentWidget, ApplicationMixin
from src.widget.central_widgets.central_widget import CentralWidget
from src.widget.components.digital.mapping_widget import TagMappingWidget

from src.window.base_window import Window

if TYPE_CHECKING:
    from src.window.digital.sip_detail_window import SipDetailWindow


UI_TEXT = UI_TEXT_ELEMENTS["digital"]["sip_detail_view"]


class SipDetailWidget(CentralWidget):
    def __init__(self, parent_window: Window, sip: SIP):
        super().__init__(parent_window)

        self.parent_window: SipDetailWindow
        self.sip = sip

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.vertical_layout)


        self.sip_name_edit = SipNameEditAndStatusWidget(parent_window=self.parent_window, sip=self.sip)
        self.series_type_selector = SeriesTypeSelectorWidget(parent_window=self.parent_window, sip=self.sip)
        self.series_retrieval = SeriesRetrievalWidget(sip=self.sip)
        self.metadata_file_selector = MetadataFileSelectorWidget(parent_window=self.parent_window)
        self.folder_structure_button = FolderStructureButton()
        self.folder_structure_button.setEnabled(False)

        self.tag_mapping_widget = TagMappingWidget()
        self.tag_mapping_widget.setMinimumSize(100, 400)

        self.open_grid_button = OpenGridButton()
        self.open_grid_button.setEnabled(False)


        self.vertical_layout.addWidget(self.sip_name_edit)
        self.vertical_layout.addWidget(self.series_type_selector)
        self.vertical_layout.addWidget(self.series_retrieval)
        self.vertical_layout.addWidget(self.metadata_file_selector)
        self.vertical_layout.addWidget(self.folder_structure_button)
        self.vertical_layout.addWidget(self.tag_mapping_widget)
        self.vertical_layout.addWidget(self.open_grid_button)

    def setup_signals(self) -> None:
        self.open_grid_button.clicked.connect(self.open_grid_handler)
        self.folder_structure_button.clicked.connect(self.open_folder_structure_handler)
        self.series_type_selector.selection_changed_signal.connect(self.series_retrieval.series_dropdown.set_series_type)
        self.series_retrieval.import_template_retrieval_requested_signal.connect(self.import_template_retrieval_requested_handler)
        self.series_retrieval.import_template_retrieved_signal.connect(self.import_template_downloaded_handler)

        self.metadata_file_selector.metadata_path_selected_signal.connect(self.metadata_file_selected_handler)

    # Handlers
    def _update_tag_mapping(self) -> None:
        self.sip.tag_mapping = self.tag_mapping_widget.get_mapping()

    def open_folder_structure_handler(self) -> None:
        self._update_tag_mapping()
        self.application.window_controller.open_folder_mapping_window(sip=self.sip)

    def open_grid_handler(self) -> None:
        if not self.sip.name.strip():
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip_name"]["empty_name_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip_name"]["empty_name_error"]["text"],
            )
            return

        from src.utils.pyside_helper import Helper

        if not Helper().is_sip_name_available(self.sip.name, sip_type=type(self.sip), exclude_sip=self.sip):
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["duplicate_name_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["duplicate_name_error"]["text"].format(name=self.sip.name),
            )
            return

        self._update_tag_mapping()

        self.application.window_controller.open_digital_grid_signal.emit(self.sip)

        self.parent_window.close()

    def import_template_retrieval_requested_handler(self) -> None:
        self.parent_window.start_retrieve_import_template_task()
        self.parent_window.worker.result_ready_signal.connect(
            self.series_retrieval.import_template_downloaded_handler
        )

    def import_template_downloaded_handler(self) -> None:
        from src.controller.excel_controller import ExcelReadError

        try:
            import_df = self.sip.read_import_template()
        except ExcelReadError:
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["excel"]["read_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["excel"]["read_error"]["text"].format(path=self.sip.import_template_path),
            )
            return

        if import_df is None:
            return

        self.open_grid_button.setEnabled(True)
        self.tag_mapping_widget.add_to_import_template(import_df.columns)

    def metadata_file_selected_handler(self, path: str) -> None:
        from src.controller.excel_controller import ExcelReadError

        self.sip.metadata_path = path

        try:
            metadata_df = self.sip.read_metadata()
        except ExcelReadError:
            self.application.notify_user_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["excel"]["read_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["excel"]["read_error"]["text"].format(path=path),
            )
            return

        if metadata_df is None:
            return

        columns_without_empty_fields = [
            c
            for c, all_empty in dict(
                metadata_df.eq("").all()
            ).items()
            if not all_empty
        ]

        self.tag_mapping_widget.add_to_metadata(columns_without_empty_fields)
        self.folder_structure_button.setEnabled(True)


# Components
class SipNameEditAndStatusWidget(ComponentWidget):
    def __init__(self, parent_window: Window, sip: SIP):
        super().__init__(parent_window)

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
        self.sip.name_changed_signal.connect(
            lambda: self.title_edit.setText(self.sip.name)
        )

class SeriesTypeSelectorWidget(ComponentWidget):
    selection_changed_signal = QtCore.Signal(SeriesStatus)

    SELECTED_TYPE = SeriesStatus.PUBLISHED

    def __init__(self, parent_window: Window, sip: SIP):
        super().__init__(parent_window)

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
        return f"{len(self.application.sneaky_series()[self.sip.environment.name]):d} serie(s)"

    # Handlers
    def series_updated_handler(self) -> None:
        self.series_amount_label.setText(self._get_series_text())

    def radio_buttons_toggled_handler(self, checked: bool) -> None:
        self.SELECTED_TYPE = SeriesStatus.PUBLISHED if checked else SeriesStatus.SUBMITTED

        self.selection_changed_signal.emit(self.SELECTED_TYPE)

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
        self.set_series()
        
    def setup_signals(self) -> None:
        self.application.series_updated_signal.connect(self.series_updated_handler)
        self.editTextChanged.connect(lambda: self.sip.set_series(self.currentData()))

    def set_series_type(self, series_type: SeriesStatus) -> None:
        self.series_type = series_type
        self.clear_series()
        self.set_series()

    # Helper
    def clear_series(self) -> None:
        for i in reversed(range(self.count())):
            self.removeItem(i)

    def set_series(self) -> None:
        series = [
            s for s in self.application.sneaky_series()[self.sip.environment.name]
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
    import_template_retrieval_requested_signal = QtCore.Signal()
    import_template_retrieved_signal = QtCore.Signal()

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
        self.import_template_retrieval_button.clicked.connect(
            self.import_template_retrieval_requested_signal.emit
        )

    def import_template_downloaded_handler(self, path: str) -> None:
        self.sip.set_import_template_path(path)
        self.import_template_retrieved_signal.emit()


class MetadataFileSelectorWidget(ComponentWidget):
    metadata_path_selected_signal = QtCore.Signal(str)

    SELECTOR_TYPE = "Metadata Files (*.xlsx)"

    def __init__(self, parent_window: Window):
        super().__init__(parent_window)

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
        self.metadata_path_selected_signal.emit(metadata_path)

class FolderStructureButton(QtWidgets.QPushButton):
    def __init__(self):
        super().__init__()

        self.setText(UI_TEXT["folder_structure_button_text"])

class OpenGridButton(QtWidgets.QPushButton, ApplicationMixin):
    def __init__(self):
        super().__init__()
        self.setText(UI_TEXT["open_grid_button_text"])
