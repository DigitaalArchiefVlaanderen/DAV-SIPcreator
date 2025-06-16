from PySide6 import QtWidgets, QtCore, QtGui
import pandas as pd

import os
from datetime import datetime

from creator.application import Application

from creator.controllers.file_controller import FileController
from creator.controllers.db_controller import SIPDBController, NotASIPDBException

from creator.utils.sip_status import SIPStatus
from creator.utils.state_utils.sip import SIP
from creator.utils.pandasmodel import PandasModel
from creator.utils.proxymodel import CustomSortFilterModel
from creator.utils.path_loader import resource_path

from creator.widgets.toolbar import Toolbar
from creator.widgets.warning_dialog import WarningDialog
from creator.widgets.dialog import YesNoDialog
from creator.widgets.dialog import Dialog
from creator.widgets.tableview_widget import TableView


class GridView(QtWidgets.QMainWindow):
    def __init__(self, sip_widget):
        super().__init__()

        self.sip_widget = sip_widget
        self.sip: SIP = sip_widget.sip

        self.application: Application = QtWidgets.QApplication.instance()
        self.state = self.application.state

        self.intentional_close = False

    def setup_ui(self):
        self.resize(800, 600)
        self.setWindowTitle(self.sip.name)
        self.toolbar = Toolbar()
        self.addToolBar(self.toolbar)

        self.setWindowIcon(QtGui.QIcon(resource_path("logo.ico")))

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)

        grid_layout = QtWidgets.QGridLayout()
        central_widget.setLayout(grid_layout)

        series_label = QtWidgets.QLabel(text=self.sip.series.get_name())
        self.default_sorting_button = QtWidgets.QPushButton(text="Reset sortering")
        grid_layout.addWidget(series_label, 0, 0, 1, 4)
        grid_layout.addWidget(self.default_sorting_button, 0, 4, 1, 1)

        self.name_extension_checkbox = QtWidgets.QCheckBox(
            text="Verwijder file-extensie uit 'Naam' kolom"
        )
        self.name_extension_checkbox.setChecked(False)
        grid_layout.addWidget(self.name_extension_checkbox, 1, 0)

        self.show_bad_rows_checkbox = QtWidgets.QCheckBox(
            text="Toon enkel rijen met fouten"
        )
        self.show_bad_rows_checkbox.stateChanged.connect(self._bad_rows_clicked)
        grid_layout.addWidget(self.show_bad_rows_checkbox, 1, 1)

        self.show_dossiers_only_checkbox = QtWidgets.QCheckBox(
            text="Toon enkel dossiers"
        )
        self.show_dossiers_only_checkbox.stateChanged.connect(self._dossiers_only_clicked)
        grid_layout.addWidget(self.show_dossiers_only_checkbox, 1, 2)

        # NOTE: will be filled once we know the columns we have
        self.column_dropdown = QtWidgets.QComboBox()
        self.add_column_button = QtWidgets.QPushButton(text="Voeg kolom toe")
        self.add_column_button.clicked.connect(self.add_column_button_clicked)
        grid_layout.addWidget(self.column_dropdown, 1, 3)
        grid_layout.addWidget(self.add_column_button, 1, 4)

        self.table_view = TableView()
        grid_layout.addWidget(self.table_view, 2, 0, 1, 5)

        save_button = QtWidgets.QPushButton(text="Opslaan")
        save_button.clicked.connect(self.save_button_click)
        grid_layout.addWidget(save_button, 3, 0, 1, 2)

        self.create_sip_button = QtWidgets.QPushButton(text="Maak SIP")
        self.create_sip_button.clicked.connect(self.create_sip_click)
        self.create_sip_button.setEnabled(False)
        grid_layout.addWidget(self.create_sip_button, 3, 2, 1, 3)

    # Grid filters
    def _set_grid_filter_connections(self) -> None:
        model: PandasModel = self.table_view.model()

        self.name_extension_checkbox.stateChanged.connect(
            lambda state: model.filter_name_column(
                active=state == QtCore.Qt.CheckState.Checked.value
            )
        )

    def _bad_rows_clicked(self, state: QtCore.Qt.CheckState) -> None:
        model: CustomSortFilterModel = self.table_view.model(proxy=True)

        if state == QtCore.Qt.CheckState.Checked.value:
            model.add_filter(CustomSortFilterModel.BAD_ROWS_FILTER)
        else:
            model.remove_filter(CustomSortFilterModel.BAD_ROWS_FILTER)

    def _dossiers_only_clicked(self, state: QtCore.Qt.CheckState) -> None:
        model: CustomSortFilterModel = self.table_view.model(proxy=True)

        if state == QtCore.Qt.CheckState.Checked.value:
            model.add_filter(CustomSortFilterModel.SHOW_DOSSIERS_FILTER)
        else:
            model.remove_filter(CustomSortFilterModel.SHOW_DOSSIERS_FILTER)

    # Loading grid
    def _fill_from_files(self, sip_folder_structure: dict):
        df = pd.DataFrame(columns=self.sip_widget.import_template_df.columns)

        df["Path in SIP"] = [s["Path in SIP"] for s in sip_folder_structure.values()]
        df["Type"] = [s["Type"] for s in sip_folder_structure.values()]
        df["DossierRef"] = [s["DossierRef"] for s in sip_folder_structure.values()]
        df["Naam"] = [s["Naam"] for s in sip_folder_structure.values()]

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
        mapping_from_cols = self.sip.tag_mapping.keys()
        mapping_to_cols = self.sip.tag_mapping.values()

        temp_df = self.sip_widget.metadata_df.copy(deep=True)

        # NOTE: make sure the Path in SIP reflects the actual value (from folder_mapping)
        temp_df["Path in SIP"] = temp_df["Path in SIP"].replace({v["original Path in SIP"]: k for k, v in sip_folder_structure.items()})

        # Select only the columns we care about
        temp_df = temp_df[temp_df.columns.intersection(mapping_from_cols)]

        # Change all the from-cols to the to-cols
        # temp_df.rename(columns={**self.sip.tag_mapping, **{"_Path in SIP": "Path in SIP"}}, inplace=True)
        temp_df.rename(columns=self.sip.tag_mapping, inplace=True)

        temp_df = pd.merge(
            self.sip_widget.import_template_df,
            temp_df,
            on="Path in SIP",
            suffixes=("_1", "_2"),
            how="left",
        )

        # NOTE: we do this to preserve the positioning of the columns
        for col in mapping_to_cols:
            if col != "Path in SIP":
                temp_df[f"{col}_1"] = temp_df[f"{col}_2"]

        required_columns = ["Path in SIP"] + [
            c if c not in mapping_to_cols else f"{c}_1"
            for c in self.sip_widget.import_template_df.columns
            if c != "Path in SIP"
        ]
        temp_df = temp_df[temp_df.columns.intersection(required_columns)]

        temp_df.rename(columns={f"{v}_1": v for v in mapping_to_cols if v != "Path in SIP"}, inplace=True)

        self.sip_widget.import_template_df = temp_df

    def load_table(self) -> pd.DataFrame:
        sip_folder_structure = self.sip.get_sip_folder_structure()

        model = PandasModel(
            self.sip_widget.import_template_df,
            self.create_sip_button,
            (
                self.sip.series.valid_from,
                self.sip.series.valid_to,
            ),
            sip_folder_structure=sip_folder_structure,
        )

        proxy_model = CustomSortFilterModel()
        proxy_model.setSourceModel(model)
        self.table_view.setModel(proxy_model)
        self.default_sorting_button.clicked.connect(proxy_model.reset_sorting)
        self._set_grid_filter_connections()

        if model.is_data_valid():
            self.create_sip_button.setEnabled(True)
        else:
            self.create_sip_button.setEnabled(False)

        unique_columns = set(m for m in model.get_data().columns)
        filtered_columns = [
            c for c in unique_columns
            if c not in (
                "Path in SIP",
                "Type",
                "DossierRef",
                "Analoog?",
                "Naam",
                "Openingsdatum",
                "Sluitingsdatum",
            )
        ]

        for column in filtered_columns:
            self.column_dropdown.addItem(column)

        return model.get_data()

    def fill_table(self) -> pd.DataFrame:
        sip_folder_structure = self.sip.get_sip_folder_structure()

        self._fill_from_files(sip_folder_structure)

        if self.sip.tag_mapping:
            self._fill_mapping(sip_folder_structure)

        model = PandasModel(
            self.sip_widget.import_template_df,
            self.create_sip_button,
            (
                self.sip.series.valid_from,
                self.sip.series.valid_to,
            ),
            sip_folder_structure=sip_folder_structure,
        )

        proxy_model = CustomSortFilterModel()
        proxy_model.setSourceModel(model)
        self.table_view.setModel(proxy_model)
        self.default_sorting_button.clicked.connect(proxy_model.reset_sorting)
        self._set_grid_filter_connections()

        if model.is_data_valid():
            self.create_sip_button.setEnabled(True)
        else:
            self.create_sip_button.setEnabled(False)

        unique_columns = set(m for m in model.get_data().columns)
        filtered_columns = [
            c for c in unique_columns
            if c not in (
                "Path in SIP",
                "Type",
                "DossierRef",
                "Analoog?",
                "Naam",
                "Openingsdatum",
                "Sluitingsdatum",
            )
        ]

        for column in filtered_columns:
            self.column_dropdown.addItem(column)

        return model.get_data()

    # Actions
    def add_column_button_clicked(self) -> None:
        column = self.column_dropdown.currentText()

        model: PandasModel = self.table_view.model()
        df = model.get_data()

        model.modelAboutToBeReset.emit()

        new_column_name = column
        spaces_added = 1

        # NOTE: keep adding spaces until it is new
        while (new_column_name := f"{new_column_name} ") in df.columns:
            spaces_added += 1

        df.insert(df.columns.get_loc(column) + spaces_added, new_column_name, None)

        # NOTE: rerun all checks (not super efficient, would be better to just do it for this row, but oh well)
        model._trigger_fill_data()
        model.modelReset.emit()

    def create_sip_click(self):
        df = self.save_button_click(filter_save=True)

        if df is None:
            return

        FileController.create_sip(
            configuration=self.application.state.configuration,
            sip=self.sip,
            df=df,
            unfiltered_df=self.table_view.model().get_data()
        )

        self.sip.set_status(SIPStatus.SIP_CREATED)

        Dialog(
            title="SIP aangemaakt",
            text="De SIP is aangemaakt"
        ).exec()

        self.intentional_close = True
        self.close()

    def save_button_click(self, filter_save=False) -> pd.DataFrame:
        # Filter_save means we are applying all the filters to the actual save
        try:
            df = self.table_view.model().get_data().copy(deep=True)

            if filter_save:
                # Bad rows filter
                df = df.loc[df["Type"] != "geen"]
                df.sort_values(df.columns[0], ascending=True)
                df.reset_index(drop=True, inplace=True)

                # Naam column filter
                if self.table_view.model().filter_name_column:
                    df["Naam"] = df["Naam"].map(lambda n: n.rsplit(".", 1)[0])

            db_path = os.path.join(self.state.configuration.sip_db_location, f"{self.sip.name}.db")
            db_controller = SIPDBController(db_path)

            if not db_controller.is_valid_db():
                raise NotASIPDBException(f"Database laden is gefaald.\nDe database op locatie '{db_path}' is geen SIP database of is corrupt.")
            
            db_controller.update_data_table(df=df)

            if not filter_save:
                Dialog(
                    title="Opgeslagen", text="De metadata is succesvol opgeslagen."
                ).exec()

            return df
        except Exception:
            WarningDialog(
                title="Ongekende fout",
                text="Ongekende fout is opgetreden tijdens het opslaan.",
            ).exec()

    def closeEvent(self, event):
        if not self.intentional_close:
            dialog = YesNoDialog(
                title="Opslaan",
                text="Gemaakte wijzigingen opslaan?"
            )
            dialog.exec()

            if dialog.result():
                self.save_button_click()

        self.intentional_close = False
        event.accept()
