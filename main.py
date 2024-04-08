from PySide6 import QtWidgets

import sys

from creator.mainwindow import MainWindow
from creator.utils.state import State
from creator.controllers.config_controller import ConfigController
from creator.controllers.db_controller import DBController


class Application(QtWidgets.QApplication):
    def __init__(self):
        super().__init__()

        self.db_controller = DBController("sqlite.db")
        self.config_controller = ConfigController("configuration.json")

        self.state = State(
            configuration_callback=self.config_controller.get_configuration,
            db_controller=self.db_controller,
        )


app = Application()

ui = MainWindow()
ui.setup_ui()
ui.load_items()
ui.show()

sys.exit(app.exec())

# TODO: use FTPS button in configuration, default on
# TODO: color tab by active?
# TODO: add the environment to the SIP
# TODO: change mapping after the fact

# TODO: add field
# TODO: statussen via e-depot
