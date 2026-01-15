import sys

from src.utils.application import Application

app = Application()

from src.utils.constants import UI_TEXT_ELEMENTS

from src.window.base_window import MainWindow

from creator.widgets.main_widgets.analoog_widget import AnaloogWidget, MainWidget
from creator.widgets.main_widgets.digital_widget import DigitalWidget
from creator.widgets.main_widgets.migration_widget import MigrationWidget


def excepthook(cls, exception: Exception, traceback):
    app.error_handler(exception=exception)

def set_main(application: Application, main_window: MainWindow) -> None:
    print("setting new main")
    config = application.configuration

    active_type = config.active_type
    print(active_type)

    if active_type == "digitaal":
        main_window.central_widget = DigitalWidget(main_window)
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
    main_window.central_widget.load_items()


sys.excepthook = excepthook

main_window = MainWindow()
app.register_window(main_window)
app.application_type_changed_signal.connect(lambda: set_main(application=app, main_window=main_window))
set_main(application=app, main_window=main_window)

app.worker_controller.get_all_series()

main_window.show()

sys.exit(app.exec())
