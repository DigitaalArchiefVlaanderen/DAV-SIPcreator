from src.utils.constants import UI_TEXT_ELEMENTS

from src.widget.central_widgets.central_widget import CentralWidget
from src.widget.central_widgets.digital.digital_widget import DigitalWidget

from src.window.base_window import MainWindow


class SipCreatorWindow(MainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.application.application_type_changed_signal.connect(self.reset_central_widget_handler)

        self.digital_widget = DigitalWidget(parent_window=self)

        self.reset_central_widget_handler()

    # Handlers
    def reset_central_widget_handler(self) -> None:
        # In case we switch, we want to make sure the worker stops
        if self.worker is not None:
            self.force_stop_worker_signal.emit()

        central_widget: CentralWidget

        match self.application.configuration.active_type:
            case "digitaal":
                central_widget = self.digital_widget
                worker_description = UI_TEXT_ELEMENTS["toolbar_info"]["digital"]["startup_loading_items_text"]
                self.setWindowTitle(UI_TEXT_ELEMENTS["window_titles"]["main"]["digital"])
            case t:
                raise ValueError(
                    UI_TEXT_ELEMENTS["errors"]["unexpected_application_type"].format(
                        application_type=t
                    )
                )
            
        self.setCentralWidget(central_widget)

        self.application.start_task(
            window=self,
            description=worker_description,
            function=central_widget.load_items,
            is_generator=True
        )

