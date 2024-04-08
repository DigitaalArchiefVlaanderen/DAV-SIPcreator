import sys

from creator.application import Application
from creator.mainwindow import MainWindow


app = Application()

ui = MainWindow()
ui.setup_ui()
ui.load_items()
ui.show()

sys.exit(app.exec())
