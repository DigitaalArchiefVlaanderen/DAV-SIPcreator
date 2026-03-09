from src.utils.data_objects.grid_data import GridData
from src.utils.data_objects.sip import SIP as CommonSIP


class MigrationSIP(CommonSIP):
    def __init__(self):
        super().__init__()

        self.overdrachtslijst_name: str = ""

        self.main_grid_data: GridData = GridData()
        self.grid_data: GridData = self.main_grid_data
        self.series_grid_data: dict[str, GridData] = {}

    @property
    def db_name(self) -> str:
        return f"{self.overdrachtslijst_name}.db"
