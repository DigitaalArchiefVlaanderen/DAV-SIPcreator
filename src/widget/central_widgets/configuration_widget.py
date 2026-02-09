from copy import deepcopy
from functools import partial

from PySide6 import QtWidgets, QtCore, QtGui

from src.utils.constants import UI_TEXT_ELEMENTS, TI_ENVIRONMENT_NAME, PROD_ENVIRONMENT_NAME
from src.utils.data_objects.configuration import Environment, Misc

from src.widget.base_widget import BaseWidget


UI_TEXT = UI_TEXT_ELEMENTS["configuration"]


class ConfigurationWidget(BaseWidget):
    save_button_clicked_signal = QtCore.Signal()

    def setup_ui(self) -> None:
        self.new_configuration = deepcopy(self.application.configuration)

        self.vertical_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.vertical_layout)


        self.tab_widget = QtWidgets.QTabWidget()
        self.misc_tab = MiscTab(misc=self.new_configuration.misc)

        ti_env = self.new_configuration.get_environment(TI_ENVIRONMENT_NAME)
        prod_env = self.new_configuration.get_environment(PROD_ENVIRONMENT_NAME)
        self.ti_tab = EnvironmentTab(environment=ti_env)
        self.prod_tab = EnvironmentTab(environment=prod_env)

        self.tab_widget.addTab(self.misc_tab, "misc")
        self.tab_widget.addTab(self.ti_tab, TI_ENVIRONMENT_NAME)
        self.tab_widget.addTab(self.prod_tab, PROD_ENVIRONMENT_NAME)

        self.save_button = QtWidgets.QPushButton(text=UI_TEXT["save_button_text"])
        

        self.vertical_layout.addWidget(self.tab_widget)
        self.vertical_layout.addWidget(self.save_button)


        self.save_button.clicked.connect(self.save_button_clicked_handler)

    def save_button_clicked_handler(self) -> None:
        original_configuration = self.application.configuration
        new_configuration = self.new_configuration

        if original_configuration.active_type != new_configuration.active_type:
            self.application.application_type_changed_signal.emit()
        if original_configuration.active_role != new_configuration.active_role:
            self.application.application_role_changed_signal.emit()
        if original_configuration.active_environment_name != new_configuration.active_environment_name:
            self.application.application_environment_changed_signal.emit()
        if original_configuration.misc.bestandscontrole_lijst_location != new_configuration.misc.bestandscontrole_lijst_location:
            self.application.reset_bestandscontrole_location()

        for env_name in (e.name for e in original_configuration.environments):
            original_env = original_configuration.get_environment(env_name)
            new_env = new_configuration.get_environment(env_name)

            if original_env == new_env:
                continue

            # This means the series no longer match the configuration, get them again
            if original_env.get_api_info() != new_env.get_api_info():
                self.application.force_stop_series_retrieval_signal.emit(env_name)
                self.application.series[env_name] = []

        self.new_configuration.save()
        self.application.get_series()
        self.application.series_updated_signal.emit()
        self.save_button_clicked_signal.emit()


class MiscTab(BaseWidget):
    UI_TEXT = UI_TEXT["misc"]

    def __init__(self, misc: Misc) -> None:
        super().__init__()

        self.misc = misc

        self.setup_ui()

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.grid_layout)


        title_font = QtGui.QFont()
        title_font.setBold(True)
        title_font.setPointSize(20)
        self.title_label = QtWidgets.QLabel(text=self.UI_TEXT["title"])
        self.title_label.setFont(title_font)

        self.save_location_text_label = QtWidgets.QLabel(text=self.UI_TEXT["sip_creator_save_location_label_text"])
        self.save_location_label = QtWidgets.QLabel(text=self.misc.save_location)
        self.save_location_button = QtWidgets.QPushButton(text=self.UI_TEXT["sip_creator_save_location_button_text"])

        self.bestandscontrole_text_label = QtWidgets.QLabel(text=self.UI_TEXT["bestandscontrole_list_label_text"])
        self.bestandscontrole_label = QtWidgets.QLabel(text=self.misc.bestandscontrole_lijst_location)
        self.bestandscontrole_button = QtWidgets.QPushButton(text=self.UI_TEXT["bestandscontrole_list_button_text"])

        self.environment_selection_group = QtWidgets.QButtonGroup()
        self.role_selection_group = QtWidgets.QButtonGroup()
        self.sip_selection_group = QtWidgets.QButtonGroup()

        
        self.grid_layout.addWidget(self.title_label, 0, 0)
        self.grid_layout.addWidget(self.save_location_text_label, 1, 0)
        self.grid_layout.addWidget(self.save_location_label, 1, 1)
        self.grid_layout.addWidget(self.save_location_button, 2, 0, 1, 2)
        self.add_to_button_group(
            button_group=self.environment_selection_group,
            title=self.UI_TEXT["environments_selection_title"],
            button_labels_and_selected=self.misc.environments_activity,
            row=0,
            col=2,
        )
        self.grid_layout.addWidget(self.bestandscontrole_text_label, 3, 0)
        self.grid_layout.addWidget(self.bestandscontrole_label, 3, 1)
        self.grid_layout.addWidget(self.bestandscontrole_button, 4, 0, 1, 2)
        self.add_to_button_group(
            button_group=self.role_selection_group,
            title=self.UI_TEXT["role_selection_title"],
            button_labels_and_selected=self.misc.role_activity,
            row=3,
            col=2,
        )
        self.add_to_button_group(
            button_group=self.sip_selection_group,
            title=self.UI_TEXT["sip_selection_title"],
            button_labels_and_selected=self.misc.type_activity,
            row=6,
            col=2,
        )

    def add_to_button_group(self, button_group: QtWidgets.QButtonGroup, title: str, button_labels_and_selected: dict[str, bool], row: int, col: int) -> None:
        title_font = QtGui.QFont()
        title_font.setBold(True)
        title_font.setPointSize(20)

        title_widget = QtWidgets.QLabel(text=title)
        title_widget.setFont(title_font)

        button_layout = QtWidgets.QVBoxLayout()
        button_widget = QtWidgets.QWidget()
        button_widget.setLayout(button_layout)

        for button_label, is_selected in button_labels_and_selected.items():
            radio_button = QtWidgets.QRadioButton(text=button_label)
            radio_button.setChecked(is_selected)

            button_group.addButton(radio_button)
            button_layout.addWidget(radio_button)

        self.grid_layout.addWidget(title_widget, row, col)
        self.grid_layout.addWidget(button_widget, row+1, col)

class EnvironmentTab(BaseWidget):
    def __init__(self, environment: Environment):
        super().__init__()

        self.environment = environment

        self.setup_ui()

    def setup_ui(self) -> None:
        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.grid_layout)
        
        
        title_font = QtGui.QFont()
        title_font.setBold(True)
        title_font.setPointSize(20)
        self.api_title = QtWidgets.QLabel(text="API")
        self.api_title.setFont(title_font)
        
        self.ftps_title = QtWidgets.QLabel(text="FTPS")
        self.ftps_title.setFont(title_font)

        # NOTE: this will contain a mapping between field names and their widgets
        self.field_mapping: dict[str, dict[str, QtWidgets.QTextEdit]] = dict(
            api=dict(),
            ftps=dict()
        )


        self.grid_layout.addWidget(self.api_title, 0, 0, 1, 2)
        self.grid_layout.addWidget(self.ftps_title, 0, 3, 1, 2)

        for index, (key, value) in enumerate(self.environment.get_api_info().items(), start=1):
            label = QtWidgets.QLabel(text=key)
            text_field = QtWidgets.QTextEdit(text=value)
            self.field_mapping["api"][key] = text_field

            self.grid_layout.addWidget(label, index, 0)
            self.grid_layout.addWidget(text_field, index, 1)
        
        for index, (key, value) in enumerate(self.environment.get_ftps_info().items(), start=1):
            label = QtWidgets.QLabel(text=key)
            text_field = QtWidgets.QTextEdit(text=value)
            self.field_mapping["ftps"][key] = text_field

            self.grid_layout.addWidget(label, index, 3)
            self.grid_layout.addWidget(text_field, index, 4)

        for connection_type, connection_values in self.field_mapping.items():
            for key, text_field in connection_values.items():
                full_key = f"{connection_type}_{key}"

                text_field.textChanged.connect(
                    partial(lambda f, k: setattr(self.environment, k, f.toPlainText()), text_field, full_key)
                )

