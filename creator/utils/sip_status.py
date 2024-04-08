import enum


class SIPStatus(enum.Enum):
    IN_PROGRESS = "color: black;"
    SIP_CREATED = "color: #42A362;"
    UPLOADING = "color: #68B581;"
    ARCHIVED = "color: grey;"
    REJECTED = "color: red;"

    def get_status_label(self):
        if self.name == "IN_PROGRESS":
            return "In verwerking"
        elif self.name == "SIP_CREATED":
            return "Klaar voor upload"
        elif self.name == "UPLOADING":
            return "Bezig met upload"
        elif self.name == "ARCHIVED":
            return "Gearchiveerd"
        elif self.name == "REJECTED":
            return "Geweigerd"
