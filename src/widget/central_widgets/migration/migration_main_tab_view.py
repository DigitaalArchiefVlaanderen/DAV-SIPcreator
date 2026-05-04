from PySide6 import QtCore, QtWidgets

from src.utils.constants import KLANT_ROLE, MIGRATION_ID_COLUMN, SERIES_NAME_COLUMN, UI_TEXT_ELEMENTS, DBColumnName
from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.grid.table.common.data_table import DataTable, MarkingSource
from src.utils.grid.table.common.grid_table_view import GridTableView
from src.utils.grid.table.common.proxy_model import SortFilterProxyModel, TableFilter

from src.widget.base_widget import BaseWidget

UI_TEXT = UI_TEXT_ELEMENTS["migration"]["main_tab"]
GRID_UI_TEXT = UI_TEXT_ELEMENTS["migration"]["grid"]

URI_SERIEREGISTER_COLUMN = DBColumnName.URI_SERIEREGISTER


class MigrationMainTabView(BaseWidget):
    assign_to_series_signal = QtCore.Signal(list, str, str)
    create_sip_signal = QtCore.Signal()
    delete_rows_signal = QtCore.Signal(list)

    def __init__(self, sip: MigrationSIP) -> None:
        super().__init__()

        self.sip = sip

        self.setup_ui()
        self.setup_signals()
        self._populate_series_dropdown()
        self._validate_series()
        self._update_role_visibility()

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        self.table_model = DataTable(sip=self.sip, editable=False)

        self.proxy_model = SortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)

        self.table_view = GridTableView()
        self.table_view.setModel(self.proxy_model)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectItems)

        self.series_dropdown = QtWidgets.QComboBox()
        self.series_dropdown.setEditable(True)
        self.series_dropdown.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.series_dropdown.setMinimumWidth(300)

        self.assign_button = QtWidgets.QPushButton(text=UI_TEXT["assign_button_text"])

        self.unassigned_only_checkbox = QtWidgets.QCheckBox(text=UI_TEXT["unassigned_only_checkbox_text"])

        self.delete_rows_button = QtWidgets.QPushButton(text=UI_TEXT["delete_rows_button_text"])

        self.default_sorting_button = QtWidgets.QPushButton(text=GRID_UI_TEXT["default_sorting_button_text"])

        self.save_button = QtWidgets.QPushButton(text=UI_TEXT["save_button_text"])
        self.create_sip_button = QtWidgets.QPushButton(text=UI_TEXT["create_sip_button_text"])

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.save_button, 1)
        button_layout.addWidget(self.create_sip_button, 1)

        self.grid_layout.addWidget(self.unassigned_only_checkbox, 0, 0)
        self.grid_layout.addWidget(self.series_dropdown, 0, 1)
        self.grid_layout.addWidget(self.assign_button, 0, 2)
        self.grid_layout.addWidget(self.delete_rows_button, 1, 0)
        self.grid_layout.addWidget(self.default_sorting_button, 1, 2)
        self.grid_layout.addWidget(self.table_view, 2, 0, 1, 3)
        self.grid_layout.addLayout(button_layout, 3, 0, 1, 3)

        self._hide_id_column()

    def _hide_id_column(self) -> None:
        columns = list(self.table_model.raw_data.columns)
        if MIGRATION_ID_COLUMN in columns:
            self.table_view.hideColumn(columns.index(MIGRATION_ID_COLUMN))

    def setup_signals(self) -> None:
        self.assign_button.clicked.connect(self._assign_button_clicked)
        self.delete_rows_button.clicked.connect(self._delete_rows_clicked)
        self.default_sorting_button.clicked.connect(self.proxy_model.reset_sorting)
        self.unassigned_only_checkbox.stateChanged.connect(self._unassigned_only_clicked)
        self.save_button.clicked.connect(self._save_button_clicked)
        self.create_sip_button.clicked.connect(self._create_sip_clicked)
        self.application.series_updated_signal.connect(self._on_series_updated)
        self.application.application_role_changed_signal.connect(self._update_role_visibility)

    def _on_series_updated(self) -> None:
        self._populate_series_dropdown()
        self._validate_series()

    def _populate_series_dropdown(self) -> None:
        self.series_dropdown.clear()

        env_name = self.application.configuration.active_environment_name
        series_list = self.application.sneaky_series().get(env_name, [])

        for series in series_list:
            self.series_dropdown.addItem(series.get_full_name(), userData=series)

        if self.series_dropdown.completer():
            self.series_dropdown.completer().setFilterMode(QtCore.Qt.MatchFlag.MatchContains)

    def _validate_series(self) -> None:
        df = self.table_model.raw_data

        if URI_SERIEREGISTER_COLUMN not in df.columns or SERIES_NAME_COLUMN not in df.columns:
            self._update_create_sip_button()

            return

        env_name = self.application.configuration.active_environment_name
        series_list = self.application.sneaky_series().get(env_name, [])
        base_uri = self.sip.environment.get_serie_register_uri()
        known_uris = {f"{base_uri}/{s._id}" for s in series_list}

        uri_col = df.columns.get_loc(URI_SERIEREGISTER_COLUMN)
        name_col = df.columns.get_loc(SERIES_NAME_COLUMN)

        for row in range(df.shape[0]):
            uri = str(df.iat[row, uri_col])
            series_name = str(df.iat[row, name_col])
            uri_index = self.table_model.index(row, uri_col)
            name_index = self.table_model.index(row, name_col)

            self.table_model.unmark_cell(uri_index, MarkingSource.CELL)
            self.table_model.unmark_cell(name_index, MarkingSource.CELL)

            if uri == "" or uri == "nan":
                self.table_model.mark_cell(
                    uri_index,
                    source=MarkingSource.CELL,
                    tooltip=UI_TEXT["series_not_linked_tooltip"],
                )
                self.table_model.mark_cell(
                    name_index,
                    source=MarkingSource.CELL,
                    tooltip=UI_TEXT["series_not_linked_tooltip"],
                )
            elif uri not in known_uris:
                self.table_model.mark_cell(
                    uri_index,
                    source=MarkingSource.CELL,
                    tooltip=UI_TEXT["series_uri_unknown_tooltip"],
                )
                self.table_model.mark_cell(
                    name_index,
                    source=MarkingSource.CELL,
                    tooltip=UI_TEXT["series_not_linked_tooltip"],
                )
            elif series_name == "" or series_name == "nan":
                self.table_model.mark_cell(
                    name_index,
                    source=MarkingSource.CELL,
                    tooltip=UI_TEXT["series_name_missing_tooltip"],
                )

        self.table_model.dataChanged.emit(
            self.table_model.index(0, 0),
            self.table_model.index(df.shape[0] - 1, df.shape[1] - 1),
        )

        self._update_create_sip_button()

    def _update_create_sip_button(self) -> None:
        self.create_sip_button.setEnabled(not self.table_model.has_bad_rows)

    def _assign_button_clicked(self) -> None:
        selected_indexes = self.table_view.selectionModel().selectedIndexes()
        selected_rows = sorted({idx.row() for idx in selected_indexes})

        if not selected_rows:
            self.application.notify_user_signal.emit(
                UI_TEXT["no_selection"]["title"],
                UI_TEXT["no_selection"]["text"],
            )

            return

        series = self.series_dropdown.currentData()

        if series is None:
            self.application.notify_user_signal.emit(
                UI_TEXT["no_series"]["title"],
                UI_TEXT["no_series"]["text"],
            )

            return

        source_rows = sorted(
            {self.proxy_model.mapToSource(self.proxy_model.index(row, 0)).row() for row in selected_rows}
        )

        self.assign_to_series_signal.emit(source_rows, series._id, series.get_full_name())

    def _unassigned_only_clicked(self, state: int) -> None:
        self.proxy_model.toggle_filter(TableFilter.BAD_ROWS)

    def _update_role_visibility(self) -> None:
        is_klant = self.application.configuration.active_role == KLANT_ROLE

        self.create_sip_button.setHidden(is_klant)

    def _save_button_clicked(self) -> None:
        self.application.migration_sip_db_controller.save_main_data(self.sip, self.table_model.raw_data)

        self.application.notify_user_signal.emit(
            UI_TEXT["save_success"]["title"],
            UI_TEXT["save_success"]["text"],
        )

    def _delete_rows_clicked(self) -> None:
        selected_indexes = self.table_view.selectionModel().selectedIndexes()
        selected_rows = sorted({idx.row() for idx in selected_indexes})

        if not selected_rows:
            return

        source_rows = sorted(
            {self.proxy_model.mapToSource(self.proxy_model.index(row, 0)).row() for row in selected_rows}
        )

        self.delete_rows_signal.emit(source_rows)

    def _create_sip_clicked(self) -> None:
        self.create_sip_signal.emit()
