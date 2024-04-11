from PySide6 import QtWidgets, QtCore
import pandas as pd
import numpy as np

from datetime import datetime
import os

from ..application import Application
from ..controllers.file_controller import FileController
from ..utils.sip_status import SIPStatus
from ..utils.pandasmodel import PandasModel, Color
from ..widgets.toolbar import Toolbar
from ..widgets.warning_dialog import WarningDialog
from ..widgets.dialog import Dialog
from ..widgets.tableview_widget import TableView


class GridView(QtWidgets.QMainWindow):
    def __init__(self, sip_widget):
        super().__init__()

        self.sip_widget = sip_widget

        self.application: Application = QtWidgets.QApplication.instance()

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
        grid_layout.addWidget(series_label, 0, 0, 1, 4)

        self.name_extension_checkbox = QtWidgets.QCheckBox(
            text="Verwijder file-extensie uit 'Naam' kolom"
        )
        self.name_extension_checkbox.setChecked(False)
        grid_layout.addWidget(self.name_extension_checkbox, 1, 0)

        self.show_bad_rows_checkbox = QtWidgets.QCheckBox(
            text="Toon enkel rijen met fouten"
        )
        self.show_bad_rows_checkbox.setChecked(False)
        self.show_bad_rows_checkbox.stateChanged.connect(self._bad_rows_clicked)
        grid_layout.addWidget(self.show_bad_rows_checkbox, 1, 1)

        self.table_view = TableView()
        grid_layout.addWidget(self.table_view, 2, 0, 1, 4)

        save_button = QtWidgets.QPushButton(text="Opslaan")
        save_button.clicked.connect(self.save_button_click)
        grid_layout.addWidget(save_button, 3, 0, 1, 2)

        self.create_sip_button = QtWidgets.QPushButton(text="Maak SIP")
        self.create_sip_button.clicked.connect(self.create_sip_click)
        self.create_sip_button.setEnabled(False)
        grid_layout.addWidget(self.create_sip_button, 3, 2, 1, 2)

    # Grid filters
    def _set_grid_filter_connections(self) -> None:
        model: PandasModel = self.table_view.model()

        self.name_extension_checkbox.stateChanged.connect(
            lambda state: model.filter_name_column(
                active=state == QtCore.Qt.CheckState.Checked.value
            )
        )

    def _bad_rows_clicked(self, state: QtCore.Qt.CheckState) -> None:
        model: PandasModel = self.table_view.model()
        data: pd.DataFrame = model.get_data()
        active = state == QtCore.Qt.CheckState.Checked.value

        if active:
            model.bad_rows_changed.connect(
                lambda row, is_bad: self.table_view.setRowHidden(row, not is_bad)
            )
        else:
            model.bad_rows_changed.disconnect()

        bad_rows = model.get_bad_rows()
        hide_row = active

        for row in range(model.rowCount()):
            data_row = data.index[row]

            if data_row not in bad_rows:
                self.table_view.setRowHidden(row, hide_row)

    def _rows_sorted(self) -> None:
        # If we sort, we need to reassess what to hide, so redo it
        if self.show_bad_rows_checkbox.isChecked():
            model = self.table_view.model()
            model.bad_rows_changed.disconnect()

            for row in range(model.rowCount()):
                self.table_view.setRowHidden(row, False)

            self._bad_rows_clicked(QtCore.Qt.CheckState.Checked.value)

    # Loading grid
    def _fill_from_files(self, sip_folder_structure: dict):
        df = pd.DataFrame(columns=self.sip_widget.import_template_df.columns)

        df["Path in SIP"] = [s["Path in SIP"] for s in sip_folder_structure.values()]
        df["Type"] = [s["Type"] for s in sip_folder_structure.values()]
        df["DossierRef"] = [s["DossierRef"] for s in sip_folder_structure.values()]

        df["Openingsdatum"] = [
            s["Openingsdatum"] for s in sip_folder_structure.values()
        ]
        df["Sluitingsdatum"] = [
            s["Sluitingsdatum"] for s in sip_folder_structure.values()
        ]

        open_dates_df = df.loc[df.Type == "dossier"][["DossierRef"]].join(
            df.loc[df.Type == "stuk"]
            .groupby(by="DossierRef")
            .Openingsdatum.min()
            .apply(lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d")),
            on="DossierRef",
            rsuffix="_r",
        )

        close_dates_df = df.loc[df.Type == "dossier"][["DossierRef"]].join(
            df.loc[df.Type == "stuk"]
            .groupby(by="DossierRef")
            .Sluitingsdatum.max()
            .apply(lambda t: datetime.fromtimestamp(t).strftime("%Y-%m-%d")),
            on="DossierRef",
            rsuffix="_r",
        )

        # Reset the columns
        df.Openingsdatum = None
        df.Sluitingsdatum = None

        df.loc[df.Type == "dossier", "Openingsdatum"] = open_dates_df.Openingsdatum
        df.loc[df.Type == "dossier", "Sluitingsdatum"] = close_dates_df.Sluitingsdatum

        self.sip_widget.import_template_df = df

    def _fill_mapping(self, sip_folder_structure: dict):
        # NOTE: this whole method is a jumble, have fun figuring it all out in it's current state
        name_mapping_from = [
            k for k, v in self.sip_widget.sip.tag_mapping.items() if v == "Naam"
        ][0]
        mapping_from_cols = self.sip_widget.sip.tag_mapping.keys()
        mapping_to_cols = self.sip_widget.sip.tag_mapping.values()

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
        temp_df.rename(columns=self.sip_widget.sip.tag_mapping, inplace=True)

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

    def load_table(self):
        sip_folder_structure = self.sip_widget.sip.get_sip_folder_structure()

        self.table_view.setModel(
            PandasModel(
                self.sip_widget.import_template_df,
                self.create_sip_button,
                (
                    self.sip_widget.sip.series.valid_from,
                    self.sip_widget.sip.series.valid_to,
                ),
                sip_folder_structure=sip_folder_structure,
            )
        )
        self.table_view.model().sort_triggered.connect(self._rows_sorted)
        self._set_grid_filter_connections()

    def fill_table(self):
        sip_folder_structure = self.sip_widget.sip.get_sip_folder_structure()

        self._fill_from_files(sip_folder_structure)

        if self.sip_widget.sip.tag_mapping:
            self._fill_mapping(sip_folder_structure)

        self.table_view.setModel(
            PandasModel(
                self.sip_widget.import_template_df,
                self.create_sip_button,
                (
                    self.sip_widget.sip.series.valid_from,
                    self.sip_widget.sip.series.valid_to,
                ),
                sip_folder_structure=sip_folder_structure,
            )
        )
        self.table_view.model().sort_triggered.connect(self._rows_sorted)
        self._set_grid_filter_connections()

    # Actions
    def create_sip_click(self):
        self.save_button_click(filter_save=True)
        table = self.table_view.model()
        df = table.get_data()

        # Filter out bad rows
        if len(df.loc[df["Type"] != "geen"]) > 9999:
            WarningDialog(
                title="Te veel data",
                text="De metadata mag maximaal 9999 rijen data bevatten",
            ).exec()
            return

        try:
            FileController.create_sip(
                configuration=self.application.state.configuration,
                sip=self.sip_widget.sip,
            )
        except FileNotFoundError:
            WarningDialog(
                title="Bestand verplaatst",
                text="Een of meerdere bestanden die in de SIP moeten komen zijn verplaatst, kan niet verder gaan.",
            ).exec()
            return

        self.sip_widget.sip.set_status(SIPStatus.SIP_CREATED)
        self.sip_widget.sip_name_label.setEnabled(False)

        self.close()

    def save_button_click(self, filter_save=False):
        # Filter_save means we are applying all the filters to the actual save
        try:
            df = self.table_view.model().get_data()

            if filter_save:
                # Bad rows filter
                df = df.loc[df["Type"] != "geen"]
                df.sort_values(df.columns[0], ascending=True)
                df.reset_index(drop=True, inplace=True)

                # Naam column filter
                if self.table_view.model().filter_name_column:
                    df["Naam"] = df["Naam"].map(lambda n: n.rsplit(".", 1)[0])

            FileController.save_grid(
                configuration=self.application.state.configuration,
                df=df,
                sip_widget=self.sip_widget,
            )

            if not filter_save:
                Dialog(
                    title="Opgeslagen", text="De metadata is succesvol opgeslagen."
                ).exec()
        except PermissionError:
            WarningDialog(
                title="Ongeldige rechten",
                text="Ongeldige rechten om het bestand op te slaan, zorg er zeker voor dat je de excel niet open hebt staan en probeer opnieuw.",
            ).exec()
        except Exception:
            WarningDialog(
                title="Ongekende fout",
                text="Ongekende fout is opgetreden tijdens het opslaan.",
            ).exec()

    def closeEvent(self, event):
        if (
            FileController.existing_grid_path(
                self.application.state.configuration, self.sip_widget.sip
            )
            is None
        ):
            self.save_button_click()
        event.accept()
