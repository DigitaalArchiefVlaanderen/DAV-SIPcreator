import os
import json

from PySide6 import QtWidgets, QtGui
import pandas as pd
import sqlite3 as sql

from creator.application import Application

from creator.widgets.main_widgets.main_widget import MainWidget
from creator.widgets.searchable_list_widget import SearchableListWidget
from creator.widgets.warning_dialog import WarningDialog

from creator.controllers.api_controller import APIController

from creator.windows.mainwindow import MainWindow
from creator.windows.analoog.grid_creation_view import GridCreationView as AnaloogGridCreationView
from creator.widgets.list_item_widget import ListItemWidget as AnaloogListItemWidget
from creator.windows.analoog.analoog_grid_view import AnaloogGridView

from creator.utils.analoog.list_item import ListItem as AnaloogListItem
from creator.utils.analoog.grid import Grid as AnaloogGrid
from creator.utils.series import Series
from creator.utils.state import State


class AnaloogWidget(MainWidget):
    def __init__(self, parent: MainWindow):
        super().__init__(parent)

        self.application: Application = QtWidgets.QApplication.instance()
        self.state: State = self.application.state

        self._layout = QtWidgets.QGridLayout()
        self.list_view = SearchableListWidget()
    
    def setup_ui(self):
        self.setLayout(self._layout)

        # MAIN UI
        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(20)

        title = QtWidgets.QLabel(text="Analoog")
        title.setFont(font)

        start_sip_button = QtWidgets.QPushButton(text="Start SIP")
        start_sip_button.clicked.connect(self.start_sip_clicked)

        file_location_button = QtWidgets.QPushButton(text="Bestandslocatie")
        file_location_button.clicked.connect(lambda: os.startfile(self.state.configuration.sips_location))

        self._layout.addWidget(title, 0, 0)
        self._layout.addWidget(start_sip_button, 1, 0)
        self._layout.addWidget(file_location_button, 1, 3)
        self._layout.addWidget(self.list_view, 2, 0, 1, 4)

    def load_items(self) -> None:
        """
            Load all the existing dbs into the list view
        """
        def _read_db_data(path: str) -> tuple[Series, str, bool, list[str], list[list[str]]]:
            with sql.connect(path) as conn:
                series_json, edepot_id, data_changed_since_last_upload = conn.execute("""
                    SELECT *
                    FROM extra;
                """).fetchone()
                columns_result = conn.execute("PRAGMA table_info(data);").fetchall()
                data_result = conn.execute("SELECT * FROM data;").fetchall()

                series = Series.from_dict(json.loads(series_json))
                data_changed_since_last_upload = bool(data_changed_since_last_upload)
                columns = [column_name.strip('"') for _, column_name, *_ in columns_result]
                data = [list(r) for r in data_result]

            return series, edepot_id, data_changed_since_last_upload, columns, data

        os.makedirs(self.state.configuration.analoog_location, exist_ok=True)

        for file in os.listdir(self.state.configuration.analoog_location):
            # 0: we only care about databases
            if not file.endswith(".db"):
                continue

            db_path = os.path.join(self.state.configuration.analoog_location, file)

            # 1: Load data
            series, edepot_id, data_changed_since_last_upload, columns, data = _read_db_data(db_path)

            # 2: Create widget
            list_item = AnaloogListItem(
                source_path=db_path,
                name=file[:-3],
                edepot_id=edepot_id,
                data_changed_since_last_upload=data_changed_since_last_upload,
                grid=AnaloogGrid(
                    series=series,
                    columns=columns,
                    data=data
                )
            )
            list_item_widget = AnaloogListItemWidget(list_item=list_item)

            # 3: Add it to the list_view
            self.list_view.add_item("name", list_item_widget)

    def start_sip_clicked(self) -> None:
        def _open_creation_view() -> None:
            grid_creation_view = AnaloogGridCreationView()
            grid_creation_view.open_grid_clicked.connect(lambda: _open_grid_clicked(grid_creation_view))
            grid_creation_view.show()

        def _open_grid_clicked(grid_creation_view: AnaloogGridCreationView) -> None:
            # 0: Download import template
            import_template_location = APIController.get_import_template(
                configuration=self.state.configuration,
                series_id=grid_creation_view.selected_series._id
            )

            # 1: Read columns
            columns = pd.read_excel(import_template_location, dtype=str, engine="openpyxl").columns.to_list()
            columns.insert(0, "_id")
            data = [[""] * len(columns)]
            data[0][0] = 0

            # 2: Create db
            db_name = f"{grid_creation_view.entered_sip_name}.db"
            db_path = os.path.join(self.state.configuration.analoog_location, db_name)
            
            if os.path.exists(db_path):
                # NOTE: this can only happen by user error
                WarningDialog(
                    title="Database bestaat al",
                    text="Database met deze naam bestaat al, kies een andere naam"
                ).exec()
                return

            list_item = AnaloogListItem(
                source_path=db_path,
                name=db_name[:-3],
                edepot_id="",
                grid=AnaloogGrid(
                    series=grid_creation_view.selected_series,
                    columns=columns,
                    data=data
                )
            )

            with sql.connect(db_path) as conn:  
                conn.execute(f"""
                    CREATE TABLE data (
                        _id INTEGER PRIMARY KEY,
                        
                        {',\n'.join(f'"{c}" TEXT' for c in list_item.grid.columns if c != "_id")}
                    );
                """)
                conn.executemany(f"INSERT INTO data VALUES ({'?,' * (len(list_item.grid.columns) - 1)}?)", data)

                conn.execute("""
                    CREATE TABLE extra (
                        series_json TEXT,
                        edepot_id TEXT,
                        data_changed_since_last_upload INTEGER
                    );
                """)
                conn.execute(f"INSERT INTO extra VALUES (?, ?, ?)", [json.dumps(list_item.grid.series.to_dict()), "", 1])

            # 3: Create list item widget
            list_item_widget = AnaloogListItemWidget(list_item=list_item)

            # 4: Add list item to list view
            self.list_view.add_item("name", list_item_widget)

            # 5: Close the creation view and open the grid view
            grid_creation_view.close()

            list_item_widget.open_button_clicked()
        
        self.state.check_series_loaded()

        _open_creation_view()
