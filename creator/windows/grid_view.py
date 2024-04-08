from PySide6 import QtWidgets, QtCore
import pandas as pd
import numpy as np

from datetime import datetime
import os


from ..controllers.file_controller import FileController
from ..utils.sip_status import SIPStatus
from ..utils.pandasmodel import PandasModel, Color
from ..widgets.toolbar import Toolbar
from ..widgets.warning_dialog import WarningDialog
from ..widgets.tableview_widget import TableView


class GridView(QtWidgets.QMainWindow):
    def __init__(self, sip_widget):
        super().__init__()

        self.sip_widget = sip_widget

        self.application = QtWidgets.QApplication.instance()

    def setup_ui(self):
        self.resize(800, 600)
        self.setWindowTitle(self.sip_widget.sip.name)
        self.toolbar = Toolbar()
        self.addToolBar(self.toolbar)

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        grid_layout = QtWidgets.QGridLayout()
        central_widget.setLayout(grid_layout)

        series_label = QtWidgets.QLabel(text=self.sip_widget.sip.series.get_name())
        grid_layout.addWidget(series_label, 0, 0, 1, 2)

        self.table_view = TableView()
        grid_layout.addWidget(self.table_view, 1, 0, 1, 2)

        save_button = QtWidgets.QPushButton(text="Opslaan")
        save_button.clicked.connect(self.save_button_click)
        grid_layout.addWidget(save_button, 2, 0)

        self.create_sip_button = QtWidgets.QPushButton(text="Maak SIP")
        self.create_sip_button.clicked.connect(self.create_sip_click)
        self.create_sip_button.setEnabled(False)
        grid_layout.addWidget(self.create_sip_button, 2, 1)

    def _fill_from_files(self, sip_folder_structure: dict):
        df = pd.DataFrame(columns=self.sip_widget.import_template_df.columns)

        df["Path in SIP"] = [s["Path in SIP"] for s in sip_folder_structure.values()]
        df["Type"] = [s["Type"] for s in sip_folder_structure.values()]
        df["DossierRef"] = [s["DossierRef"] for s in sip_folder_structure.values()]

        self.sip_widget.import_template_df = df

    def _fill_mapping(self, sip_folder_structure: dict):
        # NOTE: this whole method is a jumble, have fun figuring it all out in it's current state
        name_mapping_from = [
            k for k, v in self.sip_widget.sip.mapping.items() if v == "Naam"
        ][0]
        mapping_from_cols = self.sip_widget.sip.mapping.keys()
        mapping_to_cols = self.sip_widget.sip.mapping.values()

        temp_df = self.sip_widget.metadata_df.copy(deep=True)

        # Select only the columns we care about
        temp_df = temp_df[temp_df.columns.intersection(mapping_from_cols)]

        # Add the Path in SIP
        temp_df["Path in SIP"] = temp_df[name_mapping_from]
        temp_df.replace(
            {
                "Path in SIP": {
                    name_from: value["Path in SIP"]
                    for name_from, value in sip_folder_structure.items()
                }
            },
            inplace=True,
        )

        # Change all the from-cols to the to-cols
        temp_df.rename(columns=self.sip_widget.sip.mapping, inplace=True)

        temp_df = pd.merge(
            self.sip_widget.import_template_df,
            temp_df,
            on="Path in SIP",
            suffixes=("_1", "_2"),
            how="left",
        )

        # NOTE: we do this to preserve the positioning of the columns
        for col in mapping_to_cols:
            temp_df[f"{col}_1"] = temp_df[f"{col}_2"]

        required_columns = [
            c if c not in mapping_to_cols else f"{c}_1"
            for c in self.sip_widget.import_template_df.columns
        ]
        temp_df = temp_df[temp_df.columns.intersection(required_columns)]

        temp_df.rename(columns={f"{v}_1": v for v in mapping_to_cols}, inplace=True)

        self.sip_widget.import_template_df = temp_df

    def _set_invalid_rows(self):
        table = self.table_view.model()

        for index in table.get_invalid_name_rows().index:
            # Column 4 is "Naam"
            table.colors[(index, 4)] = Color.RED

        for index in table.get_invalid_opening_date_rows().index:
            # Column 8 is "Openingsdatum"
            table.colors[(index, 8)] = Color.RED

        for index in table.get_invalid_closing_date_rows().index:
            # Column 9 is "Sluitingsdatum"
            table.colors[(index, 9)] = Color.RED

    def load_table(self):
        self.table_view.setModel(
            PandasModel(
                self.sip_widget.import_template_df,
                self.create_sip_button,
                (
                    self.sip_widget.sip.series.valid_from,
                    self.sip_widget.sip.series.valid_to,
                ),
            )
        )

        self._set_invalid_rows()

    def fill_table(self):
        sip_folder_structure = self.sip_widget.sip.get_sip_folder_structure()

        self._fill_from_files(sip_folder_structure)

        if self.sip_widget.sip.mapping:
            self._fill_mapping(sip_folder_structure)

        self.table_view.setModel(
            PandasModel(
                self.sip_widget.import_template_df,
                self.create_sip_button,
                (
                    self.sip_widget.sip.series.valid_from,
                    self.sip_widget.sip.series.valid_to,
                ),
            )
        )

        self._set_invalid_rows()

    def create_sip_click(self):
        self.save_button_click()
        table = self.table_view.model()
        df = table.get_data()

        if len(df) > 9999:
            WarningDialog(
                title="Te veel data",
                text="De metadata mag maximaal 9999 rijen data bevatten",
            ).exec()
            return

        FileController.create_sip(
            configuration=self.application.state.configuration,
            df=df,
            sip_widget=self.sip_widget,
        )

        self.sip_widget.sip.status = SIPStatus.SIP_CREATED
        self.sip_widget.sip_status_label.setText(
            self.sip_widget.sip.status.get_status_label()
        )
        self.sip_widget.sip_status_label.setStyleSheet(self.sip_widget.sip.status.value)
        self.sip_widget.upload_button.setEnabled(True)
        self.sip_widget.open_button.setEnabled(False)
        self.sip_widget.sip_name_label.setEnabled(False)

        self.application.state.update_sip(self.sip_widget.sip)

        self.close()

    def save_button_click(self):
        try:
            FileController.save_grid(
                configuration=self.application.state.configuration,
                df=self.table_view.model().get_data(),
                sip_widget=self.sip_widget,
            )
        except PermissionError:
            WarningDialog(
                title="Ongeldige rechten",
                text="Ongeldige rechten om het bestand op te slaan, zorg er zeker voor dat je de excel niet open hebt staan en probeer opnieuw.",
            )

    def closeEvent(self, event):
        if FileController.existing_grid_path(self.application.state.configuration, self.sip_widget.sip) is None:
            self.save_button_click()
        event.accept()
