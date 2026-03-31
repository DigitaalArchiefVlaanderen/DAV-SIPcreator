import enum


class SIPStatus(enum.Enum):
    IN_PROGRESS = "color: #000000;"
    SIP_CREATED = "color: #010101;"
    UPLOADING = "color: #68B581;"
    PARTIALLY_UPLOADED = "color: #5BA87A;"
    DELETED = "color: white"

    # Status coming from API
    UPLOADED = "color: #42A362;"
    PROCESSING = "color: #888888;"
    ACCEPTED = "color: grey;"
    REJECTED = "color: red;"

    @property
    def status_label(self):
        from src.utils.constants import UI_TEXT_ELEMENTS

        return UI_TEXT_ELEMENTS["sip"]["status"][self.name.lower()]["text"]

    @property
    def priority(self):
        from src.utils.constants import UI_TEXT_ELEMENTS

        return UI_TEXT_ELEMENTS["sip"]["status"][self.name.lower()]["priority"]
