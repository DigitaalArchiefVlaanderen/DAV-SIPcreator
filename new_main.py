import sys
from types import TracebackType

from src.utils.application import Application

def excepthook(cls, exception: Exception, traceback: TracebackType):
    app.error_handler(exception=exception)
    print(traceback.tb_frame)


import faulthandler
faulthandler.enable()
# sys.excepthook = excepthook


app = Application()
app.window_controller.sip_creator_window.show()


sys.exit(app.exec())
