
class APIItemStatus:
    def __init__(self, raw_status: str):
        self.raw_status = raw_status

    @property
    def is_concept(self):
        return self.raw_status == "Concept"

    @property
    def is_published(self):
        return self.raw_status == "Published"
    
    @property
    def is_valid(self):
        return self.raw_status == "Draft.Valid"
    
    @property
    def is_processing(self):
        return self.raw_status == "Processing" or self.is_concept

    @property
    def is_invalid(self):
        return not self.is_published and not self.is_valid and not self.is_processing
