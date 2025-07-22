from creator.application import Application

from creator.windows.mainwindow import MainWindow

from creator.widgets.main_widgets.analoog_widget import AnaloogWidget
from creator.widgets.main_widgets.digital_widget import DigitalWidget
from creator.widgets.main_widgets.migration_widget import MigrationWidget


def set_main(application: Application, main: MainWindow) -> None:
    config = application.state.configuration

    active_type = config.active_type

    if active_type == "digitaal":
        main.central_widget = DigitalWidget(main)
    elif active_type in ("migratie", "onroerend_erfgoed"):
        main.central_widget = MigrationWidget(main)
    elif active_type == "analoog":
        main.central_widget = AnaloogWidget(main)
    else:
        raise ValueError("Active type not recognized")

    main.setWindowTitle(f"SIP Creator {active_type.replace("_", " ")}")
    main.setCentralWidget(None)
    main.setCentralWidget(main.central_widget)
    main.central_widget.setup_ui()
    main.central_widget.load_items()


