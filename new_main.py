import sys
from types import TracebackType

from src.utils.application import Application

app = Application()

from src.utils.constants import UI_TEXT_ELEMENTS

from src.widget.central_widgets.digital_widget import DigitalWidget

from src.window.base_window import MainWindow

from creator.widgets.main_widgets.analoog_widget import AnaloogWidget
from creator.widgets.main_widgets.migration_widget import MigrationWidget


def excepthook(cls, exception: Exception, traceback: TracebackType):
    app.error_handler(exception=exception)
    print(traceback.tb_frame)

def set_main(application: Application, main_window: MainWindow) -> None:
    if main_window.worker is not None:
        main_window.force_stop_worker_signal.emit()

    config = application.configuration

    active_type = config.active_type
    UI_TEXT = UI_TEXT_ELEMENTS["toolbar_info"]

    loading_is_generator = False

    if active_type == "digitaal":
        main_window.central_widget = DigitalWidget()
        UI_TEXT = UI_TEXT["digital_background_work"]
        loading_is_generator = True
    elif active_type in ("migratie", "onroerend_erfgoed"):
        main_window.central_widget = MigrationWidget(main_window)
    elif active_type == "analoog":
        main_window.central_widget = AnaloogWidget(main_window)
    else:
        raise ValueError(UI_TEXT_ELEMENTS["errors"]["unexpected_application_type"])
    
    main_window.setWindowTitle(f"Sip Creator {active_type.replace("_", " ")}")
    main_window.setCentralWidget(None)
    main_window.setCentralWidget(main_window.central_widget)

    main_window.central_widget.setup_ui()

    # Toolbar showing progress
    application.work_in_progress_signal.emit(main_window, UI_TEXT)
    main_window.worker = application.worker_controller.run_thread(
        thread_function=main_window.central_widget.load_items,
        thread_is_generator=loading_is_generator
    )
    main_window.worker.about_to_finish_signal.connect(lambda: application.work_ended_signal.emit(main_window))

import faulthandler
faulthandler.enable()
# sys.excepthook = excepthook

main_window = MainWindow()
app.application_type_changed_signal.connect(lambda: set_main(application=app, main_window=main_window))
set_main(application=app, main_window=main_window)

main_window.show()

sys.exit(app.exec())
