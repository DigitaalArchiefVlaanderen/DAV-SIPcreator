import sys

from creator.application import Application
from creator.mainwindow import set_main

from creator.windows.mainwindow import MainWindow

from creator.widgets.warning_dialog import WarningDialog

def excepthook(cls, exception, traceback):
    WarningDialog(
        title="Een fout is opgetreden",
        text=f"{exception}"
    ).exec()


sys.excepthook = excepthook
app = Application(MainWindow, set_main_callback=set_main)
app.state.check_series_loaded()

app.start()
sys.exit(app.exec())
