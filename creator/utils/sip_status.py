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
                return "Geaccepteerd"
            case "REJECTED":
                return "Geweigerd"

    def get_priority(self):
        # Priotity for showing, lower is more prio
        match self.name:
            case "IN_PROGRESS":
                return 0
            case "SIP_CREATED":
                return 1
            case "UPLOADING":
                return 2
            case "UPLOADED":
                return 3
            case "PROCESSING":
                return 4
            case "ACCEPTED":
                return 5
            case "REJECTED":
                return 6
