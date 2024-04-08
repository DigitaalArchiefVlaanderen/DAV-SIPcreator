from PySide6 import QtWidgets, QtGui, QtCore
import pandas as pd

from ..controllers.api_controller import APIController
from ..utils.sip_status import SIPStatus
from ..utils.series import Series
from ..widgets.mapping_widget import TagMappingWidget
from ..widgets.toolbar import Toolbar
from ..widgets.warning_dialog import WarningDialog
from ..windows.grid_view import GridView


class SIPView(QtWidgets.QMainWindow):
    def __init__(self, sip_widget):
        super().__init__()

        self.application = QtWidgets.QApplication.instance()
        self.sip_widget = sip_widget

        # Only if no series is selected do we allow for it to be edited
        self.active = self.sip_widget.sip.series.name == ""

        self.listed_series = []

    def setup_ui(self):
        self.setWindowTitle("SIP")

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        self.toolbar = Toolbar()
        self.addToolBar(self.toolbar)

        # Show SIP info as passed down by the SIPWidget
        # Add controls to select Series, MetadataFile, do linking and generate folder structure
        # Finally add button to go to grid
        grid_layout = QtWidgets.QGridLayout()
        # grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        central_widget.setLayout(grid_layout)

        font = QtGui.QFont()
        font.setBold(True)
        font.setUnderline(True)
        font.setPointSize(20)
        self.title = QtWidgets.QLineEdit(text=self.sip_widget.sip.name)
        self.title.setFont(font)

        status = QtWidgets.QLabel(text=self.sip_widget.sip.status.get_status_label())
        status.setStyleSheet(self.sip_widget.sip.status.value)
        self.title.setEnabled(self.sip_widget.sip.status == SIPStatus.IN_PROGRESS)

        configuration = self.toolbar.configuration_view.get_configuration()
        self.series_combobox = QtWidgets.QComboBox()
        self.series_combobox.setEditable(True)
        self.series_combobox.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
        self.series_combobox.completer().setCompletionMode(
            QtWidgets.QCompleter.PopupCompletion
        )
        self.series_combobox.completer().setFilterMode(
            QtCore.Qt.MatchFlag.MatchContains
        )

        if self.active:
            listed_series = APIController.get_series(configuration)
            self.set_series_combobox_items(listed_series)
        else:
            self.series_combobox.setCurrentText(repr(self.sip_widget.sip.series))

        import_template_button = QtWidgets.QPushButton(text="Haal importsjabloon op")
        import_template_button.clicked.connect(self.import_template_clicked)

        metadata_file_button = QtWidgets.QPushButton(text="Selecteer metadata file")
        metadata_file_button.clicked.connect(self.metadata_file_clicked)
        self.metadata_path_label = QtWidgets.QLabel(
            text=self.sip_widget.sip.metadata_file_path
        )
        scrollarea = QtWidgets.QScrollArea()
        scrollarea.setWidget(self.metadata_path_label)
        scrollarea.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)

        self.tag_mapping_widget = TagMappingWidget()
        self.tag_mapping_widget.setMinimumSize(100, 400)

        self.open_grid_button = QtWidgets.QPushButton(text="Open metadata grid")
        self.open_grid_button.clicked.connect(lambda *_: self.open_grid_clicked())
        self.open_grid_button.setEnabled(False)

        # Disable when needed
        if not self.active:
            self.series_combobox.setEnabled(False)
            import_template_button.setEnabled(False)
            metadata_file_button.setEnabled(False)

            # Load data where needed
            self.tag_mapping_widget.fill_from_sip_widget(self.sip_widget)

            self.open_grid_button.setEnabled(True)

        # Layout
        grid_layout.addWidget(self.title, 0, 0)
        grid_layout.addWidget(status, 0, 1)
        grid_layout.addWidget(self.series_combobox, 1, 0)
        grid_layout.addWidget(import_template_button, 1, 1)
        grid_layout.addWidget(metadata_file_button, 2, 0)
        # grid_layout.addWidget(self.metadata_path_label, 2, 1)
        grid_layout.addWidget(scrollarea, 2, 1)
        grid_layout.addWidget(self.tag_mapping_widget, 3, 0, 5, 2)
        grid_layout.addWidget(self.open_grid_button, 8, 0, 1, 2)

    def set_series_combobox_items(self, series: list):
        for i in reversed(range(self.series_combobox.count())):
            self.series_combobox.removeItem(i)

        self.series_combobox.addItems([s.get_name() for s in series])
        self.listed_series = series

    def metadata_file_clicked(self):
        metadata_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            caption="Selecteer Metadata File", filter="Metadata Files (*.xlsx)"
        )

        if metadata_path != "":
            self.sip_widget.sip.metadata_file_path = metadata_path

            self.metadata_path_label.setText(self.sip_widget.sip.metadata_file_path)

            self.sip_widget.metadata_df = pd.read_excel(
                self.sip_widget.sip.metadata_file_path
            )
            self.tag_mapping_widget.add_to_metadata(self.sip_widget.metadata_df.columns)

    def import_template_clicked(self):
        series = self.listed_series[self.series_combobox.currentIndex()]

        self.import_template_location = APIController.get_import_template(
            self.toolbar.configuration_view.get_configuration(),
            series_id=series._id,
        )

        self.sip_widget.import_template_df = pd.read_excel(
            self.import_template_location, engine="openpyxl"
        )
        self.tag_mapping_widget.add_to_import_template(
            self.sip_widget.import_template_df.columns
        )
        self.sip_widget.sip.series = series

        self.open_grid_button.setEnabled(True)

    def open_grid_clicked(self, first_open=True):
        if first_open:
            mapping = self.tag_mapping_widget.get_mapping()

            if len(mapping) > 1 and "Naam" not in mapping.values():
                WarningDialog(
                    title="Mapping fout",
                    text="Een mapping naar 'Naam' in het importsjabloon moet opgegeven worden",
                ).exec()
                return

            # Save the data as part of the SIPWidget
            self.sip_widget.sip.name = self.title.text()
            self.sip_widget.sip.mapping = mapping

            # NOTE: this should not be needed if proper linking is provided
            self.sip_widget.sip_name_label.setText(self.sip_widget.sip.name)
            self.sip_widget.import_template_location = self.import_template_location

            self.application.state.update_sip(self.sip_widget.sip)

        # Open grid with sip_widget as info
        self.__grid_view = GridView(self.sip_widget)
        self.__grid_view.setup_ui()

        # We loaded data
        if not first_open:
            self.__grid_view.load_table()
        else:
            self.__grid_view.fill_table()

        self.__grid_view.show()
        self.close()