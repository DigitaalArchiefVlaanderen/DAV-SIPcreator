import enum


class SIPStatus(enum.Enum):
    IN_PROGRESS = "color: #000000;"
    SIP_CREATED = "color: #010101;"
    UPLOADING = "color: #68B581;"

    # Status coming from API
    UPLOADED = "color: #42A362;"
    PROCESSING = "color: #888888;"
    ACCEPTED = "color: grey;"
    REJECTED = "color: red;"

    def get_status_label(self):
        match self.name:
            case "IN_PROGRESS":
                return "In verwerking"
            case "SIP_CREATED":
                return "Klaar voor upload"
            case "UPLOADING":
                return "Bezig met upload"
            case "UPLOADED":
                return "Klaar met upload"
            case "PROCESSING":
                return "Edepot verwerking"
            case "ACCEPTED":
                return "Gearchiveerd"
            case "REJECTED":
                return "Geweigerd"
