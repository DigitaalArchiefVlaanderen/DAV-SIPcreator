from PySide6 import QtWidgets

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
