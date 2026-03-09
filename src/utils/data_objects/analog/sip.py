from src.utils.data_objects.sip import SIP


class AnalogSIP(SIP):
    def __init__(self):
        super().__init__()

        self.uploaded: bool = False
