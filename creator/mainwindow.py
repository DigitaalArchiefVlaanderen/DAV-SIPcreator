import os
import json

from PySide6 import QtWidgets, QtCore, QtGui
import pandas as pd
import sqlite3 as sql

from .application import Application

from .widgets.searchable_list_widget import (
    SearchableSelectionListView,
    SIPListWidget,
)
from .widgets.dossier_widget import DossierWidget
from .widgets.sip_widget import SIPWidget
from .widgets.toolbar import Toolbar
from .widgets.dialog import YesNoDialog
from .widgets.warning_dialog import WarningDialog

from .controllers.file_controller import FileController

from .utils.state import State
from .utils.state_utils.dossier import Dossier
from .utils.state_utils.sip import SIP
from .utils.sip_status import SIPStatus

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self.central_widget = None

        # Toolbar
        self.toolbar = Toolbar()
        self.addToolBar(self.toolbar)

    def closeEvent(self, event):
        # If the main window dies, kill the whole application
        if any(
            s.status == SIPStatus.UPLOADING
            for s in self.application.db_controller.read_sips()
        ):
            WarningDialog(
                title="Upload bezig",
                text="Waarschuwing, een upload is momenteel bezig, de applicatie kan niet gesloten worden.",
            ).exec()

            event.ignore()
            return

        event.accept()
        self.application.quit()

class DigitalWidget(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self.state.sip_edepot_failed.connect(self.fail_reason_show)

    def fail_reason_show(self, sip: SIP, reason: str):
        WarningDialog(
            title="SIP upload gefaald",
            text=f"SIP '{sip.name}' is geweigerd door het Edepot met volgende reden:\n\n{reason}",
        ).exec()

        storage_location = self.state.configuration.misc.save_location
        with open(
            os.path.join(
                storage_location, FileController.SIP_STORAGE, sip.error_file_name
            ),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(
                f"SIP '{sip.name}' is geweigerd door het Edepot met volgende reden:\n\n{reason}"
            )

    def setup_ui(self):
        grid_layout = QtWidgets.QGridLayout()
        self.setLayout(grid_layout)

        # Dossiers
        add_dossier_button = QtWidgets.QPushButton(text="Voeg een dossier toe")
        add_dossier_button.clicked.connect(self.add_dossier_clicked)

        add_dossiers_button = QtWidgets.QPushButton(text="Voeg folder met dossiers toe")
        add_dossiers_button.clicked.connect(
            lambda: self.add_dossier_clicked(multi=True)
        )

        self.dossiers_list_view = SearchableSelectionListView()

        grid_layout.addWidget(add_dossier_button, 0, 0)
        grid_layout.addWidget(add_dossiers_button, 0, 1)
        grid_layout.addWidget(self.dossiers_list_view, 1, 0, 1, 2)

        # SIPS
        self.create_sip_button = QtWidgets.QPushButton(text="Start SIP")
        self.create_sip_button.clicked.connect(self.create_sip_clicked)
        self.create_sip_button.setEnabled(False)
        self.sip_list_view = SIPListWidget()
        
        self.parent().toolbar.configuration_changed.connect(self.sip_list_view.reload_widgets)

        grid_layout.addWidget(self.create_sip_button, 0, 2, 1, 2)
        grid_layout.addWidget(self.sip_list_view, 1, 2, 1, 2)

    def load_items(self):
        removed_dossiers = []
        dossier_widgets = []

        for dossier in self.application.state.dossiers:
            if dossier.disabled:
                continue

            if not os.path.exists(dossier.path):
                removed_dossiers.append(dossier)
                continue

            dossier_widget = DossierWidget(dossier=dossier)

            dossier_widgets.append(dossier_widget)

        self.dossiers_list_view.add_items(
            widgets=dossier_widgets,
            selection_changed_callback=self.dossier_selection_changed,
            first_launch=True,
        )

        if len(removed_dossiers) > 0:
            dialog = YesNoDialog(
                title="Verwijderde dossiers",
                text="Een aantal dossiers lijken niet meer op hun plaats te staan.\nWilt u deze ook uit de lijst verwijderen?\n\nDeze boodschap zal anders blijven verschijnen.",
            )
            dialog.exec()

            if dialog.result():
                for dossier in removed_dossiers:
                    dossier.disabled = True
                    self.application.state.remove_dossier(dossier)

        missing_sips = []
        sips = self.application.state.sips
        sorted_sips = sorted(sips, key=lambda s: s.status.get_priority(), reverse=True)

        for sip in sorted_sips:
            # Check for missing sips
            if sip.status in (
                SIPStatus.SIP_CREATED,
                SIPStatus.UPLOADING,
                SIPStatus.UPLOADED,
                SIPStatus.ACCEPTED,
                SIPStatus.REJECTED,
            ):
                base_sip_path = os.path.join(
                    self.state.configuration.misc.save_location,
                    FileController.SIP_STORAGE,
                )
                # Check if the saved SIP and sidecar still exists
                if not os.path.exists(
                    os.path.join(
                        base_sip_path,
                        sip.file_name,
                    )
                    or not os.path.exists(
                        os.path.join(base_sip_path, sip.sidecare_file_name)
                    )
                ):
                    missing_sips.append(sip.name)

                    continue

            sip_widget = SIPWidget(sip=sip)

            try:
                if sip.metadata_file_path != "":
                    sip_widget.metadata_df = pd.read_excel(
                        sip.metadata_file_path, dtype=str
                    )
            except Exception:
                missing_sips.append(sip.name)
                continue

            sip.value_changed.connect(self.state.update_sip)

            # Uploading is not a valid state, could have happened because of forced shutdown during upload
            if sip.status == SIPStatus.UPLOADING:
                sip.set_status(SIPStatus.SIP_CREATED)

            result = FileController.existing_grid(
                self.application.state.configuration, sip
            )

            if result is not None:
                grid = result

                sip_widget.import_template_df = grid
                sip_widget.import_template_location = os.path.join(
                    self.application.state.configuration.misc.save_location,
                    FileController.IMPORT_TEMPLATE_STORAGE,
                    f"{sip.series._id}.xlsx",
                )

            if sip.status != SIPStatus.IN_PROGRESS:
                sip_widget.open_button.setEnabled(False)

            if sip.status == SIPStatus.SIP_CREATED:
                sip_widget.upload_button.setEnabled(True)
                
            if sip.status in (
                SIPStatus.UPLOADED,
                SIPStatus.PROCESSING,
                SIPStatus.ACCEPTED,
                SIPStatus.REJECTED,
                SIPStatus.SIP_CREATED,
            ):
                sip_widget.open_explorer_button.setEnabled(True)

            if sip.status in (SIPStatus.PROCESSING, SIPStatus.ACCEPTED, SIPStatus.REJECTED):
                sip_widget.open_edepot_button.setEnabled(True)

            self.sip_list_view.add_item(
                searchable_name_field="sip_name",
                widget=sip_widget,
            )

        if len(missing_sips) > 0:
            WarningDialog(
                title="Missende bestanden",
                text=f"Een of meerdere sips, sidecars of metadata zijn niet aanwezig.\n\nMissende sips: {json.dumps(missing_sips, indent=4)}\n\nDeze bestanden zijn nodig om gegevens in te laden, deze sips worden overgeslagen.",
            ).exec()

    def add_dossier_clicked(self, multi=False):
        dossier_path = QtWidgets.QFileDialog.getExistingDirectory(
            caption="Selecteer dossier om toe te voegen"
        )

        if dossier_path != "":
            paths = [dossier_path]

            if multi:
                paths = os.listdir(dossier_path)

            overlapping_labels = self.dossiers_list_view.get_overlapping_values(paths)

            unique_paths = [p for p in paths if p not in overlapping_labels]

            bad_dossiers = [
                os.path.normpath(os.path.join(dossier_path, partial_path))
                for partial_path in overlapping_labels
            ]
            dossiers = []
            dossier_widgets = []

            estimated_seconds = len(unique_paths) // 800

            if estimated_seconds > 2:
                WarningDialog(
                    title="Dossiers toevoegen",
                    text=f"Het toevoegen van veel dossiers kan een tijdje duren.\n\nGeschatte tijd: {estimated_seconds} seconden",
                ).exec()

            for partial_path in unique_paths:
                path = os.path.normpath(os.path.join(dossier_path, partial_path))

                # NOTE: we do not care about files in there, we only take the folders as dossiers
                if not os.path.isdir(path):
                    continue

                dossier = Dossier(path=path)
                dossiers.append(dossier)

                dossier_widget = DossierWidget(dossier=dossier)

                dossier_widgets.append(dossier_widget)

            self.dossiers_list_view.add_items(
                widgets=dossier_widgets,
                selection_changed_callback=self.dossier_selection_changed,
            )

            self.state.add_dossiers(dossiers=dossiers)

            if len(bad_dossiers) > 0:
                WarningDialog(
                    title="Dossiers niet toegevoegd",
                    text=f"Sommige dossiers overlappen in naamgeving met bestaande dossiers.\n\nDossiers die overlappen: {json.dumps(bad_dossiers, indent=4)}.\n\nVerander de namen van de dossiers (foldernamen) zodat ze uniek zijn in de lijst van dossiers en voeg opnieuw toe.",
                ).exec()

    def create_sip_clicked(self):
        selected_dossiers = list(self.dossiers_list_view.get_selected())

        if len(selected_dossiers) > 0:
            dossiers = [d.dossier for d in selected_dossiers]

            sip = SIP(
                environment_name=self.application.state.configuration.active_environment_name,
                dossiers=dossiers,
            )
            sip.value_changed.connect(self.state.update_sip)
            sip_widget = SIPWidget(sip=sip)

            success = self.sip_list_view.add_item(
                searchable_name_field="sip_id",
                widget=sip_widget,
            )

            if success:
                self.application.state.add_sip(sip)

                # Remove the dossiers from the list
                self.dossiers_list_view.remove_selected_clicked()

                # Open the SIP
                sip_widget.open_button_clicked()

    def dossier_selection_changed(self):
        self.create_sip_button.setEnabled(
            len(self.dossiers_list_view.get_selected()) > 0
        )

class MigrationWidget(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state
        
        self.list_storage_path = f"{self.state.configuration.misc.save_location}/overdrachtslijsten"

        self._layout = QtWidgets.QGridLayout()
        self.list_view = SearchableSelectionListView(item_type_str="overdrachtslijsten")

        self.main_db = "main.db"

    def setup_ui(self):
        self.setLayout(self._layout)

        # MAIN UI
        add_item_button = QtWidgets.QPushButton(text="Importeer overdrachtslijst")
        add_item_button.clicked.connect(self.add_overdrachtslijst_click)

        self._layout.addWidget(add_item_button, 0, 1, 1, 2)
        self._layout.addWidget(self.list_view, 1, 0, 1, 4)

        from creator.controllers.api_controller import APIController

        self.series = APIController.get_series(self.state.configuration)

    def load_items(self):
        os.makedirs(self.list_storage_path, exist_ok=True)

        for partial_path in os.listdir(self.list_storage_path):
            path = os.path.join(self.list_storage_path, partial_path)

            tab_ui = TabUI(path=path, series=self.series)
            self.list_view.add_item("name", ListView(tab_ui))

            tab_ui.setup_ui()
            tab_ui.load_items()

    def add_overdrachtslijst_click(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            caption="Selecteer Overdrachtslijst", filter="Overdrachtslijst (*.xlsx *.xlsm *.xltx *.xltm)"
        )

        tab_ui = TabUI(path=path, series=self.series)
        self.list_view.add_item("name", ListView(tab_ui))

        tab_ui.setup_ui()
        tab_ui.load_items()
        tab_ui.show()


class TabUI(QtWidgets.QMainWindow):
    def __init__(self, path: str, series: list):
        super().__init__()
        from creator.widgets.tableview_widget import TableView

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self.storage_base = f"{self.state.configuration.misc.save_location}/overdrachtslijsten"

        self.toolbar = Toolbar()

        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.db_location = f"{self.storage_base}/{self.name}.db"
        self.series = series

        self._layout = QtWidgets.QGridLayout()
        self.tabs: dict[str, QtWidgets.QTableView] = dict()

        self.main_tab = "Overdrachtslijst"
        self.main_table = TableView()

        self.tab_widget = QtWidgets.QTabWidget()

    def setup_ui(self):
        self.resize(800, 600)
        self.setWindowTitle(self.name)
        self.addToolBar(self.toolbar)

        central_widget = QtWidgets.QWidget()
        central_widget.setLayout(self._layout)
        self.setCentralWidget(central_widget)

        self._layout.addWidget(self.tab_widget, 0, 0)

        save_button = QtWidgets.QPushButton(text="Opslaan")
        save_button.clicked.connect(self.save_tabs)
        self._layout.addWidget(save_button, 1, 0)

    def load_items(self):
        if self.create_db():
            # No need to load if the db already existed
            self.load_overdrachtslijst()
        
        self.load_main_tab()
        self.load_other_tabs()

    def create_db(self) -> bool:
        import sqlite3 as sql
        import os

        os.makedirs(self.storage_base, exist_ok=True)

        if os.path.exists(self.db_location):
            return False

        conn = sql.connect(self.db_location)

        with conn:
            conn.execute("""
            CREATE TABLE tables (
                id INTEGER PRIMARY KEY,
                table_name TEXT,
                uri_serieregister TEXT,

                UNIQUE(table_name)
            );""")

            conn.execute(f"""
            INSERT INTO tables (table_name)
            VALUES ('{self.main_tab}');
            """)

            conn.commit()

        return True

    def load_overdrachtslijst(self):
        import pandas as pd
        from openpyxl import load_workbook
        import sqlite3 as sql

        wb = load_workbook(
            self.path,
            read_only=True,
            data_only=True,
            keep_links=False,
            rich_text=False,
        )

        if not self.main_tab in wb.sheetnames:
            raise ValueError(f"{self.main_tab} tab missing")

        ws = wb[self.main_tab]
        data = ws.values

        header_transform = lambda h: str(h).strip().lower().replace(" ", "_").replace("-", "_").replace("\n", "").replace(".", "")

        while "doosnr" != header_transform((headers := next(data))[0]):
            pass
        
        # Filter out empty headers
        headers = [
            header_transform(h)
            for h in headers
            if h is not None
        ]

        # Filter out empty rows
        df = pd.DataFrame(
            (
                r for r in 
                (r[:len(headers)] for r in list(data))
                if not all(not bool(v) for v in r)
            ),
            columns=headers,
        ).fillna("").astype(str).convert_dtypes()

        # NOTE: add headers if needed
        added_headers = ("id", "series_name", "uri_serieregister")

        for h in added_headers:
            if not h in df.columns:
                df[h] = ""

            if h == "id":
                df[h] = range(df.shape[0])

        # NOTE: reorder headers
        cols = df.columns.tolist()
        cols = [added_headers[0], added_headers[1], *(c for c in cols if c not in added_headers), added_headers[2]]
        df = df[cols]

        con = sql.connect(self.db_location)
        df.to_sql(
            name=self.main_tab,
            con=con,
            index=False,
            method="multi",
            # if_exists="append",
            chunksize=1000,
        )

    def load_main_tab(self):
        from creator.utils.sqlitemodel import SQLliteModel

        container = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        container.setLayout(layout)

        listed_series = self.series
        series_names = [s.get_name() for s in listed_series if s.status == "Published"]
        
        series_combobox = QtWidgets.QComboBox()
        series_combobox.setEditable(True)
        series_combobox.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        series_combobox.completer().setCompletionMode(
            QtWidgets.QCompleter.PopupCompletion
        )
        series_combobox.completer().setFilterMode(
            QtCore.Qt.MatchFlag.MatchContains
        )
        series_combobox.setMaximumWidth(900)
        series_combobox.addItems(series_names)

        btn = QtWidgets.QPushButton(text="Voeg toe")
        btn.clicked.connect(
            lambda: 
            self.add_to_new(
                name = series_combobox.currentText(),
                uri = f"https://serieregister.vlaanderen.be/id/serie/{listed_series[series_names.index(series_combobox.currentText())]._id}"
            )
        )

        model = SQLliteModel(self.main_tab, db_name=self.db_location, is_main=True)
        self.main_table.setModel(model)

        unassigned_only_checkbox = QtWidgets.QCheckBox(text="Toon enkel rijen zonder serie")
        unassigned_only_checkbox.stateChanged.connect(self._filter_unassigned)

        layout.addWidget(btn, 0, 0)
        layout.addWidget(series_combobox, 0, 1, 1, 3)
        layout.addWidget(unassigned_only_checkbox, 1, 0, 1, 2)
        layout.addWidget(self.main_table, 2, 0, 1, 5)

        conn = sql.connect(self.db_location)

        with conn:
            # NOTE: set all the series_names where the series_id matches one we got
            for s in listed_series:
                name = s.get_name().strip().replace('"', "").replace("'", "")

                conn.execute(f"""
                    UPDATE {self.main_tab}
                    SET series_name='"{name}"'
                    WHERE uri_serieregister='https://serieregister.vlaanderen.be/id/serie/{s._id}';
                """)

        self.tab_widget.addTab(container, self.main_tab)
        self.tabs[self.main_tab] = self.main_table

    def load_other_tabs(self):
        conn = sql.connect(self.db_location)

        with conn:
            tables = conn.execute(f"SELECT table_name FROM tables WHERE table_name != '{self.main_tab}';")

        for table_name, *_ in tables:
            # NOTE: remove leading and trailing quotes
            self.create_tab(table_name[1:-1])

    def add_to_new(self, name: str, uri: str):
        from creator.utils.sqlitemodel import SQLliteModel

        # NOTE: only thing not allowed is quotes
        name = name.strip().replace('"', "").replace("'", "")

        # No funny business
        if name == "" or name == self.main_tab:
            return

        conn = sql.connect(self.db_location)

        selected_rows = [str(r.row()) for r in self.main_table.selectionModel().selectedRows()]

        if len(selected_rows) == 0:
            return

        selected_rows_str = ", ".join(selected_rows)

        with conn:
            # TODO: get definition from importsjabloon
            # Create table
            conn.execute(f"""
            CREATE TABLE IF NOT EXISTS "{name}" (
                id INTEGER PRIMARY KEY,

                main_id INTEGER NOT NULL,

                path_in_sip TEXT,
                type TEXT,
                dossierref TEXT,
                analoog TEXT,
                naam TEXT,
                beschrijving TEXT,
                dossiercode_bron TEXT,
                stukreferentie_bron TEXT,
                openingsdatum TEXT,
                sluitingsdatum TEXT,
                id_bis_registernummer TEXT,
                id_rijksregisternummer TEXT,
                id_naam TEXT,
                kbo_nummer TEXT,
                ovo_code TEXT,
                organisatienaam TEXT,
                trefwoorden_vrij TEXT,
                opmerkingen TEXT,
                auteur TEXT,
                taal TEXT,
                openbaarheidsregime TEXT,
                openbaarheidsmotivering TEXT,
                hergebruikregime TEXT,
                hergebruikmotivering TEXT,
                creatiedatum TEXT,
                origineel_doosnummer TEXT,
                legacy_locatie_id TEXT,
                legacy_range TEXT,
                verpakkingstype TEXT
            );""")

            # Update the tables table
            conn.execute(f"""
                INSERT OR IGNORE INTO tables (table_name, uri_serieregister)
                VALUES ('"{name}"', '{uri}');
            """)

            # Remove where needed
            cursor = conn.execute(f"""
                SELECT id, series_name
                FROM {self.main_tab}
                WHERE id IN ({selected_rows_str})
                  AND series_name != '"{name}"'
                  AND series_name != '';
            """)

            for main_id, table in cursor.fetchall():
                # NOTE: table already contains ""-marks
                tab = table[1:-1]

                conn.execute(f"""
                    DELETE FROM {table}
                    WHERE main_id={main_id};
                """)

                rows = conn.execute(f"""
                    SELECT count() FROM {table};
                """).fetchone()[0]

                if rows == 0:
                    conn.execute(f"""
                        DROP TABLE {table};
                    """)
                    
                    conn.execute(f"""
                        DELETE FROM tables
                        WHERE table_name='{table}';
                    """)

                    self.tab_widget.removeTab(list(self.tabs).index(tab))
                    del self.tabs[tab]
                    
                    continue

                # Recalculate shape for table
                model: SQLliteModel = self.tabs[tab].model()
                model.row_count = rows

                # Update the graphical side
                model.layoutChanged.emit()

            # Insert where needed
            # NOTE: don't do other auto-mapping
            conn.execute(f"""
                INSERT INTO "{name}" (main_id) --, beschrijving, openingsdatum, sluitingsdatum)
                SELECT id --, beschrijving, begin_datum, eind_datum
                FROM {self.main_tab}
                WHERE id IN ({selected_rows_str})
                  AND (series_name != '"{name}"' OR series_name IS NULL OR series_name == '');
            """)
            
            # Update the main table to show correct linking
            conn.execute(f"""
                UPDATE {self.main_tab}
                SET series_name='"{name}"',
                    uri_serieregister='{uri}'
                WHERE id IN ({selected_rows_str});
            """)

            conn.commit()

        # Update the graphical side
        model: SQLliteModel = self.main_table.model()
        
        model.get_data()
        model.layoutChanged.emit()
        
        # If the tab already exists, stop here
        if name in self.tabs:
            model: SQLliteModel = self.tabs[name].model()
            
            model.get_data()
            model.layoutChanged.emit()
            return

        self.create_tab(name)

    def create_tab(self, name: str):
        from creator.widgets.tableview_widget import TableView

        container = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        container.setLayout(layout)

        series_label = QtWidgets.QLabel(text=name)
        table_view = TableView()

        layout.addWidget(series_label, 0, 0)
        layout.addWidget(table_view, 1, 0)

        from creator.utils.sqlitemodel import SQLliteModel

        model = SQLliteModel(name, db_name=self.db_location)
        table_view.setModel(model)

        self.tab_widget.addTab(container, name)
        self.tabs[name] = table_view

    def closeEvent(self, event):
        from creator.utils.sqlitemodel import SQLliteModel

        models: list[SQLliteModel] = [t.model() for t in self.tabs.values()]

        # NOTE: only ask the user if data has actually changed
        if not any(m.has_changed for m in models):
            event.accept()
            return

        dialog = YesNoDialog(
            title="Overdrachtslijst sluiten",
            text="Wil je de huidige data opslaan?\nZonder opslaan gaat de nieuwe data verloren bij heropstarten van de applicatie."
        )
        dialog.exec()

        if dialog.result():
            self.save_tabs()

        event.accept()

    def save_tabs(self) -> None:
        from creator.utils.sqlitemodel import SQLliteModel

        for table_view in self.tabs.values():
            if table_view == self.main_table:
                continue

            model: SQLliteModel = table_view.model()

            model.save_data()
            model.has_changed = False

    def _filter_unassigned(self, state: QtCore.Qt.CheckState) -> None:
        from creator.utils.sqlitemodel import SQLliteModel

        model: SQLliteModel = self.main_table.model()
        data: list[list[str]] = model.get_data()

        if state == QtCore.Qt.CheckState.Checked.value:
            columns = model.columns
            series_col = list(columns.values()).index("series_name")

            for row_index, row in enumerate(data):
                if row[series_col] != "":
                    self.main_table.setRowHidden(row_index, True)

            return
        
        for row_index in range(len(data)):
            self.main_table.setRowHidden(row_index, False)

class ListView(QtWidgets.QWidget):
    def __init__(self, tab_ui: TabUI):
        super().__init__()

        self.name = tab_ui.name
        self.tab_ui = tab_ui

        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)

        title = QtWidgets.QLabel(text=self.name)

        open_button = QtWidgets.QPushButton(text="Open")
        open_button.clicked.connect(self.tab_ui.show)

        layout.addWidget(title, 0, 0, 1, 2)
        layout.addWidget(open_button, 0, 2)

def set_main(application: Application, main: MainWindow) -> None:
    config = application.state.configuration

    # TODO: use role
    active_role, active_type = config.active_role, config.active_type

    print(active_type)

    if active_type == "digitaal":
        main.central_widget = DigitalWidget(main)
        main.setWindowTitle("SIP Creator digitaal")
    else:
        main.central_widget = MigrationWidget(main)
        main.setWindowTitle("SIP Creator migratie")

    main.setCentralWidget(None)
    main.setCentralWidget(main.central_widget)
    main.central_widget.setup_ui()
    main.central_widget.load_items()


