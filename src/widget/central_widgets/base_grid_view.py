from PySide6 import QtCore, QtWidgets

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.grid.table.common.grid_table_view import GridTableView
from src.utils.grid.table.common.proxy_model import SortFilterProxyModel, TableFilter
from src.utils.pyside_helper import clear_widget_warning_style, set_widget_warning_style

from src.widget.base_widget import BaseWidget

COMMON_GRID_TEXT = UI_TEXT_ELEMENTS["grid_checks"]["common"]


class BaseGridView(BaseWidget):
    NON_DUPLICATABLE_COLUMNS: set[str] = set()

    def __init__(self, sip) -> None:
        super().__init__()

        self.sip = sip
        self.has_unsaved_changes = False
        self._active_workers: list = []

    def _create_common_widgets(self, ui_text: dict) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        self.series_label = QtWidgets.QLabel()
        self.default_sorting_button = QtWidgets.QPushButton(text=ui_text["default_sorting_button_text"])
        self.show_bad_rows_checkbox = QtWidgets.QCheckBox(text=ui_text["bad_rows_checkbox_text"])

        self.column_dropdown = QtWidgets.QComboBox()
        self.column_dropdown.setEditable(True)
        self.column_dropdown.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.add_column_button = QtWidgets.QPushButton(text=ui_text["add_column_button_text"])

        self.save_button = QtWidgets.QPushButton(text=ui_text["save_button_text"])
        self.create_sip_button = QtWidgets.QPushButton(text=ui_text["create_sip_button_text"])

    def _create_table(self, table_model) -> None:
        self.table_model = table_model
        self.proxy_model = SortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self.table_view = GridTableView()
        self.table_view.setModel(self.proxy_model)

        self._populate_column_dropdown()
        self.column_dropdown.completer().setFilterMode(QtCore.Qt.MatchFlag.MatchContains)

    def _connect_common_signals(self) -> None:
        self.default_sorting_button.clicked.connect(self.proxy_model.reset_sorting)
        self.show_bad_rows_checkbox.stateChanged.connect(self._bad_rows_clicked)
        self.add_column_button.clicked.connect(self._add_column_button_clicked)
        self.save_button.clicked.connect(self._save_button_clicked)
        self.create_sip_button.clicked.connect(self._create_sip_clicked)
        self.table_model.dataChanged.connect(self._data_changed)
        self.table_model.data_edited_signal.connect(self._on_data_edited)
        self.table_model.validation_started_signal.connect(self._update_create_sip_button)
        self.table_model.validation_finished_signal.connect(self._update_create_sip_button)

    def _populate_column_dropdown(self) -> None:
        seen = set()

        for col in self.table_model.raw_data.columns:
            base_col = col.rstrip()
            if base_col not in self.NON_DUPLICATABLE_COLUMNS and base_col not in seen:
                self.column_dropdown.addItem(base_col)
                seen.add(base_col)

    def _update_series_label(self) -> None:
        if self.sip.series:
            self.series_label.setText(self.sip.series.get_full_name())
            clear_widget_warning_style(self.series_label)
        else:
            fallback = self.sip.saved_series_name or self.sip.name
            self.series_label.setText(fallback)
            set_widget_warning_style(self.series_label, COMMON_GRID_TEXT["series_not_found_tooltip"])

        self._update_create_sip_button()

    def _update_create_sip_button(self) -> None:
        raise NotImplementedError

    def _data_changed(self) -> None:
        self.has_unsaved_changes = True
        self._update_create_sip_button()

    def _on_data_edited(self) -> None:
        if self.sip.status != SIPStatus.IN_PROGRESS:
            self.sip.set_status(SIPStatus.IN_PROGRESS)

    def _bad_rows_clicked(self, state: int) -> None:
        self.proxy_model.toggle_filter(TableFilter.BAD_ROWS)

    def _add_column_button_clicked(self) -> None:
        column = self.column_dropdown.currentText()

        if not column:
            return

        df = self.table_model.raw_data

        self.table_model.beginResetModel()

        new_column_name = column
        while (new_column_name := f"{new_column_name} ") in df.columns:
            pass

        col_loc = df.columns.get_loc(column)
        spaces = len(new_column_name) - len(column)
        insert_pos = col_loc + spaces
        df.insert(insert_pos, new_column_name, "")

        self.table_model.shift_markings_for_insert(insert_pos)

        from src.utils.grid.checks.digital.empty_row_check import mark_empty_rows

        mark_empty_rows(self.table_model)
        self.table_model.endResetModel()

    def _save_button_clicked(self, silent: bool = False) -> None:
        raise NotImplementedError

    def _create_sip_clicked(self) -> None:
        raise NotImplementedError

    def _on_sip_created(self, success: bool) -> None:
        raise NotImplementedError

    def _on_create_sip_finished(self) -> None:
        self.save_button.setEnabled(True)
        self._update_create_sip_button()
