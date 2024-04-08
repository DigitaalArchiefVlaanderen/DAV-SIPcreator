import sys

from creator.application import Application
from creator.mainwindow import MainWindow


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
