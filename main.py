import sys

from creator.application import Application
from creator.mainwindow import MainWindow, set_main

app = Application(MainWindow, set_main_callback=set_main)
app.start()

try:
    sys.exit(app.exec())
except KeyboardInterrupt:
    sys.exit(-1)
