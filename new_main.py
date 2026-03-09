import sys
from types import TracebackType

from src.utils.application import Application

import traceback as tb_module

def excepthook(cls, exception: Exception, traceback: TracebackType):
    tb_module.print_exception(cls, exception, traceback)
    app.error_handler(exception=exception)


if sys.stderr is not None:
    import faulthandler
    faulthandler.enable()
sys.excepthook = excepthook


app = Application()
app.window_controller.sip_creator_window.show()


sys.exit(app.exec())
