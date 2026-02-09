import numpy as np
import os
from PySide6 import QtWidgets, QtGui, QtCore

from src.controller.api_controller import APIController

from src.utils.constants import BusinessRules, UI_TEXT_ELEMENTS
from src.utils.data_objects.series import SeriesStatus
from src.utils.data_objects.sip import SIP

from src.widget.base_widget import BaseWidget, ApplicationMixin
from src.widget.central_widgets.folder_structure import FolderStructure
from src.widget.components.mapping_widget import TagMappingWidget, FolderMappingWidget

from src.window.base_window import Window

UI_TEXT = UI_TEXT_ELEMENTS["digital"]["sip_detail_view"]


class SipDetailWidget(BaseWidget):
    open_grid_signal = QtCore.Signal()

    def __init__(self, parent_window: Window, sip: SIP):
        super().__init__(parent_window)

        self.parent_window = parent_window
        self.sip = sip

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.vertical_layout)


        self.sip_name_edit = SipNameEditAndStatusWidget(sip=self.sip)
        self.series_type_selector = SeriesTypeSelectorWidget(sip=self.sip)
        self.series_retrieval = SeriesRetrievalWidget(parent_window=self.parent_window, sip=self.sip)
        self.metadata_file_selector = MetadataFileSelectorWidget()
        self.folder_structure_button = FolderStructureButton(sip=self.sip)
        self.folder_structure_button.setEnabled(False)

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


    def setup_signals(self) -> None:
        self.open_grid_button.clicked.connect(self.open_grid_handler)
        self.series_type_selector.selection_changed_signal.connect(self.series_retrieval.series_dropdown.set_series_type)
        self.series_retrieval.import_template_retrieved_signal.connect(self.import_template_downloaded_handler)

        self.metadata_file_selector.metadata_path_selected_signal.connect(self.metadata_file_selected_handler)

    # Handlers
    def open_grid_handler(self) -> None:
        """
            We don't actually open the grid here, but we do prep the values in the sip
        """
        self.sip.tag_mapping = self.tag_mapping.get_mapping()

        self.open_grid_signal.emit()

    def import_template_downloaded_handler(self) -> None:
        self.open_grid_button.setEnabled(True)

        # NOTE: this will always have a value here, since we only just downloaded it
        import_df = self.sip.read_import_template()
        self.tag_mapping.add_to_import_template(import_df.columns)

    def metadata_file_selected_handler(self, path: str) -> None:
        self.sip.metadata_path = path

        metadata_df = self.sip.read_metadata()

        columns_without_empty_fields = [
            c
            for c, all_empty in dict(
                metadata_df.eq("").all()
            ).items()
            if not all_empty
        ]

        self.tag_mapping.add_to_metadata(columns_without_empty_fields)
        self.folder_structure_button.setEnabled(True)


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
    selection_changed_signal = QtCore.Signal(SeriesStatus)

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
    import_template_retrieved_signal = QtCore.Signal()

    def __init__(self, parent_window: Window, sip: SIP):
        super().__init__()

        self.sip = sip
        self.parent_window = parent_window 

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
        self.application.work_in_progress_signal.emit(self.parent_window, UI_TEXT["import_template_retrieval_toolbar_text"])
        self.parent_window.worker = self.application.worker_controller.run_thread(
            thread_function=lambda: APIController.get_import_template(
                configuration=self.application.configuration,
                environment=self.sip.environment,
                series_id=self.sip.series._id
            ),
            thread_is_generator=False
        )
        self.parent_window.worker.about_to_finish_signal.connect(lambda: self.application.work_ended_signal.emit(self.parent_window))

        self.parent_window.worker.result_ready_signal.connect(self.import_template_downloaded_handler)

    def import_template_downloaded_handler(self, path: str) -> None:
        self.sip.set_import_template_path(path)

        self.import_template_retrieved_signal.emit()


class MetadataFileSelectorWidget(BaseWidget):
    metadata_path_selected_signal = QtCore.Signal(str)

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
        self.metadata_path_selected_signal.emit(metadata_path)

class FolderStructureButton(QtWidgets.QPushButton, ApplicationMixin):
    def __init__(self, sip: SIP):
        super().__init__()

        self.sip = sip
        self.mapping_widget: FolderMappingWidget = None

        self.setText(UI_TEXT["folder_structure_button_text"])

        self.setup_signals()
        
    def setup_signals(self) -> None:
        self.clicked.connect(self.open_folder_mapping_handler)

    def open_folder_mapping_handler(self) -> None:
        # NOTE: just to make sure we don't have dangling connections
        if self.mapping_widget is not None:
            self.mapping_widget.save_button.clicked.disconnect()

        self.folder_structure_widget = FolderStructure()
        self.mapping_widget = self.folder_structure_widget.mapping

        path_in_sip_map_column = [
            k for k, v in self.sip.tag_mapping.items()
            if v == "Path in SIP"
        ][0]
        # Only allow columns where not all fields are empty
        columns_without_empty_fields = [
            c
            for c, all_empty in dict(
                self.sip.read_metadata().eq("").all()
            ).items()
            if not all_empty and c != path_in_sip_map_column
        ]

        self.folder_structure_widget.add_to_metadata(columns_without_empty_fields)

        self.mapping_window = Window(UI_TEXT_ELEMENTS["window_titles"]["folder_structure"])
        self.mapping_window.setCentralWidget(self.folder_structure_widget)

        self.mapping_widget.save_button.clicked.connect(lambda: self.mapping_closed_handler(path_in_sip_map_column=path_in_sip_map_column))
        self.mapping_window.show()

    def mapping_closed_handler(self, path_in_sip_map_column: str) -> None:
        df = self.sip.read_metadata()
        folder_structure = self.folder_structure_widget.mapping.get_mapping()

        # NOTE: only check for files (anything with an extension)
        df_sub = df[df[path_in_sip_map_column].str.contains(r"\.[a-zA-Z0-9]+$", regex=True, na=False)][[*folder_structure]].apply(lambda x: x.str.strip())

        if np.any(df_sub.isna()) or np.any(df_sub == ""):
            self.application.thread_error_signal.emit(
                UI_TEXT_ELEMENTS["errors"]["sip"]["folder_mapping_error"]["title"],
                UI_TEXT_ELEMENTS["errors"]["sip"]["folder_mapping_error"]["text"]
            )
            return

        # Kamerplanten/groot/monstera.docx
        # jaar -> dor of niet dor
        # Kamerplanten/groot/**2022/dor**/monstera.docx

        df["__folder"] = df[path_in_sip_map_column].apply(lambda x: x.rsplit("/", 1)[0])
        df["__file"] = df[path_in_sip_map_column].apply(lambda x: "" if len(x.rsplit("/", 1)) == 1 else x.rsplit("/", 1)[1])

        folder_mapping = {
            path_in_sip: mapped_name
            for path_in_sip, mapped_name in zip(
                df[path_in_sip_map_column],
                df[["__folder", *folder_structure, "__file"]].fillna("").astype(str).convert_dtypes().agg("/".join, axis=1),
            )
            # NOTE: only do aggregate mapping if it's a stuk (with an extension)
            if os.path.splitext(path_in_sip)[1] != ""
        }

        self.sip.folder_mapping = folder_mapping


class OpenGridButton(QtWidgets.QPushButton, ApplicationMixin):
    def __init__(self):
        super().__init__()
        self.setText(UI_TEXT["open_grid_button_text"])
