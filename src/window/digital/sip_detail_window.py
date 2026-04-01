from src.controller.api_controller import APIController

from src.utils.constants import UI_TEXT_ELEMENTS
from src.utils.data_objects.digital.sip import SIP
from src.utils.workers.worker import Worker

from src.widget.central_widgets.digital.sip_detail_widget import SipDetailWidget

from src.window.base_window import Window


class SipDetailWindow(Window):
    UI_TEXT = UI_TEXT_ELEMENTS["toolbar_info"]["digital"]

    def __init__(self, sip: SIP) -> None:
        super().__init__()

        self.sip = sip

        self.setup_ui()
        self.setup_signals()

    def setup_ui(self) -> None:
        self.setWindowTitle(self.sip.name)

        self.sip_detail_widget = SipDetailWidget(parent_window=self, sip=self.sip)
        self.setCentralWidget(self.sip_detail_widget)

    def setup_signals(self) -> None:
        self.sip.name_changed_signal.connect(lambda: self.setWindowTitle(self.sip.name))

    # Background tasks
    def start_retrieve_import_template_task(self) -> Worker:
        return self.application.start_task(
            window=self,
            description=self.UI_TEXT["import_template_retrieval_text"],
            function=lambda: APIController.get_import_template(
                configuration=self.application.configuration,
                environment=self.sip.environment,
                series_id=self.sip.series._id,
            ),
            is_generator=False,
        )
