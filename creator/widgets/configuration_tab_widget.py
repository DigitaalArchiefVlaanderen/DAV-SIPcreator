from PySide6 import QtWidgets, QtGui, QtCore
import os

from ..utils.configuration import Environment, Misc


class ConnectionConfigurationTab(QtWidgets.QWidget):
    def __init__(self, environment: Environment):
        super().__init__()

        self.tab_links = {}

        self.grid_layout = QtWidgets.QGridLayout()
        self.setLayout(self.grid_layout)

        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(20)

        title = QtWidgets.QLabel(text="API")
        title.setFont(font)
        self.grid_layout.addWidget(title, 0, 0)
        self.tab_links["API"] = {}

        for index, (key, value) in enumerate(environment.get_api_info().items(), start=1):
            label = QtWidgets.QLabel(text=key)
            text_field = QtWidgets.QTextEdit(text=value)
            self.tab_links["API"][key] = text_field

            self.grid_layout.addWidget(label, index, 0)
            self.grid_layout.addWidget(text_field, index, 1)

        title = QtWidgets.QLabel(text="FTPS")
        title.setFont(font)
        self.grid_layout.addWidget(title, 0, 3)
        self.tab_links["FTPS"] = {}

        for index, (key, value) in enumerate(environment.get_ftps_info().items(), start=1):
            label = QtWidgets.QLabel(text=key)
            text_field = QtWidgets.QTextEdit(text=value)
            self.tab_links["FTPS"][key] = text_field

            self.grid_layout.addWidget(label, index, 3)
            self.grid_layout.addWidget(text_field, index, 4)

    def get_tab_info(self):
        return {
            connection_type: {
                key: text_field.toPlainText() for key, text_field in values.items()
            }
            for connection_type, values in self.tab_links.items()
        }


class MiscConfigurationTab(QtWidgets.QWidget):
    def __init__(self, misc: Misc):
        super().__init__()

        self.tab_links = {}

        self.grid_layout = QtWidgets.QGridLayout()
        self.grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)
        self.setLayout(self.grid_layout)

        font = QtGui.QFont()
        font.setBold(True)
        font.setPointSize(20)

        title = QtWidgets.QLabel(text="Misc opties")
        title.setFont(font)
        self.grid_layout.addWidget(title, 0, 0)

        key = "SIP Creator opslag locatie"
        value = os.path.normpath(misc.save_location)
        label = QtWidgets.QLabel(text=key)
        self.location_label = QtWidgets.QLabel(text=value)
        change_location_button = QtWidgets.QPushButton(text="Selecteer opslag locatie")
        change_location_button.clicked.connect(self.change_location_clicked)
        self.tab_links[key] = self.location_label

        self.grid_layout.addWidget(label, 1, 0)
        self.grid_layout.addWidget(self.location_label, 1, 1)
        self.grid_layout.addWidget(change_location_button, 2, 0, 1, 2)

        self.environment_selection_group = QtWidgets.QButtonGroup()
        self.role_selection_group = QtWidgets.QButtonGroup()
        self.type_selection_group = QtWidgets.QButtonGroup()

        button_group_info = [
            ("Actieve omgeving", misc.environments_activity, self.environment_selection_group),
        ]

        for index, (title, activity, button_group) in enumerate(button_group_info):
            row = index * 3

            title_widget = QtWidgets.QLabel(text=title)
            title_widget.setFont(font)
            self.grid_layout.addWidget(title_widget, row, 2)

            button_grid_layout = QtWidgets.QGridLayout()
            button_grid = QtWidgets.QWidget()
            button_grid.setLayout(button_grid_layout)
            self.grid_layout.addWidget(button_grid, row + 1, 2, 2, 1)

            for i, (button_label, is_active) in enumerate(activity.items()):
                radio_button = QtWidgets.QRadioButton(text=button_label)
                radio_button.setChecked(is_active)

                button_group.addButton(radio_button)
                button_grid_layout.addWidget(radio_button, i, 0)

    def get_tab_info(self):
        return {
            **{
                "Omgevingen": {
                    button.text(): button.isChecked()
                    for button in self.environment_selection_group.buttons()
                },
                "Type SIPs": {
                    button.text(): button.isChecked()
                    for button in self.type_selection_group.buttons()
                },
            },
            **{key: text_field.text() for key, text_field in self.tab_links.items()},
        }

    def change_location_clicked(self):
        folder_path = QtWidgets.QFileDialog.getExistingDirectory(
            caption="Selecteer opslag locatie"
        )

        if folder_path != "":
            self.location_label.setText(
                os.path.normpath(os.path.join(folder_path, "SIP_Creator"))
            )
