import threading
import time

from PySide6 import QtWidgets

from creator.utils.state import State
from creator.controllers.config_controller import ConfigController
from creator.controllers.db_controller import DBController
from creator.controllers.api_controller import APIController, APIException
from creator.utils.sip_status import SIPStatus


class SIPStatusThread(threading.Thread):
    def __init__(self, state: State):
        super().__init__()

        self.state = state

        self.daemon = True
        self.start()

    def run(self):
        # On first launch, allow the application time to start up
        time.sleep(30)

        while True:
            try:
                self._check_sip_status()
            except APIException:
                pass

            time.sleep(60)

    def _check_sip_status(self):
        # TODO: better sql get for only uploaded sips
        for sip in self.state.sips:
            # We only care about unfinished edepot statusses
            if sip.status in (
                SIPStatus.ACCEPTED,
                SIPStatus.REJECTED,
                SIPStatus.IN_PROGRESS,
                SIPStatus.SIP_CREATED,
                SIPStatus.UPLOADING,
            ):
                continue

            # Make sure we have the edepot id
            if sip.edepot_sip_id is None:
                sip.set_edepot_sip_id(APIController.get_sip_id(sip))

            new_status, fail_reason = APIController.get_sip_status(sip)

            if new_status == sip.status:
                continue

            sip.status = new_status
            self.state.update_sip(sip, fail_reason=fail_reason)


class Application(QtWidgets.QApplication):
    def __init__(self):
        super().__init__()

        self.db_controller = DBController("sqlite.db")
        self.config_controller = ConfigController("configuration.json")

        self.state = State(
            configuration_callback=self.config_controller.get_configuration,
            db_controller=self.db_controller,
        )

        self.sip_status_thread = SIPStatusThread(self.state)
