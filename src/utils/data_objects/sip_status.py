import enum

from src.utils.constants import UI_TEXT_ELEMENTS

UI_TEXT = UI_TEXT_ELEMENTS["sip"]["status"]


class SIPStatus(enum.Enum):
    IN_PROGRESS = "color: #000000;"
    SIP_CREATED = "color: #010101;"
    UPLOADING = "color: #68B581;"
    DELETED = "color: white"

    # Status coming from API
    UPLOADED = "color: #42A362;"
    PROCESSING = "color: #888888;"
    ACCEPTED = "color: grey;"
    REJECTED = "color: red;"

    @property
    def status_label(self):
        return UI_TEXT[self.name.lower()]["text"]

    @property
    def priority(self):
        # Priotity for showing, lower is more prio
        return UI_TEXT[self.name.lower()]["priority"]
