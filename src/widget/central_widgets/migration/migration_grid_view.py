import re

from PySide6 import QtCore, QtWidgets

from src.controller.migration.bestandscontrole_controller import VALUE_TO_COLUMN

from src.utils.constants import KLANT_ROLE, MIGRATION_MAIN_ID_COLUMN, UI_TEXT_ELEMENTS, ColumnName
from src.utils.data_objects.grid_data import GridData
from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.data_objects.series import Series
from src.utils.grid.checks.common.date_check import DateCheck
from src.utils.grid.checks.migration.location_group_check import LOCATION_COLUMNS, _get_location_groups
from src.utils.grid.table.migration_data_verification_table import MigrationDataVerificationTable
from src.utils.pyside_helper import clear_widget_warning_style, set_widget_warning_style

from src.widget.central_widgets.base_grid_view import COMMON_GRID_TEXT, BaseGridView

UI_TEXT = UI_TEXT_ELEMENTS["migration"]["grid"]

NON_DUPLICATABLE_COLUMNS = {
    MIGRATION_MAIN_ID_COLUMN,
    ColumnName.PATH_IN_SIP.value,
    ColumnName.TYPE.value,
    ColumnName.DOSSIER_REF.value,
    ColumnName.ANALOOG.value,
    ColumnName.NAAM.value,
    ColumnName.OPENINGSDATUM.value,
    ColumnName.SLUITINGSDATUM.value,
    ColumnName.ORIGINEEL_DOOSNUMMER.value,
    ColumnName.LEGACY_LOCATIE_ID.value,
    ColumnName.LEGACY_RANGE.value,
    ColumnName.VERPAKKINGSTYPE.value,
}

LOCATION_COLUMN_BASES = {
    ColumnName.ORIGINEEL_DOOSNUMMER.value,
    ColumnName.LEGACY_LOCATIE_ID.value,
    ColumnName.LEGACY_RANGE.value,
    ColumnName.VERPAKKINGSTYPE.value,
}


class MigrationGridView(BaseGridView):
    NON_DUPLICATABLE_COLUMNS = NON_DUPLICATABLE_COLUMNS

    create_sip_signal = QtCore.Signal()

    def __init__(self, sip: MigrationSIP, series_name: str, grid_data: GridData, series_id: str = "") -> None:
        super().__init__(sip)

        self.series_name = series_name
        self.series_id = series_id
        self.grid_data = grid_data
        self.series: Series | None = None

        self._lookup_series()
        self.setup_ui()
        self._update_date_check_series()
        self.setup_signals()
        self._update_role_visibility()

    def _lookup_series(self) -> None:
        env_name = self.application.configuration.active_environment_name
        series_list = self.application.sneaky_series().get(env_name, [])

        if self.series_id:
            for s in series_list:
                if s._id == self.series_id:
                    self.series = s
                    return

        for s in series_list:
            if s.get_full_name() == self.series_name:
                self.series = s
                return

    def setup_ui(self) -> None:
        self._create_common_widgets(UI_TEXT)

        self.duplicate_location_button = QtWidgets.QPushButton(text=UI_TEXT["duplicate_location_columns_button_text"])

        self.load_bestandscontrole_button = QtWidgets.QPushButton(text=UI_TEXT["load_bestandscontrole_button_text"])

        previous_grid_data = self.sip.grid_data
        self.sip.grid_data = self.grid_data
        self._create_table(MigrationDataVerificationTable(sip=self.sip))
        self.sip.grid_data = previous_grid_data

        self._hide_main_id_column()

        self._update_series_label()
        self.table_model.validate_all()

        self.duplication_layout = QtWidgets.QHBoxLayout()
        self.duplication_layout.setContentsMargins(0, 0, 0, 0)
        self.duplication_layout.addWidget(self.column_dropdown, 1)
        self.duplication_layout.addWidget(self.add_column_button, 1)
        self.duplication_layout.addWidget(self.duplicate_location_button, 1)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.save_button, 1)
        button_layout.addWidget(self.create_sip_button, 1)

        self.grid_layout.addWidget(self.series_label, 0, 0, 1, 4)
        self.grid_layout.addWidget(self.default_sorting_button, 0, 4, 1, 1)
        self.grid_layout.addWidget(self.show_bad_rows_checkbox, 1, 0)
        self.grid_layout.addWidget(self.load_bestandscontrole_button, 1, 1)
        self.grid_layout.addLayout(self.duplication_layout, 1, 2, 1, 3)
        self.grid_layout.addWidget(self.table_view, 2, 0, 1, 5)
        self.grid_layout.addLayout(button_layout, 3, 0, 1, 5)

    def setup_signals(self) -> None:
        self._connect_common_signals()
        self.duplicate_location_button.clicked.connect(self._duplicate_location_columns_clicked)
        self.load_bestandscontrole_button.clicked.connect(self._load_bestandscontrole_clicked)
        self.application.series_updated_signal.connect(self._on_series_updated)
        self.application.application_role_changed_signal.connect(self._update_role_visibility)

    def _update_date_check_series(self) -> None:
        for validator in self.table_model.COLUMN_VALIDATORS.values():
            if isinstance(validator, DateCheck):
                validator._series_provider = lambda: self.series

    def _on_series_updated(self) -> None:
        if self.series:
            return

        self._lookup_series()
        self._update_series_label()

        if self.series:
            self.table_model.validate_all()

    def _update_series_label(self) -> None:
        if self.series:
            self.series_label.setText(self.series.get_full_name())
            clear_widget_warning_style(self.series_label)
        else:
            self.series_label.setText(self.series_name)
            set_widget_warning_style(self.series_label, COMMON_GRID_TEXT["series_not_found_tooltip"])

        self._update_create_sip_button()

    def _hide_main_id_column(self) -> None:
        columns = list(self.table_model.raw_data.columns)

        if MIGRATION_MAIN_ID_COLUMN in columns:
            self.table_view.hideColumn(columns.index(MIGRATION_MAIN_ID_COLUMN))

    def _populate_column_dropdown(self) -> None:
        seen = set()

        for col in self.table_model.raw_data.columns:
            base_col = col.rstrip()

            if base_col in self.NON_DUPLICATABLE_COLUMNS:
                continue

            if re.match(r".+_\d+$", base_col):
                base_col = re.sub(r"_\d+$", "", base_col)

                if base_col in self.NON_DUPLICATABLE_COLUMNS:
                    continue

            if base_col not in seen:
                self.column_dropdown.addItem(base_col)
                seen.add(base_col)

    def _update_create_sip_button(self) -> None:
        self.create_sip_button.setEnabled(
            not self.table_model.has_bad_rows and self.series is not None and not self.table_model.is_validating
        )

    def _duplicate_location_columns_clicked(self) -> None:
        df = self.table_model.raw_data
        columns = list(df.columns)
        groups = _get_location_groups(columns)

        if not groups:
            return

        last_group = groups[-1]
        last_verpakkingstype = last_group[-1]

        suffix = len(groups)

        new_columns = [f"{base}_{suffix}" for base in LOCATION_COLUMNS]

        insert_pos = columns.index(last_verpakkingstype) + 1

        self.table_model.beginResetModel()

        for i, col_name in enumerate(new_columns):
            df.insert(insert_pos + i, col_name, "")
            self.table_model.shift_markings_for_insert(insert_pos + i)

        from src.utils.grid.checks.digital.empty_row_check import mark_empty_rows

        mark_empty_rows(self.table_model)
        self.table_model.endResetModel()

    def _update_role_visibility(self) -> None:
        is_klant = self.application.configuration.active_role == KLANT_ROLE

        self.duplicate_location_button.setHidden(is_klant)

        if is_klant:
            self.duplication_layout.insertStretch(0, 1)
        else:
            item = self.duplication_layout.itemAt(0)

            if item and item.spacerItem():
                self.duplication_layout.removeItem(item)

        self.load_bestandscontrole_button.setHidden(is_klant)
        self.create_sip_button.setHidden(is_klant)

        self._update_location_column_visibility(is_klant)

    def _update_location_column_visibility(self, hide: bool) -> None:
        for i, col_name in enumerate(self.table_model.raw_data.columns):
            base_col = re.sub(r"_\d+$", "", col_name.rstrip())

            if base_col in LOCATION_COLUMN_BASES:
                if hide:
                    self.table_view.hideColumn(i)
                else:
                    self.table_view.showColumn(i)

    def _load_bestandscontrole_clicked(self) -> None:
        controller = self.application.bestandscontrole_controller

        if not controller.valid:
            self.application.notify_user_signal.emit(
                UI_TEXT["bestandscontrole_invalid"]["title"],
                UI_TEXT["bestandscontrole_invalid"]["text"],
            )

            return

        values = controller.get_values(overdrachtslijst_name=self.sip.overdrachtslijst_name)

        if values is None:
            return

        df = self.table_model.raw_data
        col_indices = []

        for source_col, target_col in VALUE_TO_COLUMN.items():
            matching_cols = [i for i, c in enumerate(df.columns) if c.rstrip() == target_col]

            for col_idx in matching_cols:
                col_indices.append(col_idx)
                new_val = values[source_col]

                for r in range(len(df)):
                    self.table_model.setData(
                        self.table_model.index(r, col_idx),
                        new_val,
                    )

        if col_indices:
            self.table_model.dataChanged.emit(
                self.table_model.index(0, min(col_indices)),
                self.table_model.index(len(df) - 1, max(col_indices)),
            )

    def _save_button_clicked(self, silent: bool = False) -> None:
        self.grid_data.data_as_df = self.table_model.raw_data
        self.application.migration_sip_db_controller.save_series_data(
            self.sip,
            self.series_name,
            self.table_model.raw_data,
        )
        self.has_unsaved_changes = False

        if not silent:
            self.application.notify_user_signal.emit(
                UI_TEXT["save_success"]["title"],
                UI_TEXT["save_success"]["text"],
            )

    def _create_sip_clicked(self) -> None:
        self.create_sip_signal.emit()
