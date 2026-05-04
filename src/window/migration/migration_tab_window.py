import os
import re

import pandas as pd
from PySide6 import QtCore, QtGui, QtWidgets

from src.controller.api_controller import APIController
from src.controller.excel_controller import ExcelController

from src.utils.constants import (
    ANALOOG_DEFAULT_VALUE,
    MIGRATION_ID_COLUMN,
    MIGRATION_MAIN_ID_COLUMN,
    SERIES_NAME_COLUMN,
    UI_TEXT_ELEMENTS,
    BusinessRules,
    ColumnName,
    DBColumnName,
    OverdrachtslijstColumnName,
    RowType,
)
from src.utils.data_objects.grid_data import GridData
from src.utils.data_objects.migration.sip import MigrationSIP
from src.utils.data_objects.sip_status import SIPStatus
from src.utils.pyside_helper import clear_widget_warning_style, set_widget_warning_style
from src.utils.workers.worker import Worker

from src.widget.central_widgets.migration.migration_grid_view import MigrationGridView
from src.widget.central_widgets.migration.migration_main_tab_view import MigrationMainTabView
from src.widget.dialog.yes_no_dialog import YesNoDialog

from src.window.base_window import Window

UI_TEXT = UI_TEXT_ELEMENTS["migration"]["tab_window"]

MAIN_TO_SERIES_COLUMN_MAPPING = {
    OverdrachtslijstColumnName.BESCHRIJVING: [ColumnName.NAAM, ColumnName.PATH_IN_SIP],
    OverdrachtslijstColumnName.BEGINDATUM: [ColumnName.OPENINGSDATUM],
    OverdrachtslijstColumnName.EINDDATUM: [ColumnName.SLUITINGSDATUM],
    OverdrachtslijstColumnName.DOOSNR: [ColumnName.ORIGINEEL_DOOSNUMMER],
}

FIXED_VALUE_COLUMNS = {
    ColumnName.ANALOOG: ANALOOG_DEFAULT_VALUE,
}

AUTO_MAP_BLOCKED_COLUMNS = {
    MIGRATION_ID_COLUMN,
    ColumnName.TYPE,
    ColumnName.DOSSIER_REF,
    ColumnName.ANALOOG,
}

URI_SERIEREGISTER_COLUMN = DBColumnName.URI_SERIEREGISTER


def _format_origineel_doosnummer(mapped_data: dict[str, list], sip_name: str) -> None:
    col = ColumnName.ORIGINEEL_DOOSNUMMER

    if col not in mapped_data:
        return

    for i, value in enumerate(mapped_data[col]):
        raw = str(value).strip()

        if not raw or raw == "nan":
            mapped_data[col][i] = ""
            continue

        if re.match(r"^\d+$", raw):
            raw = raw.zfill(4)

        mapped_data[col][i] = f"{raw}/{sip_name}"


def _derive_type_and_dossier_ref(mapped_data: dict[str, list], row_count: int) -> None:
    path_col = ColumnName.PATH_IN_SIP

    if path_col not in mapped_data:
        return

    types = []
    refs = []

    for value in mapped_data[path_col]:
        value = str(value).strip()

        if not value or value == "nan":
            types.append("")
            refs.append("")
        elif "/" in value:
            types.append(RowType.STUK)
            refs.append(value.split("/", 1)[0])
        else:
            types.append(RowType.DOSSIER)
            refs.append(value)

    mapped_data[ColumnName.TYPE] = types
    mapped_data[ColumnName.DOSSIER_REF] = refs


def _derive_naam_from_path(mapped_data: dict[str, list]) -> None:
    naam_col = ColumnName.NAAM
    path_col = ColumnName.PATH_IN_SIP

    if naam_col not in mapped_data or path_col not in mapped_data:
        return

    for i, path in enumerate(mapped_data[path_col]):
        path = str(path).strip()
        if "/" in path:
            mapped_data[naam_col][i] = path.rsplit("/", 1)[1]


def map_main_to_series(
    selected_data: pd.DataFrame,
    template_columns: list[str] | None = None,
    sip_name: str = "",
    all_data: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if all_data is None:
        all_data = selected_data
    mapped_data: dict[str, list] = {}
    row_count = len(selected_data)

    mapped_data[MIGRATION_MAIN_ID_COLUMN] = selected_data[MIGRATION_ID_COLUMN].astype(str).tolist()

    for main_col, series_cols in MAIN_TO_SERIES_COLUMN_MAPPING.items():
        if main_col in selected_data.columns:
            values = selected_data[main_col].values.tolist()
        else:
            values = [""] * row_count

        for series_col in series_cols:
            mapped_data[series_col] = list(values)

    for col_name, fixed_value in FIXED_VALUE_COLUMNS.items():
        mapped_data[col_name] = [fixed_value] * row_count

    _format_origineel_doosnummer(mapped_data, sip_name)

    # Auto-map: carry over columns from the Overdrachtslijst that match template columns.
    # This can overwrite earlier mappings (e.g. Naam, Origineel Doosnummer).
    # Read-only columns (Type, DossierRef, Analoog?) and their duplicates are never overwritten.
    # A column is only mapped if it has at least one non-empty value across the entire
    # Overdrachtslijst (not just the selected rows).
    auto_mapped_columns: set[str] = set()
    if template_columns:
        for col in template_columns:
            if col.rstrip() in AUTO_MAP_BLOCKED_COLUMNS or col not in selected_data.columns:
                continue

            if not all_data[col].astype(str).str.strip().any():
                continue

            source_values = selected_data[col].values.tolist()
            mapped_data[col] = source_values
            auto_mapped_columns.add(col)

    # Auto-map duplicate columns from the Overdrachtslijst that are NOT in the template
    # but whose base column IS in the template. Only include if the selected rows have data.
    # Location column duplicates are handled as full sets (all 4 or none).
    extra_duplicate_columns: list[str] = []
    extra_location_groups: list[list[str]] = []
    if template_columns:
        template_set = set(template_columns)

        # First, find complete location column duplicate sets
        from src.utils.grid.checks.migration.location_group_check import LOCATION_COLUMNS

        suffix = 1
        while True:
            spaces = " " * suffix
            group = [f"{base}{spaces}" for base in LOCATION_COLUMNS]
            present = [col for col in group if col in selected_data.columns]
            if not present:
                break
            # Check if any of the 4 columns have data in the selected rows
            has_data = any(selected_data[col].astype(str).str.strip().any() for col in present)
            if has_data and len(present) == 4:
                for col in group:
                    mapped_data[col] = selected_data[col].values.tolist()
                    auto_mapped_columns.add(col)
                extra_location_groups.append(group)
            suffix += 1

        # Then, find regular (non-location) duplicate columns
        location_base_set = set(LOCATION_COLUMNS)
        for col in selected_data.columns:
            if col in template_set or col in mapped_data:
                continue
            if col.rstrip() in AUTO_MAP_BLOCKED_COLUMNS:
                continue
            base_col = col.rstrip()
            if base_col in location_base_set:
                continue  # Handled above as location group
            if base_col in template_set and col != base_col:
                if selected_data[col].astype(str).str.strip().any():
                    mapped_data[col] = selected_data[col].values.tolist()
                    auto_mapped_columns.add(col)
                    extra_duplicate_columns.append(col)

    # Derive Type and DossierRef AFTER auto-mapping, so they use the final
    # Path in SIP values (which may have been auto-mapped from the source Excel).
    _derive_type_and_dossier_ref(mapped_data, row_count)

    # Only derive Naam from Path in SIP if it wasn't explicitly auto-mapped
    if ColumnName.NAAM not in auto_mapped_columns:
        _derive_naam_from_path(mapped_data)

    ordered_columns = [MIGRATION_MAIN_ID_COLUMN]

    if template_columns:
        location_base_set = set(LOCATION_COLUMNS) if extra_location_groups else set()

        for col in template_columns:
            if col not in ordered_columns and col != DBColumnName.URI_SERIEREGISTER:
                ordered_columns.append(col)
                # Insert regular duplicate columns right after their base column
                if col.rstrip() not in location_base_set:
                    for dup_col in extra_duplicate_columns:
                        if dup_col.rstrip() == col.rstrip() and dup_col not in ordered_columns:
                            ordered_columns.append(dup_col)

            # After the last location column (Verpakkingstype), insert all location groups
            if col == ColumnName.VERPAKKINGSTYPE:
                for group in extra_location_groups:
                    for loc_col in group:
                        if loc_col not in ordered_columns:
                            ordered_columns.append(loc_col)

        if DBColumnName.URI_SERIEREGISTER in template_columns:
            ordered_columns.append(DBColumnName.URI_SERIEREGISTER)

    series_df = pd.DataFrame()

    for col in ordered_columns:
        series_df[col] = mapped_data.get(col, "")

    return series_df.fillna("").reset_index(drop=True)


class MigrationTabWindow(Window):
    def __init__(self, sip: MigrationSIP) -> None:
        super().__init__()

        self.sip = sip
        self.series_tabs: dict[str, MigrationGridView] = {}
        self._active_workers: list[tuple[Worker, QtCore.QThread]] = []
        self._tabs_loading: bool = False
        self._main_has_unsaved_changes: bool = False
        self._deleted_series: set[str] = set()

        self.setWindowTitle(self.sip.name)
        self.resize(1200, 800)

        self.setup_ui()
        self.setup_signals()
        self._load_existing_series_tabs()

    def setup_ui(self) -> None:
        self.tab_widget = QtWidgets.QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self._ensure_series_name_column()
        self._auto_populate_series_names()

        self.sip.grid_data = self.sip.main_grid_data
        self.main_tab_view = MigrationMainTabView(sip=self.sip)
        self.tab_widget.addTab(self.main_tab_view, UI_TEXT["main_tab_title"])

    def setup_signals(self) -> None:
        self.main_tab_view.assign_to_series_signal.connect(self._assign_rows_to_series)
        self.main_tab_view.delete_rows_signal.connect(self._delete_rows_from_main)
        self.main_tab_view.create_sip_signal.connect(self._create_all_sips)
        self.sip.name_changed_signal.connect(lambda: self.setWindowTitle(self.sip.name))
        self.application.application_environment_changed_signal.connect(self.close)
        self.application.application_type_changed_signal.connect(self._on_type_changed)
        self.application.series_updated_signal.connect(self._on_series_updated)

    def _ensure_series_name_column(self) -> None:
        df = self.sip.main_grid_data.data_as_df
        changed = False

        if SERIES_NAME_COLUMN not in df.columns:
            df.insert(0, SERIES_NAME_COLUMN, "")
            changed = True

        if URI_SERIEREGISTER_COLUMN not in df.columns:
            df[URI_SERIEREGISTER_COLUMN] = ""
            changed = True
        elif list(df.columns)[-1] != URI_SERIEREGISTER_COLUMN:
            # Move URI Serieregister to the last column
            uri_data = df.pop(URI_SERIEREGISTER_COLUMN)
            df[URI_SERIEREGISTER_COLUMN] = uri_data
            changed = True

        if changed:
            self.sip.main_grid_data.data_as_df = df

    def _on_series_updated(self) -> None:
        if self._tabs_loading:
            return

        if self._auto_populate_series_names():
            self.main_tab_view.table_model.beginResetModel()
            self.main_tab_view.table_model.raw_data = self.sip.main_grid_data.data_as_df
            self.main_tab_view.table_model.endResetModel()

            existing_table_names = set(self.series_tabs.keys())
            self._create_missing_series_tabs(existing_table_names)

    def _auto_populate_series_names(self) -> bool:
        df = self.sip.main_grid_data.data_as_df

        if URI_SERIEREGISTER_COLUMN not in df.columns or SERIES_NAME_COLUMN not in df.columns:
            return False

        env_name = self.application.configuration.active_environment_name
        series_list = self.application.sneaky_series().get(env_name, [])
        base_uri = self.sip.environment.get_serie_register_uri()
        uri_to_name = {f"{base_uri}/{s._id}": s.get_full_name() for s in series_list}

        uri_col = df.columns.get_loc(URI_SERIEREGISTER_COLUMN)
        name_col = df.columns.get_loc(SERIES_NAME_COLUMN)
        changed = False

        for row in range(df.shape[0]):
            uri = str(df.iat[row, uri_col]).strip()
            series_name = str(df.iat[row, name_col]).strip()

            if not uri or uri == "nan":
                continue

            if series_name and series_name != "nan":
                continue

            if uri in uri_to_name:
                df.iat[row, name_col] = uri_to_name[uri]
                changed = True

        if changed:
            self.sip.main_grid_data.data_as_df = df

        return changed

    def _on_type_changed(self) -> None:
        for grid_view in self.series_tabs.values():
            grid_view.table_model.validate_all()

    def _load_existing_series_tabs(self) -> None:
        self._tabs_loading = True
        self._set_tab_loading(0, True)
        self._set_controls_busy(True)

        def background_load_tabs():
            tables = self.application.migration_sip_db_controller.read_tables(self.sip.db_name)
            results = []

            for table_name, uri_serieregister, _, _ in tables:
                df = self.application.migration_sip_db_controller.read_series_data(self.sip.db_name, table_name)
                series_id = uri_serieregister.rsplit("/", 1)[-1] if uri_serieregister else ""
                results.append((table_name, df, series_id))

            return results

        Worker.start(
            background_load_tabs,
            on_result=self._on_tabs_loaded,
            on_error=lambda e: self.application.error_handler(e),
            on_finished=self._on_load_finished,
            track_in=self._active_workers,
        )

    def _on_tabs_loaded(self, results: list[tuple[str, pd.DataFrame, str]]) -> None:
        existing_table_names = set()
        existing_uris = set()

        for table_name, df, series_id in results:
            existing_table_names.add(table_name)
            if series_id:
                base_uri = self.sip.environment.get_serie_register_uri()
                existing_uris.add(f"{base_uri}/{series_id}")

            grid_data = GridData()
            grid_data.data_as_df = df
            self.sip.series_grid_data[table_name] = grid_data

            grid_view = MigrationGridView(
                sip=self.sip, series_name=table_name, grid_data=grid_data, series_id=series_id
            )
            grid_view.table_model.validation_finished_signal.connect(self.update_global_create_sip_button)
            grid_view.create_sip_signal.connect(self._create_all_sips)
            grid_view.delete_series_rows_signal.connect(self._delete_rows_from_series)
            self.series_tabs[table_name] = grid_view

            tab_index = self.tab_widget.addTab(grid_view, table_name)
            self._set_tab_loading(tab_index, True)

        self._create_missing_series_tabs(existing_table_names, existing_uris)

    def _on_load_finished(self) -> None:
        self._tabs_loading = False
        self._set_controls_busy(False)

        for i in range(self.tab_widget.count()):
            self._set_tab_loading(i, False)

    def _set_tab_loading(self, tab_index: int, loading: bool) -> None:
        tab_bar = self.tab_widget.tabBar()

        if loading:
            tab_bar.setTabTextColor(tab_index, QtGui.QColor("red"))
            current_text = self.tab_widget.tabText(tab_index)

            if not current_text.endswith(UI_TEXT["tab_loading_text"]):
                self.tab_widget.setTabText(tab_index, f"{current_text} ({UI_TEXT['tab_loading_text']})")
        else:
            tab_bar.setTabTextColor(tab_index, QtGui.QColor())
            current_text = self.tab_widget.tabText(tab_index)
            suffix = f" ({UI_TEXT['tab_loading_text']})"

            if current_text.endswith(suffix):
                self.tab_widget.setTabText(tab_index, current_text[: -len(suffix)])

    def _create_missing_series_tabs(
        self, existing_table_names: set[str], existing_uris: set[str] | None = None
    ) -> None:
        main_df = self.sip.main_grid_data.data_as_df

        if SERIES_NAME_COLUMN not in main_df.columns or URI_SERIEREGISTER_COLUMN not in main_df.columns:
            return

        if existing_uris is None:
            existing_uris = set()

        name_col = main_df.columns.get_loc(SERIES_NAME_COLUMN)
        uri_col = main_df.columns.get_loc(URI_SERIEREGISTER_COLUMN)

        unlinked_series: dict[str, dict] = {}

        for row in range(main_df.shape[0]):
            series_name = str(main_df.iat[row, name_col]).strip()
            uri = str(main_df.iat[row, uri_col]).strip()

            if not series_name or series_name == "nan":
                continue

            if series_name in existing_table_names:
                continue

            # Also skip if this URI is already covered by an existing tab
            # (handles case where the series name changed but the URI is the same)
            if uri and uri != "nan" and uri in existing_uris:
                continue

            if series_name not in unlinked_series:
                unlinked_series[series_name] = {"rows": [], "uri": uri}

            unlinked_series[series_name]["rows"].append(row)

        for series_name, info in unlinked_series.items():
            uri = info["uri"]
            series_id = uri.rsplit("/", 1)[-1] if uri and uri != "nan" else ""

            template_columns = self._get_template_columns(series_id) if series_id else None
            series_df = self._map_main_to_series(main_df.iloc[info["rows"]].copy(), template_columns)

            uri_serieregister = uri if uri and uri != "nan" else ""

            grid_data = GridData()
            grid_data.data_as_df = series_df
            self.sip.series_grid_data[series_name] = grid_data

            self.application.migration_sip_db_controller.create_series_table(
                self.sip, uri_serieregister=uri_serieregister, table_name=series_name, df=series_df
            )
            self.sip.series_statuses[series_name] = SIPStatus.IN_PROGRESS

            grid_view = MigrationGridView(
                sip=self.sip, series_name=series_name, grid_data=grid_data, series_id=series_id
            )
            grid_view.table_model.validation_finished_signal.connect(self.update_global_create_sip_button)
            grid_view.create_sip_signal.connect(self._create_all_sips)
            grid_view.delete_series_rows_signal.connect(self._delete_rows_from_series)
            self.series_tabs[series_name] = grid_view
            self.tab_widget.addTab(grid_view, series_name)

    def _get_template_columns(self, series_id: str) -> list[str] | None:
        try:
            file_location = APIController.get_import_template(
                configuration=self.application.configuration,
                environment=self.sip.environment,
                series_id=series_id,
            )
        except Exception:
            self.application.notify_user_signal.emit(
                UI_TEXT["template_retrieval_error"]["title"],
                UI_TEXT["template_retrieval_error"]["text"],
            )
            return None

        template_df = ExcelController.read_excel(file_location)

        if template_df is None:
            return None

        return list(template_df.columns)

    def _set_controls_busy(self, busy: bool) -> None:
        self.main_tab_view.assign_button.setEnabled(not busy)
        self.main_tab_view.save_button.setEnabled(not busy)
        self.main_tab_view.create_sip_button.setEnabled(not busy)

        for grid_view in self.series_tabs.values():
            grid_view.save_button.setEnabled(not busy)
            grid_view.create_sip_button.setEnabled(not busy)

        if busy:
            set_widget_warning_style(
                self.main_tab_view.assign_button,
                tooltip=UI_TEXT["assign_loading_tooltip"],
            )
        else:
            clear_widget_warning_style(self.main_tab_view.assign_button)
            self.main_tab_view._update_create_sip_button()

            for grid_view in self.series_tabs.values():
                grid_view._update_create_sip_button()

    def _assign_rows_to_series(self, source_rows: list[int], series_id: str, series_name: str) -> None:
        table_name = series_name
        uri_serieregister = f"{self.sip.environment.get_serie_register_uri()}/{series_id}"
        self.sip.series_zip_names[table_name] = f"{series_id}-{self.sip.name}-SIPC.zip"
        main_df = self.sip.main_grid_data.data_as_df

        existing_count = 0

        if table_name in self.series_tabs:
            existing_count = len(self.series_tabs[table_name].table_model.raw_data)

        total_count = existing_count + len(source_rows)

        if total_count > BusinessRules.MAX_ROWS_PER_SERIES:
            self.application.notify_user_signal.emit(
                UI_TEXT["row_limit_error"]["title"],
                UI_TEXT["row_limit_error"]["text"].format(
                    max_rows=BusinessRules.MAX_ROWS_PER_SERIES,
                    total_rows=total_count,
                ),
            )

            return

        selected_data = main_df.iloc[source_rows].copy()

        self._remove_rows_from_old_series(main_df, source_rows, table_name)

        main_df.iloc[source_rows, main_df.columns.get_loc(SERIES_NAME_COLUMN)] = series_name
        main_df.iloc[source_rows, main_df.columns.get_loc(URI_SERIEREGISTER_COLUMN)] = uri_serieregister
        self.sip.main_grid_data.data_as_df = main_df

        self.sip.grid_data = self.sip.main_grid_data

        self.main_tab_view.table_model.beginResetModel()
        self.main_tab_view.table_model.raw_data = main_df
        self.main_tab_view.table_model.endResetModel()

        self.main_tab_view._validate_series()

        self._set_controls_busy(True)

        def background_assign():
            self.application.migration_sip_db_controller.save_main_data(self.sip, main_df)
            template_columns = self._get_template_columns(series_id)
            series_df = self._map_main_to_series(selected_data, template_columns)

            return series_df, template_columns

        Worker.start(
            background_assign,
            on_result=lambda result: self._on_assign_complete(result, table_name, uri_serieregister, series_name),
            on_error=lambda e: self.application.notify_user_signal.emit(
                UI_TEXT["assign_error"]["title"],
                UI_TEXT["assign_error"]["text"],
            ),
            on_finished=lambda: self._set_controls_busy(False),
            track_in=self._active_workers,
        )

    def _on_assign_complete(self, result: tuple, table_name: str, uri_serieregister: str, series_name: str) -> None:
        series_df, template_columns = result

        if table_name in self.series_tabs:
            existing_grid_data = self.sip.series_grid_data[table_name]
            existing_df = existing_grid_data.data_as_df

            # Use series_df column order (which has correct duplicate column placement)
            # and include any existing columns not in series_df
            all_columns = list(series_df.columns)
            for col in existing_df.columns:
                if col not in all_columns:
                    all_columns.append(col)

            combined_df = pd.concat([existing_df, series_df], ignore_index=True).fillna("")
            combined_df = combined_df[all_columns]
            existing_grid_data.data_as_df = combined_df

            grid_view = self.series_tabs[table_name]
            grid_view.table_model.beginResetModel()
            grid_view.table_model.raw_data = combined_df
            grid_view.table_model.endResetModel()

            grid_view.table_model.re_mark_disabled_columns()
            grid_view.table_model.validate_all()

            self.application.migration_sip_db_controller.save_series_data(self.sip, table_name, combined_df)
        else:
            grid_data = GridData()
            grid_data.data_as_df = series_df
            self.sip.series_grid_data[table_name] = grid_data

            self.application.migration_sip_db_controller.create_series_table(
                self.sip, uri_serieregister=uri_serieregister, table_name=table_name, df=series_df
            )
            self.sip.series_statuses[table_name] = SIPStatus.IN_PROGRESS

            series_id = uri_serieregister.rsplit("/", 1)[-1] if uri_serieregister else ""
            grid_view = MigrationGridView(
                sip=self.sip, series_name=series_name, grid_data=grid_data, series_id=series_id
            )
            grid_view.table_model.validation_finished_signal.connect(self.update_global_create_sip_button)
            grid_view.create_sip_signal.connect(self._create_all_sips)
            grid_view.delete_series_rows_signal.connect(self._delete_rows_from_series)
            self.series_tabs[table_name] = grid_view
            self.tab_widget.addTab(grid_view, series_name)

    def _find_tab_name_for_series(self, series_name: str, main_df: pd.DataFrame, row_idx: int) -> str | None:
        """Find the series_tabs key for a given series name, with URI-based fallback."""
        if series_name in self.series_tabs:
            return series_name

        # Fallback: match by URI if the name doesn't match any tab
        if URI_SERIEREGISTER_COLUMN not in main_df.columns:
            return None

        uri_col = main_df.columns.get_loc(URI_SERIEREGISTER_COLUMN)
        uri = str(main_df.iat[row_idx, uri_col]).strip()

        if not uri or uri == "nan":
            return None

        tables = self.application.migration_sip_db_controller.read_tables(self.sip.db_name)
        for table_name, table_uri, _, _ in tables:
            if table_uri == uri and table_name in self.series_tabs:
                return table_name

        return None

    def _remove_rows_from_old_series(self, main_df: pd.DataFrame, source_rows: list[int], new_table_name: str) -> None:
        if SERIES_NAME_COLUMN not in main_df.columns:
            return

        name_col = main_df.columns.get_loc(SERIES_NAME_COLUMN)
        id_col = main_df.columns.get_loc(MIGRATION_ID_COLUMN)
        main_ids_by_old_series: dict[str, list[str]] = {}

        for row_idx in source_rows:
            old_series = str(main_df.iat[row_idx, name_col]).strip()

            if not old_series or old_series == "nan":
                continue

            # Resolve the actual tab key (handles name mismatches via URI fallback)
            tab_key = self._find_tab_name_for_series(old_series, main_df, row_idx)

            if tab_key is None:
                continue

            if tab_key not in main_ids_by_old_series:
                main_ids_by_old_series[tab_key] = []

            main_ids_by_old_series[tab_key].append(str(main_df.iat[row_idx, id_col]))

        for old_series_name, main_ids in main_ids_by_old_series.items():
            if old_series_name not in self.series_tabs:
                continue

            grid_view = self.series_tabs[old_series_name]
            old_df = grid_view.table_model.raw_data
            main_id_set = set(main_ids)

            remaining_df = old_df[~old_df[MIGRATION_MAIN_ID_COLUMN].astype(str).isin(main_id_set)].reset_index(
                drop=True
            )

            if remaining_df.empty:
                tab_index = self.tab_widget.indexOf(grid_view)
                self.tab_widget.removeTab(tab_index)
                grid_view.deleteLater()

                del self.series_tabs[old_series_name]
                del self.sip.series_grid_data[old_series_name]

                self.application.migration_sip_db_controller.delete_series_table(self.sip, old_series_name)
            else:
                grid_view.grid_data.data_as_df = remaining_df

                grid_view.table_model.beginResetModel()
                grid_view.table_model.raw_data = remaining_df
                grid_view.table_model.drop_orphan_markings()
                grid_view.table_model.endResetModel()

                self.application.migration_sip_db_controller.save_series_data(self.sip, old_series_name, remaining_df)

    def _map_main_to_series(
        self, selected_data: pd.DataFrame, template_columns: list[str] | None = None
    ) -> pd.DataFrame:
        return map_main_to_series(
            selected_data,
            template_columns,
            self.sip.name,
            all_data=self.sip.main_grid_data.data_as_df,
        )

    def _delete_rows_from_main(self, source_rows: list[int]) -> None:
        """Delete rows from the Overdrachtslijst and cascade to series tabs."""
        main_df = self.sip.main_grid_data.data_as_df
        id_col = main_df.columns.get_loc(MIGRATION_ID_COLUMN)
        main_ids = [str(main_df.iat[row, id_col]) for row in source_rows]
        main_id_set = set(main_ids)

        # Remove matching rows from all series tabs
        for series_name in list(self.series_tabs.keys()):
            grid_view = self.series_tabs[series_name]
            series_df = grid_view.table_model.raw_data

            if MIGRATION_MAIN_ID_COLUMN not in series_df.columns:
                continue

            remaining_df = series_df[~series_df[MIGRATION_MAIN_ID_COLUMN].astype(str).isin(main_id_set)].reset_index(
                drop=True
            )

            if remaining_df.empty:
                tab_index = self.tab_widget.indexOf(grid_view)
                self.tab_widget.removeTab(tab_index)
                grid_view.deleteLater()

                del self.series_tabs[series_name]
                del self.sip.series_grid_data[series_name]

                self._deleted_series.add(series_name)
            else:
                grid_view.grid_data.data_as_df = remaining_df

                grid_view.table_model.beginResetModel()
                grid_view.table_model.raw_data = remaining_df
                grid_view.table_model.drop_orphan_markings()
                grid_view.table_model.endResetModel()

                grid_view.has_unsaved_changes = True
                grid_view.table_model.re_mark_disabled_columns()
                grid_view.table_model.validate_all()

        # Remove rows from main DataFrame
        updated_main_df = main_df.drop(index=source_rows).reset_index(drop=True)
        self.sip.main_grid_data.data_as_df = updated_main_df

        self.main_tab_view.table_model.beginResetModel()
        self.main_tab_view.table_model.raw_data = updated_main_df
        self.main_tab_view.table_model.drop_orphan_markings()
        self.main_tab_view.table_model.endResetModel()

        self._main_has_unsaved_changes = True
        self.main_tab_view._validate_series()

    def _delete_rows_from_series(self, series_name: str, source_rows: list[int]) -> None:
        """Delete rows from a series tab and clear the assignment in Overdrachtslijst."""
        if series_name not in self.series_tabs:
            return

        grid_view = self.series_tabs[series_name]
        series_df = grid_view.table_model.raw_data

        # Get main_ids for the rows being deleted
        deleted_main_ids = set()
        if MIGRATION_MAIN_ID_COLUMN in series_df.columns:
            for row in source_rows:
                deleted_main_ids.add(str(series_df.iloc[row, series_df.columns.get_loc(MIGRATION_MAIN_ID_COLUMN)]))

        # Clear series_name and URI in the main DataFrame for matching rows
        main_df = self.sip.main_grid_data.data_as_df
        if SERIES_NAME_COLUMN in main_df.columns and MIGRATION_ID_COLUMN in main_df.columns:
            name_col = main_df.columns.get_loc(SERIES_NAME_COLUMN)
            uri_col = main_df.columns.get_loc(URI_SERIEREGISTER_COLUMN)
            id_col = main_df.columns.get_loc(MIGRATION_ID_COLUMN)

            for main_id in deleted_main_ids:
                matches = main_df.index[main_df.iloc[:, id_col].astype(str) == str(main_id)]
                for row_idx in matches:
                    main_df.iat[row_idx, name_col] = ""
                    main_df.iat[row_idx, uri_col] = ""

            self.sip.main_grid_data.data_as_df = main_df

            self.main_tab_view.table_model.beginResetModel()
            self.main_tab_view.table_model.raw_data = main_df
            self.main_tab_view.table_model.endResetModel()

            self._main_has_unsaved_changes = True
            self.main_tab_view._validate_series()

        # Remove rows from series DataFrame
        remaining_df = series_df.drop(index=source_rows).reset_index(drop=True)

        if remaining_df.empty:
            tab_index = self.tab_widget.indexOf(grid_view)
            self.tab_widget.removeTab(tab_index)
            grid_view.deleteLater()

            del self.series_tabs[series_name]
            del self.sip.series_grid_data[series_name]

            self._deleted_series.add(series_name)
        else:
            grid_view.grid_data.data_as_df = remaining_df

            grid_view.table_model.beginResetModel()
            grid_view.table_model.raw_data = remaining_df
            grid_view.table_model.drop_orphan_markings()
            grid_view.table_model.endResetModel()

            grid_view.has_unsaved_changes = True
            grid_view.table_model.validate_all()

        self.update_global_create_sip_button()

    def update_global_create_sip_button(self) -> None:
        all_valid = (
            bool(self.series_tabs)
            and all(
                not gv.table_model.has_bad_rows and gv.series is not None and not gv.table_model.is_validating
                for gv in self.series_tabs.values()
            )
            and not self.main_tab_view.table_model.has_bad_rows
        )

        self.main_tab_view.create_sip_button.setEnabled(all_valid)

        for grid_view in self.series_tabs.values():
            grid_view.create_sip_button.setEnabled(all_valid)

        self.sip.set_grid_valid(all_valid)

    def _create_all_sips(self) -> None:
        for grid_view in self.series_tabs.values():
            grid_view._save_button_clicked(silent=True)

        self.main_tab_view._save_button_clicked()

        series_data: list[tuple[str, str, pd.DataFrame]] = []

        for series_name, grid_view in self.series_tabs.items():
            if grid_view.series is None:
                continue

            series_id = grid_view.series._id
            df = grid_view.table_model.raw_data.copy()

            if MIGRATION_MAIN_ID_COLUMN in df.columns:
                df = df.drop(columns=[MIGRATION_MAIN_ID_COLUMN])

            if len(df) > BusinessRules.MAX_ROWS_PER_SERIES:
                self.application.notify_user_signal.emit(
                    UI_TEXT["row_limit_error"]["title"],
                    UI_TEXT["row_limit_error"]["text"].format(
                        max_rows=BusinessRules.MAX_ROWS_PER_SERIES,
                        total_rows=len(df),
                    ),
                )

                return

            series_data.append((series_name, series_id, df))

        if not series_data:
            return

        self._set_controls_busy(True)

        def background_create_sips():
            from src.controller.sip_creation_controller import create_migration_series_sips

            create_migration_series_sips(self.sip, self.application.configuration, series_data)

            return True

        Worker.start(
            background_create_sips,
            on_result=self._on_all_sips_created,
            on_error=lambda e: self.application.error_handler(e),
            on_finished=lambda: self._set_controls_busy(False),
            track_in=self._active_workers,
        )

    def _on_all_sips_created(self, success: bool) -> None:
        if not success:
            return

        for series_name in self.series_tabs:
            self.sip.series_statuses[series_name] = SIPStatus.SIP_CREATED

            self.application.migration_sip_db_controller.update_series_status(
                self.sip, series_name, SIPStatus.SIP_CREATED
            )

        self.sip.set_status(SIPStatus.SIP_CREATED)

        self.application.notify_user_signal.emit(
            UI_TEXT["create_all_sips_success"]["title"],
            UI_TEXT["create_all_sips_success"]["text"],
        )

        self.close()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        has_unsaved = (
            self._main_has_unsaved_changes
            or bool(self._deleted_series)
            or any(grid_view.has_unsaved_changes for grid_view in self.series_tabs.values())
        )

        if has_unsaved:
            dialog = YesNoDialog(
                title=UI_TEXT["unsaved_changes_dialog"]["title"],
                text=UI_TEXT["unsaved_changes_dialog"]["text"],
            )
            dialog.exec()

            if dialog.result():
                self._save_all_pending_changes()

                self.application.notify_user_signal.emit(
                    UI_TEXT["save_all_success"]["title"],
                    UI_TEXT["save_all_success"]["text"],
                )

        super().closeEvent(event)

    def _save_all_pending_changes(self) -> None:
        db_controller = self.application.migration_sip_db_controller

        if self._main_has_unsaved_changes:
            db_controller.save_main_data(self.sip, self.sip.main_grid_data.data_as_df)
            self._main_has_unsaved_changes = False

        for series_name in self._deleted_series:
            db_controller.delete_series_table(self.sip, series_name)
        self._deleted_series.clear()

        for grid_view in self.series_tabs.values():
            if grid_view.has_unsaved_changes:
                grid_view._save_button_clicked(silent=True)
