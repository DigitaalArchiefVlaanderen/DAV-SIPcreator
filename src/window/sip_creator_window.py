from PySide6 import QtWidgets

from src.utils.constants import UI_TEXT_ELEMENTS, SIPType

from src.widget.central_widgets.analog.analog_widget import AnalogWidget
from src.widget.central_widgets.central_widget import CentralWidget
from src.widget.central_widgets.digital.digital_widget import DigitalWidget
from src.widget.central_widgets.migration.migration_widget import MigrationWidget

from src.window.base_window import MainWindow


class SipCreatorWindow(MainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.application.application_type_changed_signal.connect(self.reset_central_widget_handler)

        self.stacked_widget = QtWidgets.QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        self.digital_widget = DigitalWidget(parent_window=self)
        self.migration_widget = MigrationWidget(parent_window=self)
        self.analog_widget = AnalogWidget(parent_window=self)

        self.stacked_widget.addWidget(self.digital_widget)
        self.stacked_widget.addWidget(self.migration_widget)
        self.stacked_widget.addWidget(self.analog_widget)

        self.reset_central_widget_handler()

    # Handlers
    def reset_central_widget_handler(self) -> None:
        if self.worker is not None:
            self.force_stop_worker_signal.emit()

        central_widget: CentralWidget

        match self.application.configuration.active_type:
            case SIPType.DIGITAAL:
                central_widget = self.digital_widget
                worker_description = UI_TEXT_ELEMENTS["toolbar_info"]["digital"]["startup_loading_items_text"]
                self.setWindowTitle(UI_TEXT_ELEMENTS["window_titles"]["main"]["digital"])
            case SIPType.MIGRATIE | SIPType.ONROEREND_ERFGOED:
                central_widget = self.migration_widget
                worker_description = UI_TEXT_ELEMENTS["toolbar_info"]["migration"]["startup_loading_items_text"]
                self.setWindowTitle(
                    UI_TEXT_ELEMENTS["window_titles"]["main"].get(
                        self.application.configuration.active_type,
                        UI_TEXT_ELEMENTS["window_titles"]["main"]["migration"],
                    )
                )
            case SIPType.ANALOOG:
                central_widget = self.analog_widget
                worker_description = UI_TEXT_ELEMENTS["toolbar_info"]["analog"]["startup_loading_items_text"]
                self.setWindowTitle(UI_TEXT_ELEMENTS["window_titles"]["main"].get("analog", "SIP Creator - Analoog"))
            case t:
                raise ValueError(UI_TEXT_ELEMENTS["errors"]["unexpected_application_type"].format(application_type=t))

        self.stacked_widget.setCurrentWidget(central_widget)

        self.application.start_task(
            window=self, description=worker_description, function=central_widget.load_items, is_generator=True
        )
