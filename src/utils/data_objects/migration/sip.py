import os

from src.utils.data_objects.grid_data import GridData
from src.utils.data_objects.sip import SIP as CommonSIP
from src.utils.data_objects.sip_status import SIPStatus


class MigrationSIP(CommonSIP):
    def __init__(self):
        super().__init__()

        self.overdrachtslijst_name: str = ""

        self.main_grid_data: GridData = GridData()
        self.grid_data: GridData = self.main_grid_data
        self.series_grid_data: dict[str, GridData] = {}
        self.series_statuses: dict[str, SIPStatus] = {}

    @property
    def db_name(self) -> str:
        return f"{self.overdrachtslijst_name}.db"

    @property
    def db_path(self) -> str:
        return os.path.join(self.application.configuration.overdrachtslijsten_location, self.db_name)

    def derive_overall_status(self) -> None:
        if not self.series_statuses:
            return

        statuses = set(self.series_statuses.values())

        if all(s == SIPStatus.IN_PROGRESS for s in statuses):
            return

        if any(s == SIPStatus.UPLOADING for s in statuses):
            self.set_status(SIPStatus.UPLOADING)
        elif all(s in (SIPStatus.UPLOADED, SIPStatus.PROCESSING, SIPStatus.ACCEPTED) for s in statuses):
            self.set_status(SIPStatus.UPLOADED)
        elif any(s in (SIPStatus.UPLOADED, SIPStatus.PROCESSING, SIPStatus.ACCEPTED, SIPStatus.REJECTED) for s in statuses):
            self.set_status(SIPStatus.PARTIALLY_UPLOADED)
        elif all(s == SIPStatus.SIP_CREATED for s in statuses):
            self.set_status(SIPStatus.SIP_CREATED)
