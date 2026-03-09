import os

from src.utils.data_objects.sip import SIP


class AnalogSIP(SIP):
    def __init__(self):
        super().__init__()

        self.uploaded: bool = False

    @property
    def db_path(self) -> str:
        return os.path.join(self.application.configuration.analoog_location, self.db_name)
